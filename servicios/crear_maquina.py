import boto3
import os
import time
from dotenv import load_dotenv

# --- 1. PREPARACIÓN INFALIBLE DE RUTAS ---
# Esto calcula la ruta exacta donde está guardado este script en tu disco duro
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
print(f"📍 Trabajando en: {DIRECTORIO_ACTUAL}")

# Buscamos el archivo info.env en ESTA misma carpeta
ruta_env = os.path.join(DIRECTORIO_ACTUAL, ".env")

if os.path.exists(ruta_env):
    print("📂 Cargando credenciales de info.env...")
    load_dotenv(ruta_env)
else:
    # Si no encuentra info.env, intenta buscar .env por si acaso
    ruta_env_alt = os.path.join(DIRECTORIO_ACTUAL, ".env")
    if os.path.exists(ruta_env_alt):
        print("📂 Cargando credenciales de .env...")
        load_dotenv(ruta_env_alt)
    else:
        print(f"❌ ERROR CRÍTICO: No encuentro 'info.env' ni '.env' en: {DIRECTORIO_ACTUAL}")
        exit()

# Carga de variables
AWS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION = os.getenv("AWS_REGION", "us-west-2") 

if not AWS_KEY or not AWS_SECRET:
    print("❌ ERROR: El archivo de entorno está vacío o mal escrito.")
    exit()

# --- 2. CONEXIÓN CON AWS ---
try:
    ec2 = boto3.client('ec2', region_name=REGION, aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    ec2_resource = boto3.resource('ec2', region_name=REGION, aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
except Exception as e:
    print(f"❌ Error conectando: {e}")
    exit()

# --- FUNCIONES ---

def conseguir_ami_ubuntu():
    """Busca la ID de la última imagen de Ubuntu 22.04"""
    print(f"🔎 Buscando Ubuntu 22.04 en {REGION}...")
    filters = [
        {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']},
        {'Name': 'virtualization-type', 'Values': ['hvm']},
        {'Name': 'architecture', 'Values': ['x86_64']}
    ]
    response = ec2.describe_images(Filters=filters, Owners=['099720109477'])
    images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
    if not images: raise Exception("No encontré imagen de Ubuntu.")
    return images[0]['ImageId']

def crear_key_pair(nombre_clave="HackEPS-Key"):
    """
    Crea la llave SSH asegurando que el archivo .pem se guarde
    EXACTAMENTE al lado del script.
    """
    # AQUÍ ESTÁ LA MAGIA: Forzamos la ruta completa
    ruta_pem_completa = os.path.join(DIRECTORIO_ACTUAL, f"{nombre_clave}.pem")
    
    # 1. Lógica de recuperación: ¿Tengo el archivo físico?
    if not os.path.exists(ruta_pem_completa):
        print(f"⚠️ No encuentro el archivo en: {ruta_pem_completa}")
        print("♻️ Intentando regenerar la llave en AWS...")
        try:
            ec2.delete_key_pair(KeyName=nombre_clave)
            print("🗑️ Clave antigua borrada de la nube.")
        except:
            pass 

    # 2. Crear la nueva
    try:
        key_pair = ec2.create_key_pair(KeyName=nombre_clave)
        
        # Guardar el archivo en la ruta forzada
        with open(ruta_pem_completa, "w") as file:
            file.write(key_pair['KeyMaterial'])
        
        # Permisos de solo lectura (chmod 400)
        os.chmod(ruta_pem_completa, 0o400)
        print(f"🔑 ¡NUEVA LLAVE CREADA! Guardada en: {ruta_pem_completa}")
        
    except Exception as e:
        if "Duplicate" in str(e):
            print(f"ℹ️ Usando llave existente (ya tienes el archivo en la carpeta correcta).")
        else:
            print(f"❌ Error creando llave: {e}")
            
    # Devolvemos AMBOS: el nombre para AWS y la ruta para tu comando SSH
    return nombre_clave, ruta_pem_completa

def seleccionar_tamano():
    print("\n📊 ELIGE POTENCIA:")
    print("   1. T2.Micro (Gratis/Barata)")
    print("   2. T3.Small (Recomendada)")
    opcion = input("👉 Opción (1-2): ")
    return "t3.small" if opcion == "2" else "t2.micro"

# --- EJECUCIÓN PRINCIPAL ---

if __name__ == "__main__":
    try:
        # 1. Preparar ingredientes
        tipo = seleccionar_tamano()
        ami_id = conseguir_ami_ubuntu()
        
        # Recuperamos nombre Y ruta del archivo
        nombre_key, ruta_key_absoluta = crear_key_pair() 
        
        print(f"\n🚀 Lanzando instancia {tipo}...")
        
        # 2. Crear la máquina
        instancia = ec2_resource.create_instances(
            ImageId=ami_id,
            MinCount=1, MaxCount=1,
            InstanceType=tipo,
            KeyName=nombre_key,
            TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': 'NebulOuS-Node'}]}]
        )[0]
        
        print(f"✅ ¡Enviado! ID: {instancia.id}")
        print("⏳ Esperando a que arranque (30s)...")
        
        instancia.wait_until_running()
        instancia.reload()
        
        print("\n🎉 ¡LISTO PARA ENTRAR!")
        print(f"📡 IP:  {instancia.public_ip_address}")
        print(f"🔑 Comando SSH (Copia y pega esto):")
        print("-" * 60)
        # Usamos la ruta absoluta entre comillas para que no falle nunca
        print(f"ssh -i \"{ruta_key_absoluta}\" ubuntu@{instancia.public_ip_address}")
        print("-" * 60)

    except Exception as e:
        print(f"\n❌ Error fatal: {e}")