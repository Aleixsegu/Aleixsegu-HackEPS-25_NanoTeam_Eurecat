import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError

DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(DIRECTORIO_ACTUAL, ".env"))

AWS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION = os.getenv("AWS_REGION", "us-west-2")

try:
    ec2_resource = boto3.resource('ec2', region_name=REGION, aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
    ec2_client = boto3.client('ec2', region_name=REGION, aws_access_key_id=AWS_KEY, aws_secret_access_key=AWS_SECRET)
except: pass

def buscar_ami_por_os(so):
    filtros = [{'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']}]
    try:
        images = ec2_client.describe_images(Filters=filtros, Owners=['099720109477'])
        return sorted(images['Images'], key=lambda x: x['CreationDate'], reverse=True)[0]['ImageId']
    except: return "ami-052efd3df9dad4825"

def gestionar_security_group():
    nombre_grupo = "HackEPS-Final-SG" # Nombre nuevo para forzar creación
    try: return ec2_client.describe_security_groups(GroupNames=[nombre_grupo])['SecurityGroups'][0]['GroupId']
    except ClientError:
        sg = ec2_resource.create_security_group(GroupName=nombre_grupo, Description="Swarm + App")
        puertos = [(22,'tcp'), (80,'tcp'), (2377,'tcp'), (7946,'tcp'), (7946,'udp'), (4789,'udp'), (30008,'tcp')]
        for p, pro in puertos:
            sg.authorize_ingress(IpPermissions=[{'IpProtocol': pro, 'FromPort': p, 'ToPort': p, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}])
        return sg.id

def crear_maquina_web(nombre, tipo, so, cluster_id="default"):
    print(f"🔥 AWS: Creando {nombre}...")
    ami = buscar_ami_por_os(so)
    sg = gestionar_security_group()
    
    user_data = """#!/bin/bash
    apt-get update
    apt-get install -y docker.io ufw
    systemctl start docker
    systemctl enable docker
    ufw allow 22/tcp
    ufw allow 30008/tcp
    ufw allow 2377/tcp
    ufw allow 7946/tcp
    ufw allow 7946/udp
    ufw allow 4789/udp
    echo "y" | ufw enable
    """
    
    ins = ec2_resource.create_instances(
        ImageId=ami, MinCount=1, MaxCount=1, InstanceType=tipo,
        KeyName="HackEPS-Key", SecurityGroupIds=[sg],
        UserData=user_data,
        TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key':'Name','Value':nombre}, {'Key':'ClusterId', 'Value': cluster_id}]}]
    )[0]
    ins.wait_until_running()
    ins.reload()
    return {"ip": ins.public_ip_address, "id": ins.id}

def borrar_maquina(instance_id):
    print(f"🗑️ AWS: Eliminando instancia {instance_id}...")
    ec2_resource.instances.filter(InstanceIds=[instance_id]).terminate()
    return "Terminated"