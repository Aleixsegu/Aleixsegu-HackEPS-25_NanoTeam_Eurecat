import paramiko
import time
import os
import socket

# Rutas de claves
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
AWS_KEY_PATH = os.path.join(ROOT_DIR, "aws", "HackEPS-Key.pem")
GCP_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa") 

# Configuración del Stack
DUMMY_STACK_YAML = """
version: "3.9"
services:
  dummy-app-controller:
    image: rsprat/dummy-rest-app-controller:v1
    ports: ["30008:8000"]
    environment: {report_metrics_to_ems: "False"}
    networks: [hybrid-net]
    deploy:
      replicas: 1
      placement: {constraints: [node.role == manager]}
  dummy-app-worker:
    image: rsprat/dummy-rest-app-worker:v1
    environment: {API_ADDRESS: "http://dummy-app-controller:8000"}
    networks: [hybrid-net]
    depends_on: [dummy-app-controller]
    deploy:
      replicas: 4
      restart_policy: {condition: on-failure}
networks:
  hybrid-net:
    driver: overlay
"""

def ssh_exec(ip, user, key_path, command):
    print(f"   [DEBUG] Conectando a {ip} ({user})...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Intentamos 2 veces máximo con timeout corto para no bloquear la web
    for i in range(2):
        try:
            # Timeout de conexión: 5 segundos (Si no conecta en 5s, falla)
            client.connect(ip, username=user, key_filename=key_path, timeout=5, banner_timeout=5)
            
            # Ejecutar comando con timeout de ejecución (15s)
            stdin, stdout, stderr = client.exec_command(command, timeout=15)
            
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            client.close()
            
            # Ignorar warnings típicos de Linux que no son errores reales
            if err and "warning" not in err.lower() and "sudo" not in err.lower(): 
                print(f"   [STDERR] {err}")
                return f"LOG: {out} | STDERR: {err}"
            
            return out

        except socket.timeout:
            print(f"   [TIMEOUT] Intento {i+1} fallido en {ip}")
        except paramiko.AuthenticationException:
            return f"ERROR: Fallo de Autenticación (Clave rechazada)"
        except Exception as e:
            print(f"   [ERROR] {e}")
            time.sleep(1)
            
    return "ERROR: No se pudo conectar tras varios intentos"

def setup_cluster(master_info, workers_info):
    log = []
    
    # 1. INICIAR MASTER
    log.append(f"👑 Configurando Master en {master_info['ip']}...")
    
    # Forzamos 'leave' por si ya estaba iniciado y luego 'init'
    cmd_init = f"sudo docker swarm leave --force; sudo docker swarm init --advertise-addr {master_info['ip']} || sudo docker swarm join-token worker"
    
    res_master = ssh_exec(master_info['ip'], master_info['user'], GCP_KEY_PATH, cmd_init)
    
    if "ERROR" in res_master:
        log.append(f"❌ Error crítico conectando al Master: {res_master}")
        return log

    import re
    # Buscamos el token en la respuesta del comando
    match = re.search(r'docker swarm join --token \S+ \S+:\d+', res_master)
    
    if match:
        join_cmd = match.group(0)
        log.append("✅ Master inicializado. Token capturado.")
    else:
        log.append(f"❌ No se pudo obtener el token. Output Master:\n{res_master}")
        return log

    # 2. UNIR WORKERS
    for worker in workers_info:
        log.append(f"👷 Uniendo Worker {worker['name']} ({worker['provider']})...")
        
        if worker['provider'] == 'AWS':
            key = AWS_KEY_PATH
            user = "ubuntu"
        else:
            key = GCP_KEY_PATH
            user = master_info['user']
        
        # Comando join
        full_join = f"sudo docker swarm leave --force; sudo {join_cmd}"
        res = ssh_exec(worker['ip'], user, key, full_join)
        
        if "joined" in res: 
            log.append(f"   ✅ {worker['name']} unido correctamente.")
        elif "ERROR" in res:
            log.append(f"   ❌ Error conectando a {worker['name']}: {res}")
        else:
            log.append(f"   ℹ️ Respuesta {worker['name']}: {res}")
    
    log.append("\n✨ CLUSTER LISTO.")
    return log

def deploy_stack(master_info):
    log = []
    log.append(f"🚀 Conectando al Master para desplegar...")
    
    # Crear el archivo YAML
    cmd_write = f"cat <<EOF > dummy-stack.yml\n{DUMMY_STACK_YAML}\nEOF"
    ssh_exec(master_info['ip'], master_info['user'], GCP_KEY_PATH, cmd_write)
    
    # Desplegar
    cmd_deploy = "sudo docker stack deploy -c dummy-stack.yml demo"
    res = ssh_exec(master_info['ip'], master_info['user'], GCP_KEY_PATH, cmd_deploy)
    
    log.append(f"Respuesta:\n{res}")
    log.append(f"\n🌐 APP DISPONIBLE EN:\nhttp://{master_info['ip']}:30008")
    return log