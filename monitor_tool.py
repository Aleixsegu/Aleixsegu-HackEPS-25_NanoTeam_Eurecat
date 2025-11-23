import paramiko
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
AWS_KEY_PATH = os.path.join(ROOT_DIR, "aws", "HackEPS-Key.pem")
GCP_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")

def get_remote_metrics(ip, user, provider):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = AWS_KEY_PATH if provider == 'AWS' else GCP_KEY_PATH
    
    try:
        client.connect(ip, username=user, key_filename=key_path, timeout=4)
        
        # Comandos ligeros para extraer datos limpios
        cmd_cpu = "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}'"
        cmd_ram = "free -m | grep Mem | awk '{print $3/$2 * 100.0}'"
        cmd_disk = "df -h / | awk 'NR==2 {print $5}' | tr -d '%'"
        
        stdin, stdout, stderr = client.exec_command(f"{cmd_cpu}; {cmd_ram}; {cmd_disk}")
        output = stdout.read().decode().strip().split('\n')
        client.close()
        
        if len(output) >= 3:
            return {
                "cpu": round(float(output[0]), 1),
                "ram": round(float(output[1]), 1),
                "disk": float(output[2]),
                "status": "success"
            }
        return {"error": "Datos incompletos", "status": "error"}
    except Exception as e:
        return {"error": str(e), "status": "error"}