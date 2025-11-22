import streamlit as st
# Importamos los DOS cocineros
import backend_aws as aws_motor
import backend_gcp as gcp_motor 

st.set_page_config(page_title="NebulOuS", page_icon="☁️", layout="wide")

st.title("☁️ NebulOuS Platform")
st.markdown("### Orquestador Híbrido Multi-Cloud")

# --- MENU SUPERIOR DE PROVEEDOR ---
proveedor = st.radio("Elige tu Nube:", ["🟢 Amazon Web Services (AWS)", "🔵 Google Cloud Platform (GCP)"], horizontal=True)

col1, col2 = st.columns([1, 2])

# ==========================================
# LÓGICA PARA AWS
# ==========================================
if "AWS" in proveedor:
    with col1:
        with st.form("form_aws"):
            st.subheader("Amazon Config")
            nombre = st.text_input("Nombre Servidor", "AWS-Worker-01")
            os_aws = st.selectbox("Sistema Operativo", ["Ubuntu 22.04 LTS", "Amazon Linux 2023", "Windows Server 2022"])
            
            # Carga dinámica AWS
            with st.spinner("Cargando catálogo AWS..."):
                tipos_aws = aws_motor.obtener_tipos_instancia()
            tipo_aws = st.selectbox("Potencia", tipos_aws).split(" ")[0]
            
            enviar_aws = st.form_submit_button("🔥 LANZAR EN AWS", use_container_width=True)

    with col2:
        if enviar_aws:
            st.info(f"🚀 Desplegando en Oregón (us-west-2)...")
            try:
                datos = aws_motor.crear_maquina_web(nombre, tipo_aws, os_aws)
                st.balloons()
                st.success("✅ AWS Deploy Éxito")
                
                c1, c2 = st.columns(2)
                c1.metric("IP Pública", datos['ip'])
                c2.metric("ID", datos['id'])
                
                # Comando SSH
                user = "ubuntu" if "Ubuntu" in os_aws else "ec2-user"
                if "Windows" in os_aws: user = "Administrator"
                
                st.code(f"ssh -o StrictHostKeyChecking=no -i \"{datos['key_path']}\" {user}@{datos['ip']}", language="bash")
                
            except Exception as e:
                st.error(f"Error AWS: {e}")

# ==========================================
# LÓGICA PARA GOOGLE CLOUD
# ==========================================
elif "Google" in proveedor:
    with col1:
        with st.form("form_gcp"):
            st.subheader("Google Config")
            nombre_gcp = st.text_input("Nombre VM", "gcp-worker-01")
            zona_gcp = st.selectbox("Zona", ["us-central1-a", "europe-west1-b", "europe-west4-a"])
            os_gcp = st.selectbox("Imagen", ["Ubuntu 22.04", "Debian 11"])
            tipo_gcp = st.selectbox("Tipo Máquina", ["e2-micro", "e2-small", "e2-medium"])
            
            enviar_gcp = st.form_submit_button("🔥 LANZAR EN GOOGLE", use_container_width=True)

    with col2:
        if enviar_gcp:
            st.info(f"🚀 Desplegando en {zona_gcp}...")
            barra = st.progress(0)
            try:
                # LLAMADA A TU NUEVO SCRIPT GCP
                datos = gcp_motor.crear_maquina_gcp(nombre_gcp, zona_gcp, tipo_gcp, os_gcp)
                barra.progress(100)
                st.balloons()
                st.success("✅ GCP Deploy Éxito")
                
                c1, c2 = st.columns(2)
                c1.metric("IP Pública", datos['ip'])
                c2.metric("ID", datos['id'])
                
                st.info("🔑 Conectando con usuario 'hackeps'")
                st.code(f"ssh -o StrictHostKeyChecking=no -i \"{datos['key_path']}\" {datos['user']}@{datos['ip']}", language="bash")
                
            except Exception as e:
                st.error(f"Error Google: {e}")