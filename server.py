import sys
import os
import json
import subprocess
import re
from flask import Flask, request, send_from_directory

# --- CONFIGURACIÓN ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
AWS_DIR = os.path.join(ROOT_DIR, "aws")
GCP_DIR = os.path.join(ROOT_DIR, "google-cloud-platform")

sys.path.append(AWS_DIR)

try: import backend_aws
except: backend_aws = None
try: import swarm_tool
except: swarm_tool = None
try: import monitor_tool
except: monitor_tool = None

app = Flask(__name__, static_folder=".")

@app.get("/")
def root(): return send_from_directory(".", "index.html")

@app.get("/styles/<path:filename>")
def serve_styles(filename): return send_from_directory("styles", filename)

# --- 1. CREAR CLUSTER COMPLETO ---
@app.post("/create-vm")
def create_vm():
    data = request.json
    raw_name = data.get('vm_name', 'node')
    cluster_id = re.sub(r'[^a-z0-9-]', '', raw_name.lower()) or "cluster-default"
    try: cluster_size = int(data.get('cluster_size', 2))
    except: cluster_size = 2
    vm_type_gcp = data.get('machine_type', 'e2-medium')
    disk_size = str(data.get('disk_size', '10'))
    
    aws_type_map = {"e2-micro": "t2.micro", "e2-small": "t2.small", "e2-medium": "t2.medium", "e2-standard-2": "t3.large"}
    vm_type_aws = aws_type_map.get(vm_type_gcp, "t2.micro")

    log_output = f"🚀 Creando Cluster ID: '{cluster_id}' ({cluster_size} nodos)...\n"

    for i in range(cluster_size):
        is_gcp = (i % 2 == 0)
        current_name = f"{cluster_id}-{i+1}" # Nombre secuencial simple
        
        if is_gcp:
            log_output += f"\n[GCP] Lanzando {current_name}..."
            inputs = f"{current_name}\nus-central1-a\n{vm_type_gcp}\n{disk_size}\n{cluster_id}\n"
            try:
                proc = subprocess.run([sys.executable, os.path.join(GCP_DIR, "deploy_vm.py")], input=inputs, text=True, capture_output=True, encoding='utf-8')
                log_output += f"\n{proc.stdout}" if proc.returncode == 0 else f"\n[GCP ERROR] {proc.stderr}"
            except Exception as e: log_output += f"\n[GCP CRITICAL] {e}"
        else:
            if backend_aws:
                log_output += f"\n[AWS] Lanzando {current_name}..."
                try:
                    res = backend_aws.crear_maquina_web(current_name, vm_type_aws, "Ubuntu", cluster_id)
                    log_output += f"\n[AWS] ✅ OK. IP: {res['ip']}"
                except Exception as e: log_output += f"\n[AWS ERROR] {e}"
            else: log_output += f"\n[AWS] ❌ Módulo no cargado."

    return log_output

# --- NUEVO: ESCALAR CLUSTER (AÑADIR 1 NODO) ---
@app.post("/scale-cluster")
def scale_cluster():
    data = request.json
    vm_name = data.get('name')
    provider = data.get('provider')
    cluster_id = data.get('cluster_id')
    
    # Configuración estándar
    vm_type_gcp = "e2-medium"
    vm_type_aws = "t2.medium"
    disk_size = "15"

    log = f"📈 Escalando {cluster_id}: Añadiendo {vm_name} en {provider}...\n"

    if provider == "GCP":
        inputs = f"{vm_name}\nus-central1-a\n{vm_type_gcp}\n{disk_size}\n{cluster_id}\n"
        try:
            proc = subprocess.run([sys.executable, os.path.join(GCP_DIR, "deploy_vm.py")], input=inputs, text=True, capture_output=True, encoding='utf-8')
            log += f"\n{proc.stdout}" if proc.returncode == 0 else f"\n[GCP ERROR] {proc.stderr}"
        except Exception as e: log += f"\n[GCP ERROR] {e}"
        
    elif provider == "AWS":
        if backend_aws:
            try:
                res = backend_aws.crear_maquina_web(vm_name, vm_type_aws, "Ubuntu", cluster_id)
                log += f"\n[AWS] ✅ Creada correctamente. IP: {res['ip']}"
            except Exception as e: log += f"\n[AWS ERROR] {e}"
        else: log += "\n[AWS] Módulo no disponible."
        
    return log

