import os
import sys
from google.cloud import compute_v1
from google.oauth2 import service_account

KEY_FILENAME = "hackeps2025-team4-adrian.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(SCRIPT_DIR, KEY_FILENAME)

def delete_instance(vm_name, zone):
    try:
        credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
        client = compute_v1.InstancesClient(credentials=credentials)
        print(f"🗑️ Solicitando eliminación de '{vm_name}' en {zone}...")
        op = client.delete(project=credentials.project_id, zone=zone, instance=vm_name)
        compute_v1.ZoneOperationsClient(credentials=credentials).wait(project=credentials.project_id, zone=zone, operation=op.name)
        print(f"✅ Instancia '{vm_name}' eliminada.")
    except Exception as e:
        print(f"❌ Error eliminando instancia GCP: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 2: delete_instance(sys.argv[1], sys.argv[2])
    else: print("Uso: python delete_vm.py <vm_name> <zone>")