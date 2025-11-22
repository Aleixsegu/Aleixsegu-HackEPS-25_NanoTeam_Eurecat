import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError

# --- 1. CONFIGURACIÓN ---
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
ruta_env = os.path.join(DIRECTORIO_ACTUAL, "info.env")
if not os.path.exists(ruta_env):
    ruta_env = os.path.join(DIRECTORIO_ACTUAL, ".env")

load_dotenv(ruta_env)

AWS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION = os.getenv("AWS_REGION", "us-west-2")

try:
    ec2_resource = boto3.resource('ec2', region_name=REGION, aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    ec2_client = boto3.client('ec2', region_name=REGION, aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
except Exception as e:
    print(f"Error crítico: {e}")

# --- 2. FUNCIONES DE LÓGICA ---

def obtener_tipos_instancia():
    """Obtiene lista de potencias T2 y T3"""
    try:
        response = ec2_client.describe_instance_types(
            Filters=[{'Name': 'instance-type', 'Values': ['t2.*', 't3.*']}, {'Name': 'current-generation', 'Values': ['true', 'false']}]
        )
        tipos = []
        for t in response['InstanceTypes']:
            nombre = t['InstanceType']
            ram = t['MemoryInfo']['SizeInMiB'] / 1024
            cpus = t['VCpuInfo']['DefaultVCpus']
            tipos.append(f"{nombre} ({cpus} vCPU, {ram:.1f} GB RAM)")
        return sorted(tipos)
    except:
        return ["t2.micro (Default)"]

def buscar_ami_por_os(nombre_os):
    """
    Imita el menú de 'Inicio Rápido' de AWS.
    Busca la última versión oficial de cada sistema.
    """
    print(f"🔎 Buscando la última AMI oficial para: {nombre_os}...")
    
    filtros = []
    owner_id = ""

    # LÓGICA DE FILTROS (Igual que en la consola de AWS)
    if "Ubuntu" in nombre_os:
        # Canonical (Dueño oficial de Ubuntu)
        owner_id = '099720109477' 
        filtros = [{'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']}]
        
    elif "Amazon Linux" in nombre_os:
        # Amazon (Oficial)
        owner_id = '137112412989'
        filtros = [{'Name': 'name', 'Values': ['al2023-ami-2023.*-x86_64']}]
        
    elif "Windows" in nombre_os:
        # Amazon (Oficial para Windows)
        owner_id = '801119661308'
        filtros = [{'Name': 'name', 'Values': ['Windows_Server-2022-English-Full-Base-*']}]
        
    elif "Red Hat" in nombre_os:
        # Red Hat (Oficial)
        owner_id = '309956199498'
        filtros = [{'Name': 'name', 'Values': ['RHEL-9.*_HVM-*-x86_64-*-Hourly2-GP2']}]

    # Ejecutamos la búsqueda en el catálogo de AWS
    try:
        images = ec2_client.describe_images(
            Filters=filtros + [{'Name': 'architecture', 'Values': ['x86_64']}], # Solo Intel/AMD
            Owners=[owner_id]
        )
        
        # Ordenamos por fecha (la más nueva primero)
        lista_ordenada = sorted(images['Images'], key=lambda x: x['CreationDate'], reverse=True)
        
        if not lista_ordenada:
            raise Exception(f"No encontrada ninguna imagen para {nombre_os}")
            
        id_imagen = lista_ordenada[0]['ImageId']
        nombre_imagen = lista_ordenada[0]['Name']
        print(f"✅ Imagen encontrada: {id_imagen} ({nombre_imagen})")
        return id_imagen

    except Exception as e:
        print(f"❌ Error buscando AMI: {e}")
        raise e

def garantizar_llave(nombre_clave):
    ruta_llave = os.path.join(DIRECTORIO_ACTUAL, f"{nombre_clave}.pem")
    try:
        ec2_client.describe_key_pairs(KeyNames=[nombre_clave])
        existe_en_aws = True
    except ClientError:
        existe_en_aws = False

    if existe_en_aws and not os.path.exists(ruta_llave):
        ec2_client.delete_key_pair(KeyName=nombre_clave)
        existe_en_aws = False
    
    if not existe_en_aws:
        if os.path.exists(ruta_llave): os.remove(ruta_llave)
        key = ec2_client.create_key_pair(KeyName=nombre_clave)
        with open(ruta_llave, "w") as f: f.write(key['KeyMaterial'])
        os.chmod(ruta_llave, 0o400)
    
    return ruta_llave

def gestionar_security_group(nombre_grupo="NebulOuS-Multi-OS"):
    try:
        response = ec2_client.describe_security_groups(GroupNames=[nombre_grupo])
        return response['SecurityGroups'][0]['GroupId']
    except ClientError:
        print("🛡️ Creando Firewall nuevo...")
        grupo = ec2_resource.create_security_group(GroupName=nombre_grupo, Description="Acceso SSH y RDP")
        # Puerto 22 (SSH - Linux)
        grupo.authorize_ingress(IpPermissions=[{'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}])
        # Puerto 3389 (RDP - Windows)
        grupo.authorize_ingress(IpPermissions=[{'IpProtocol': 'tcp', 'FromPort': 3389, 'ToPort': 3389, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}])
        # Puerto 80 (Web - Opcional)
        grupo.authorize_ingress(IpPermissions=[{'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}])
        return grupo.id

# --- 3. FUNCIÓN PRINCIPAL ---

def crear_maquina_web(nombre_maquina, tipo_instancia, sistema_operativo):
    print(f"🔥 WEB: Solicitando {nombre_maquina} ({sistema_operativo})...")
    
    ami_id = buscar_ami_por_os(sistema_operativo)
    nombre_clave = "HackEPS-Key"
    ruta_llave = garantizar_llave(nombre_clave)
    sg_id = gestionar_security_group()

    instancia = ec2_resource.create_instances(
        ImageId=ami_id,
        MinCount=1, MaxCount=1,
        InstanceType=tipo_instancia,
        KeyName=nombre_clave,
        SecurityGroupIds=[sg_id],
        TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': nombre_maquina}, {'Key': 'OS', 'Value': sistema_operativo}]}]
    )[0]

    instancia.wait_until_running()
    instancia.reload()

    return {
        "ip": instancia.public_ip_address,
        "id": instancia.id,
        "key_path": ruta_llave,
        "ami": ami_id
    }