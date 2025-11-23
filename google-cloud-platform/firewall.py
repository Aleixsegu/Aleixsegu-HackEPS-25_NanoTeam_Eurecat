import os
from google.cloud import compute_v1
from google.oauth2 import service_account

# Configuración
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(SCRIPT_DIR, "hackeps2025-team4-adrian.json")
PROJECT_ID = "hackeps2025-team4"
FIREWALL_RULE_NAME = "allow-hackeps-swarm-30008"

def ensure_firewall_open():
    print(f"[GCP FIREWALL] Verificando reglas externas...")
    try:
        credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
        client = compute_v1.FirewallsClient(credentials=credentials)

        # Intentar crear la regla directamente
        try:
            firewall_rule = compute_v1.Firewall()
            firewall_rule.name = FIREWALL_RULE_NAME
            firewall_rule.network = "global/networks/default"
            firewall_rule.source_ranges = ["0.0.0.0/0"]
            
            allowed_tcp = compute_v1.Allowed()
            allowed_tcp.I_p_protocol = "tcp"
            # AÑADIMOS TODOS LOS PUERTOS IMPORTANTES
            allowed_tcp.ports = ["22", "80", "2377", "7946", "30008"]

            allowed_udp = compute_v1.Allowed()
            allowed_udp.I_p_protocol = "udp"
            allowed_udp.ports = ["7946", "4789"]

            firewall_rule.allowed = [allowed_tcp, allowed_udp]

            operation = client.insert(project=PROJECT_ID, firewall_resource=firewall_rule)
            print(f"[GCP FIREWALL] ⏳ Creando regla global...")
            
            op_client = compute_v1.GlobalOperationsClient(credentials=credentials)
            op_client.wait(project=PROJECT_ID, operation=operation.name)
            print(f"[GCP FIREWALL] ✅ Regla creada. Puerto 30008 abierto al mundo.")
            
        except Exception as e:
            if "already exists" in str(e):
                print(f"[GCP FIREWALL] ✅ La regla ya existe. Todo OK.")
            else:
                print(f"[GCP FIREWALL] ❌ Error: {e}")

    except Exception as e:
        print(f"[GCP FIREWALL] ❌ Error credenciales: {e}")

if __name__ == "__main__":
    ensure_firewall_open()