# --- 2. LISTAR ---
@app.get("/list-vms")
def list_vms():
    all_vms = []
    # GCP
    try:
        proc = subprocess.run([sys.executable, os.path.join(GCP_DIR, "list_vms.py")], capture_output=True, text=True, encoding='utf-8')
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                gcp_data = json.loads(proc.stdout)
                if isinstance(gcp_data, list):
                    for vm in gcp_data: vm['provider'] = 'GCP'
                    all_vms.extend(gcp_data)
            except: pass
    except: pass
    # AWS
    try:
        if backend_aws and backend_aws.ec2_client:
            resp = backend_aws.ec2_client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'pending']}])
            for r in resp['Reservations']:
                for ins in r['Instances']:
                    name = "AWS-Node"
                    c_id = "sin-grupo"
                    if 'Tags' in ins:
                        for t in ins['Tags']:
                            if t['Key'] == 'Name': name = t['Value']
                            if t['Key'] == 'ClusterId': c_id = t['Value']
                    
                    # Fallback nombre
                    if c_id == "sin-grupo":
                        if "-master" in name: c_id = name.split("-master")[0]
                        elif "-worker" in name: c_id = name.split("-worker")[0]
                        else: c_id = name.split("-")[0] if "-" in name else "Otros"

                    all_vms.append({
                        "name": name, "provider": "AWS", "zone": ins['Placement']['AvailabilityZone'],
                        "status": ins['State']['Name'].upper(), "external_ip": ins.get('PublicIpAddress', 'Pendiente'),
                        "internal_ip": ins.get('PrivateIpAddress', 'N/A'), "machine_type": ins['InstanceType'],
                        "cluster_id": c_id, "id": ins['InstanceId']
                    })
    except: pass
    return json.dumps(all_vms)

# --- 3. SSH ---
@app.post("/get-ssh")
def get_ssh():
    data = request.json
    if data.get("provider") == "AWS":
        return f"ssh -i aws/HackEPS-Key.pem ubuntu@{data.get('external_ip')}"
    
    proc = subprocess.run([sys.executable, os.path.join(GCP_DIR, "ssh.py"), data['vm_name'], data['zone'], data['user']], capture_output=True, text=True, encoding='utf-8')
    target = data.get('external_ip')
    if not target or target.startswith("Pendiente"): target = data['vm_name']
    return proc.stdout + f"\n\nssh {data['user']}@{target}"

# --- 4. SWARM & APP ---
@app.post("/setup-swarm")
def setup_swarm():
    if not swarm_tool: return "❌ Swarm tool missing."
    data = request.json
    vms, user = data.get('vms', []), data.get('user', 'adrian')
    master = next((v for v in vms if "master" in v['name']), None)
    if not master: master = next((v for v in vms if v['provider'] == 'GCP'), None)
    if not master or not master['external_ip'] or master['external_ip'].startswith("Pendiente"): return "❌ Master sin IP."
    master_info = {'name': master['name'], 'ip': master['external_ip'], 'user': user, 'provider': master['provider']}
    workers = [{'name': v['name'], 'ip': v['external_ip'], 'provider': v['provider']} for v in vms if v['name'] != master['name'] and v['external_ip']]
    return "\n".join(swarm_tool.setup_cluster(master_info, workers))

@app.post("/deploy-app")
def deploy_app():
    if not swarm_tool: return "❌ Swarm tool missing."
    data = request.json
    vms, user = data.get('vms', []), data.get('user', 'adrian')
    master = next((v for v in vms if "master" in v['name']), None)
    if not master: master = next((v for v in vms if v['provider'] == 'GCP'), None)
    return "\n".join(swarm_tool.deploy_stack({'name': master['name'], 'ip': master['external_ip'], 'user': user}))

# --- BORRAR & MONITOR ---
@app.post("/delete-vm")
def delete_vm():
    data = request.json
    prov = data.get('provider')
    if prov == "GCP":
        try:
            subprocess.Popen([sys.executable, os.path.join(GCP_DIR, "delete_vm.py"), data['name'], data['zone']])
            return "Eliminando en GCP..."
        except Exception as e: return str(e)
    elif prov == "AWS":
        if backend_aws:
            backend_aws.borrar_maquina(data['id'])
            return "Eliminando en AWS..."
    return "Error provider"

@app.post("/monitor-nodes")
def monitor_nodes():
    if not monitor_tool: return json.dumps({"error": "No monitor tool"})
    data = request.json
    results = {}
    for vm in data.get('vms', []):
        if not vm.get('external_ip') or vm['external_ip'].startswith("Pend"): continue
        user = "ubuntu" if vm['provider'] == "AWS" else data.get('user', 'adrian')
        results[vm['name']] = monitor_tool.get_remote_metrics(vm['external_ip'], user, vm['provider'])
    return json.dumps(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)