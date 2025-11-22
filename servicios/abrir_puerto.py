import boto3
import os
from dotenv import load_dotenv

# 1. Cargar credenciales
load_dotenv()
REGION = os.getenv('AWS_REGION', 'us-west-2')

ec2 = boto3.client('ec2', region_name=REGION)
ec2_resource = boto3.resource('ec2', region_name=REGION)

# PON AQUÍ LA ID DE LA MÁQUINA QUE CREASTE ANTES
# (La tienes en la salida del script anterior, algo como 'i-0662e...')
INSTANCE_ID = "i-0b6905eb0697a0a08"  # <--- ¡CÁMBIALA POR LA TUYA!

print(f"🔧 Arreglando firewall para la máquina {INSTANCE_ID} en {REGION}...")

try:
    # 1. Obtener información de la máquina
    instancia = ec2_resource.Instance(INSTANCE_ID)
    
    # Obtener el Grupo de Seguridad (El Firewall) que tiene asignado
    grupos = instancia.security_groups
    if not grupos:
        print("❌ Error: Esta máquina no tiene Grupo de Seguridad.")
        exit()
        
    sg_id = grupos[0]['GroupId']
    sg_name = grupos[0]['GroupName']
    print(f"🛡️ Grupo de seguridad detectado: {sg_name} ({sg_id})")

    # 2. Intentar abrir el puerto 22
    try:
        print("🔓 Intentando abrir puerto 22 (SSH)...")
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}] # 0.0.0.0/0 significa "Todo internet"
            }]
        )
        print("✅ ¡HECHO! Puerto 22 abierto para todo el mundo.")
        
    except Exception as e:
        if "Duplicate" in str(e):
            print("⚠️ El puerto 22 ya estaba abierto. El problema podría ser tu red local (Eduroam).")
        else:
            print(f"❌ Error abriendo puerto: {e}")

except Exception as e:
    print(f"❌ No encuentro la máquina: {e}")
