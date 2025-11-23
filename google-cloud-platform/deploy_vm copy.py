import os
import sys
from google.cloud import compute_v1
from google.oauth2 import service_account

# Configuración
KEY_FILENAME = "hackeps2025-team4-adrian.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(SCRIPT_DIR, KEY_FILENAME)
NETWORK_INTERFACE_URL = "global/networks/default"
SOURCE_IMAGE_URL = "projects/debian-cloud/global/images/debian-11-bullseye-v20230509"
SSH_PUB_PATH = os.path.expanduser("~/.ssh/id_rsa.pub")

def get_vm_data_terminal():
    try:
        vm_name = input().strip()
        zone = input().strip()
        machine_type_input = input().strip()
        disk_size_input = input().strip()
        cluster_id = input().strip()
        
        if not vm_name: raise ValueError("Nombre vacío")
        
        try: disk_size_gb = int(disk_size_input)
        except: disk_size_gb = 10
        
        return vm_name, zone, f"zones/{zone}/machineTypes/{machine_type_input}", disk_size_gb, cluster_id

    except Exception as e:
        print(f"[CRITICAL ERROR] Input error: {e}")
        return None

def deploy_vm_instance_with_sa_key(vm_name, zone, machine_type_url, disk_size_gb, cluster_id, project_id, credentials):
    client = compute_v1.InstancesClient(credentials=credentials)

    # 1. Clave SSH
    ssh_keys_value = ""
    if os.path.exists(SSH_PUB_PATH):
        try:
            with open(SSH_PUB_PATH, 'r') as f: pub_key = f.read().strip()
            ssh_keys_value = f"adrian:{pub_key}"
            print(f"[INFO] Clave SSH leída.")
        except: pass
    
    # 2. SCRIPT DE ARRANQUE (CON PUERTO 30008)
    startup = """#!/bin/bash
    # Instalar Docker
    apt-get update
    apt-get install -y docker.io ufw
    systemctl start docker
    systemctl enable docker
    
    # CONFIGURACIÓN FIREWALL
    ufw allow 22/tcp       # SSH
    ufw allow 2377/tcp     # Swarm
    ufw allow 7946/tcp     # Swarm
    ufw allow 7946/udp     # Swarm
    ufw allow 4789/udp     # Swarm
    
    # >>> PUERTO DUMMY APP <<<
    ufw allow 30008/tcp    
    
    # Activar
    echo "y" | ufw enable
    """
    
    metadata_items = [
        {"key": "startup-script", "value": startup},
        {"key": "real-provider", "value": "GCP"},
        {"key": "cluster-id", "value": cluster_id}
    ]
    if ssh_keys_value: metadata_items.append({"key": "ssh-keys", "value": ssh_keys_value})

    metadata = compute_v1.Metadata(items=metadata_items)

    disk_config = compute_v1.AttachedDisk(
        auto_delete=True, boot=True,
        initialize_params=compute_v1.AttachedDiskInitializeParams(source_image=SOURCE_IMAGE_URL, disk_size_gb=disk_size_gb)
    )
    network_config = compute_v1.NetworkInterface(
        name="nic0", network=NETWORK_INTERFACE_URL,
        access_configs=[compute_v1.AccessConfig(name="External NAT", type_="ONE_TO_ONE_NAT")]
    )
    instance_resource = compute_v1.Instance(
        name=vm_name, machine_type=machine_type_url,
        disks=[disk_config], network_interfaces=[network_config], metadata=metadata
    )

    print(f"[INFO] GCP: Creando {vm_name}...")
    req = compute_v1.InsertInstanceRequest(project=project_id, zone=zone, instance_resource=instance_resource)
    op = client.insert(request=req)
    op_client = compute_v1.ZoneOperationsClient(credentials=credentials)
    op_client.wait(project=project_id, zone=zone, operation=op.name)
    print(f"[OK] GCP: {vm_name} lista.")

if __name__ == "__main__":
    try:
        creds = service_account.Credentials.from_service_account_file(KEY_PATH)
        data = get_vm_data_terminal()
        if data: deploy_vm_instance_with_sa_key(*data, creds.project_id, creds)
        else: sys.exit(1)
    except Exception as e: 
        print(f"[ERROR GLOBAL] {e}")
        sys.exit(1)