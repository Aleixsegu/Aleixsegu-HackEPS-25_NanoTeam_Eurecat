import os
import sys
from google.cloud import compute_v1
from google.oauth2 import service_account
from google.cloud.compute_v1.services.zone_operations import ZoneOperationsClient

KEY_FILENAME = "hackeps2025-team4-adrian.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(SCRIPT_DIR, KEY_FILENAME)
SSH_PUBLIC_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa.pub")

def inject_public_key(vm_name, zone, username):
    print(f"[INFO] Conectando a GCP para VM: {vm_name}...")
    
    try:
        credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
        project_id = credentials.project_id

        if not os.path.exists(SSH_PUBLIC_KEY_PATH):
            print(f"[ERROR] No tienes clave publica en {SSH_PUBLIC_KEY_PATH}")
            return

        with open(SSH_PUBLIC_KEY_PATH, 'r') as f:
            public_key = f.read().strip()
        
        ssh_value = f"{username}:{public_key}"
        
        client = compute_v1.InstancesClient(credentials=credentials)
        instance = client.get(project=project_id, zone=zone, instance=vm_name)
        
        existing_keys = ""
        # Usamos getattr de forma segura para metadatos
        if instance.metadata and instance.metadata.items:
            for item in instance.metadata.items:
                if item.key == 'ssh-keys':
                    existing_keys = item.value
        
        if ssh_value in existing_keys:
            print("[OK] Tu clave ya esta autorizada en esta maquina.")
            return

        new_keys = existing_keys + f"\n{ssh_value}" if existing_keys else ssh_value
        
        metadata = compute_v1.Metadata()
        metadata.fingerprint = instance.metadata.fingerprint
        metadata.items = [{"key": "ssh-keys", "value": new_keys}]
        
        print("[WAIT] Inyectando clave SSH...")
        req = compute_v1.SetMetadataInstanceRequest(
            project=project_id, zone=zone, instance=vm_name, metadata_resource=metadata
        )
        
        op = client.set_metadata(request=req)
        op_client = ZoneOperationsClient(credentials=credentials)
        op_client.wait(operation=op.name, project=project_id, zone=zone)
        
        print("[OK] Clave inyectada con exito.")

    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == '__main__':
    if len(sys.argv) > 3:
        inject_public_key(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("Faltan argumentos: ssh.py <vm_name> <zone> <user>")