import streamlit as st
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import os
import io
import streamlit.components.v1 as components
import base64

# Configuración visual de la app móvil
st.set_page_config(page_title="Mi Libreta Inteligente", page_icon="📝", layout="centered")

# --- COMPONENTE DE CÁMARA ULTRA RÁPIDA (JAVASCRIPT) ---
def camara_ultra_rapida_js():
    html_code = """
    <div style="text-align: center;">
        <video id="webcam" autoplay playsinline width="100%" style="border-radius: 10px; max-width: 500px; background-color: #000;"></video>
        <br><br>
        <button id="snap" style="
            background-color: #FF4B4B; color: white; border: none; 
            padding: 14px 28px; font-size: 16px; border-radius: 8px; 
            cursor: pointer; font-weight: bold; width: 85%; max-width: 300px;
            box-shadow: 0px 4px 6px rgba(0,0,0,0.2);
        ">📷 Capturar Hoja al Instante</button>
        <canvas id="canvas" style="display:none;"></canvas>
    </div>
    <script>
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('canvas');
        const snap = document.getElementById('snap');
        const ctx = canvas.getContext('2d');

        // Acceder a la cámara trasera directamente en Full HD de manera local
        navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } }, 
            audio: false 
        })
        .then(stream => { video.srcObject = stream; })
        .catch(err => { alert("No se pudo acceder a la cámara trasera. Asegúrate de dar los permisos."); });

        // Captura inmediata al pulsar el botón
        snap.addEventListener('click', () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.90);
            Streamlit.setComponentValue(dataUrl);
        });
    </script>
    """
    return components.html(html_code, height=480)

# --- CONEXIÓN A DRIVE ---
def conectar_drive():
    info_claves = st.secrets["gcp_service_account"]
    credenciales = service_account.Credentials.from_service_account_info(info_claves)
    return build('drive', 'v3', credentials=credenciales)

def subir_a_drive(bytes_image, nombre_archivo, folder_id, creadenciales_dict):
    try:
        creds = service_account.Credentials.from_service_account_info(creadenciales_dict)
        service = build('drive', 'v3', credentials=creds)
        
        # Preparar el archivo desde memoria RAM
        media = MediaIoBaseUpload(io.BytesIO(bytes_image), mimetype='image/jpeg', resumable=True)
        
        file_metadata = {
            'name': nombre_archivo,
            'parents': [folder_id]
        }
        
        # Sube vinculando la propiedad del almacenamiento al dueño de la carpeta destino
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True  # Soluciona la cuota de las cuentas de servicio
        ).execute()
        
        return file.get('id')
        
    except Exception as e:
        st.error(f"Error al subir a Google Drive: {e}")
        return None

# --- INTERFAZ GRÁFICA MÓVIL ---
st.title("📝 Mi Libreta Inteligente")

if "modo_escaneo" not in st.session_state:
    st.session_state.modo_escaneo = False

# PANTALLA A: Menú de Inicio Principal
if not st.session_state.modo_escaneo:
    st.write("¡Bienvenido, Carlos! Organiza tus apuntes de la universidad al instante.")
    st.write("")
    if st.button("🚀 EMPEZAR A ESCANEAR APUNTES", use_container_width=True):
        st.session_state.modo_escaneo = True
        st.rerun()
        
    st.info("💡 Consejo: Al presionar el botón, la cámara se abrirá al instante gracias a la optimización local.")

# PANTALLA B: Modo Cámara Activo (Sin Lag)
else:
    st.subheader("📷 Escáner Activo")
    
    if st.button("⬅️ Volver al Inicio"):
        st.session_state.modo_escaneo = False
        st.rerun()

    # Desplegar el visor de cámara de alta velocidad
    data_url = camara_ultra_rapida_js()

    # 🟢 CONTROL CLAVE: Solo procesamos si el usuario YA capturó la foto y data_url tiene texto válido
    if data_url and isinstance(data_url, str) and ";base64," in data_url:
        st.info("Procesando imagen con filtro avanzado...")
        
        try:
            # Decodificar el String Base64 que viene de JavaScript a bytes puros de imagen
            format, imgstr = data_url.split(';base64,')
            bytes_data = base64.b64decode(imgstr)
            
            img_array = np.frombuffer(bytes_data, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            # Escaneo de QR
            codigos_qr = decode(img)
            if codigos_qr:
                nombre_base = codigos_qr[0].data.decode('utf-8')
                st.success(f"🔗 Código QR detectado: **{nombre_base}**")
            else:
                nombre_base = "APUNTE_MANUAL"
                st.warning("⚠️ No se detectó código QR. Se guardará como 'APUNTE_MANUAL'.")

            # Filtro de Limpieza Avanzado (Filtro Mágico)
            canales = cv2.split(img)
            canales_limpios = []
            kernel_fondo = cv2.getStructuringElement(cv2.MORPH_RECT, (51, 51))
            for canal in canales:
                background = cv2.morphologyEx(canal, cv2.MORPH_CLOSE, kernel_fondo)
                background = cv2.GaussianBlur(background, (3, 3), 0)
                canal_normalizado = cv2.divide(canal, background, scale=255)
                _, canal_limpio = cv2.threshold(canal_normalizado, 240, 255, cv2.THRESH_TRUNC)
                canal_final = cv2.normalize(canal_limpio, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
                canales_limpios.append(canal_final)
                
            img_final_color = cv2.merge(canales_limpios)

            # Mostrar el resultado final en la app
            st.image(img_final_color, caption="Vista previa del escaneo limpio", use_container_width=True)

            # Convertir la imagen limpia de OpenCV de vuelta a bytes (JPEG) para enviarla a Drive
            _, buffer_limpio = cv2.imencode('.jpg', img_final_color)
            bytes_limpios = buffer_limpio.tobytes()

            # Configurar la subida usando los Secrets guardados en Streamlit
            nombre_archivo_drive = f"{nombre_base}_Limpio.jpg"
            folder_id = st.secrets["gcp_service_account"]["folder_id"] if "folder_id" in st.secrets["gcp_service_account"] else "CAMBIA_POR_EL_ID_DE_TU_CARPETA"
            creadenciales_dict = st.secrets["gcp_service_account"]

            st.write("Subiendo a tu Google Drive...")
            id_drive = subir_a_drive(bytes_limpios, nombre_archivo_drive, folder_id, creadenciales_dict)
            
            if id_drive:
                st.balloons()
                st.success(f"🎉 ¡Guardado en Drive perfectamente!")
                st.session_state.modo_escaneo = False
                st.write("Volviendo al menú principal...")
                st.button("Ok", on_click=st.rerun)
                
        except Exception as error_procesamiento:
            st.error(f"Error al procesar la captura: {error_procesamiento}")
