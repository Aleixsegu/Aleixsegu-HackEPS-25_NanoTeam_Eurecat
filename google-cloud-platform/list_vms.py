import json
import sys
import os
from google.cloud import compute_v1
from google.oauth2 import service_account

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(SCRIPT_DIR, "hackeps2025-team4-adrian.json")
PROJECT_ID = "hackeps2025-team4"

def list_instances_json():
    vms = []
    try:
        if not os.path.exists(KEY_PATH): return
        credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
        client = compute_v1.InstancesClient(credentials=credentials)
        request = compute_v1.AggregatedListInstancesRequest(project=PROJECT_ID)

        for zone, response in client.aggregated_list(request=request):
            if response.instances:
                for instance in response.instances:
                    internal = instance.network_interfaces[0].network_i_p
                    external = "Pendiente..."
                    if instance.network_interfaces[0].access_configs:
                        external = instance.network_interfaces[0].access_configs[0].nat_i_p
                    
                    cid = "sin-grupo"
                    if instance.metadata.items:
                        for i in instance.metadata.items:
                            if i.key == 'cluster-id': cid = i.value

                    vms.append({
                        "name": instance.name, "zone": zone.split('/')[-1], "status": instance.status,
                        "internal_ip": internal, "external_ip": external,
                        "machine_type": instance.machine_type.split('/')[-1], "provider": "GCP",
                        "cluster_id": cid
                    })
        print(json.dumps(vms))
    except Exception as e: print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    list_instances_json()