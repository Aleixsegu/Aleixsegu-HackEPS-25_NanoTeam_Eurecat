import boto3
import os
from dotenv import load_dotenv

# 1. CARGAR LAS CLAVES DEL ARCHIVO .env
# Esto es obligatorio. Si no lo pones, boto3 no encuentra nada.
print("📂 Cargando archivo .env...")
load_dotenv()

# Verificación rápida (opcional, para depurar)
if not os.getenv("AWS_ACCESS_KEY_ID"):
    print("❌ ERROR: No encuentro las claves en el entorno. Revisa tu archivo .env")
    exit()

# 2. Configurar la región (Irlanda por defecto)
REGION = os.getenv('AWS_REGION', 'eu-west-2')

print(f"🔄 Conectando con AWS en {REGION}...")

try:
    # 3. Crear el cliente EC2
    ec2 = boto3.client('ec2', region_name=REGION)

    # 4. Probar la conexión preguntando "¿Quién soy?"
    sts = boto3.client('sts', region_name=REGION)
    user_id = sts.get_caller_identity()
    print(f"✅ ¡CONEXIÓN EXITOSA! Identificado como: {user_id['UserId']}")

    # AQUÍ IRÁ EL CÓDIGO PARA CREAR LA MÁQUINA LUEGO
    # Por ahora solo listamos para asegurar que funciona
    response = ec2.describe_instances()
    print("📋 Conexión verificada. Listo para crear máquinas.")

except Exception as e:
    print("\n❌ FALLÓ LA CONEXIÓN:")
    print(e)
    print("\n💡 PISTA: Asegúrate de que el archivo .env está en la misma carpeta que este script.")
