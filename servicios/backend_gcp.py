import os
import time
from google.cloud import compute_v1
from google.oauth2 import service_account
from google.cloud.compute_v1.services.zone_operations import ZoneOperationsClient

# --- CONFIGURACIÓN ---
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))

# Busca el archivo JSON que empiece por 'hackeps' o usa uno genérico
archivo_json = "hackeps2025-team4-adrian.json" # <--- CONFIRMA QUE SE LLAMA ASÍ
KEY_PATH = os.path.join(DIRECTORIO_ACTUAL, archivo_json)

def get_credentials():
    if not os.path.exists(KEY_PATH):
        raise Exception(f"❌ No encuentro el archivo JSON de Google en: {KEY_PATH}")
    return service_account.Credentials.from_service_account_file(KEY_PATH)

def generar_pares_claves_local(nombre_usuario="hackeps"):
    """Genera archivos de clave pública y privada en la carpeta del proyecto"""
    ruta_privada = os.path.join(DIRECTORIO_ACTUAL, "gcp_key")
    ruta_publica = os.path.join(DIRECTORIO_ACTUAL, "gcp_key.pub")
    
    if not os.path.exists(ruta_privada) or not os.path.exists(ruta_publica):
        print("🔑 Generando nuevas claves SSH para Google...")
        # Usamos ssh-keygen del sistema
        os.system(f'ssh-keygen -t rsa -b 2048 -f "{ruta_privada}" -N "" -C "{nombre_usuario}" -q')
        os.chmod(ruta_privada, 0o400)
    
    with open(ruta_publica, 'r') as f:
        public_content = f.read().strip()
        
    return ruta_privada, f"{nombre_usuario}:{public_content}"

def inyectar_ssh(project_id, zone, instance_name, user_ssh_string, credentials):
    """Mete la clave en la máquina ya creada (Lógica de tu amigo ssh.py mejorada)"""
    client = compute_v1.InstancesClient(credentials=credentials)
    instance = client.get(project=project_id, zone=zone, instance=instance_name)
    
    # Preservar claves existentes
    items = []
    existing_keys = ""
    if instance.metadata.items:
        for item in instance.metadata.items:
            if item.key == "ssh-keys":
                existing_keys = item.value
            else:
                items.append(item)
    
    # Añadir la nuestra
    new_keys = f"{existing_keys}\n{user_ssh_string}" if existing_keys else user_ssh_string
    items.append(compute_v1.Items(key="ssh-keys", value=new_keys))
    
    metadata = compute_v1.Metadata(items=items, fingerprint=instance.metadata.fingerprint)
    
    request = compute_v1.SetMetadataInstanceRequest(
        project=project_id, zone=zone, instance=instance_name, metadata_resource=metadata
    )
    
    op = client.set_metadata(request=request)
    op_client = ZoneOperationsClient(credentials=credentials)
    op_client.wait(operation=op.name, project=project_id, zone=zone)
    print("✅ Clave SSH inyectada en Google.")

def crear_maquina_gcp(nombre, zona, tipo_maquina, imagen_os):
    """Función principal llamada desde la web"""
    creds = get_credentials()
    project_id = creds.project_id
    client = compute_v1.InstancesClient(credentials=creds)

    # 1. Selección de Imagen
    if "Ubuntu" in imagen_os:
        source_img = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
    elif "Debian" in imagen_os:
        source_img = "projects/debian-cloud/global/images/family/debian-11"
    else:
        source_img = "projects/debian-cloud/global/images/family/debian-11"

    # 2. Configuración de Disco y Red
    disk = compute_v1.AttachedDisk(
        boot=True, auto_delete=True,
        initialize_params=compute_v1.AttachedDiskInitializeParams(source_image=source_img, disk_size_gb=15)
    )
    network = compute_v1.NetworkInterface(
        name="nic0", network="global/networks/default",
        access_configs=[compute_v1.AccessConfig(name="External NAT", type_="ONE_TO_ONE_NAT")]
    )

    machine_type_full = f"zones/{zona}/machineTypes/{tipo_maquina}"

    vm_resource = compute_v1.Instance(
        name=nombre, machine_type=machine_type_full,
        disks=[disk], network_interfaces=[network]
    )

    # 3. Crear VM
    print(f"🔥 GCP: Creando {nombre} en {zona}...")
    op = client.insert(project=project_id, zone=zona, instance_resource=vm_resource)
    
    op_client = ZoneOperationsClient(credentials=creds)
    op_client.wait(operation=op.name, project=project_id, zone=zona)
    
    # 4. Inyectar SSH y obtener IP
    ruta_key_privada, ssh_string = generar_pares_claves_local("hackeps")
    inyectar_ssh(project_id, zona, nombre, ssh_string, creds)
    
    # Recargar para ver IP
    instance = client.get(project=project_id, zone=zona, instance=nombre)
    ip_publica = instance.network_interfaces[0].access_configs[0].nat_i_p

    return {
        "ip": ip_publica,
        "id": str(instance.id),
        "key_path": ruta_key_privada,
        "user": "hackeps" # Usuario forzado para GCP
    }

def listar_zonas():
    return ["us-central1-a", "europe-west1-b", "europe-west4-a"] # Simplificado para hackathon