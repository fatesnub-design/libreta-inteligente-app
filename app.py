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

# --- COMPONENTE DE CÁMARA ULTRA RÁPIDA OPTIMIZADA ---
def camara_ultra_rapida_js():
    html_code = """
    <div style="text-align: center; font-family: sans-serif;">
        <button id="snap" style="
            background-color: #FF4B4B; color: white; border: none; 
            padding: 16px 30px; font-size: 18px; border-radius: 50px; 
            cursor: pointer; font-weight: bold; width: 90%; max-width: 340px;
            box-shadow: 0px 4px 10px rgba(255, 75, 75, 0.4);
            margin-bottom: 15px;
        ">📸 CAPTURAR HOJA AHORA</button>
        
        <div style="position: relative; width: 100%; max-width: 500px; margin: 0 auto;">
            <video id="webcam" autoplay playsinline muted width="100%" style="
                border-radius: 12px; 
                background-color: #111;
                box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
            "></video>
        </div>
        <canvas id="canvas" style="display:none;"></canvas>
    </div>
    
    <script>
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('canvas');
        const snap = document.getElementById('snap');
        const ctx = canvas.getContext('2d');

        // Configuración reforzada para asegurar que abra la cámara trasera en móviles
        const constraints = {
            video: { 
                facingMode: { ideal: "environment" }, 
                width: { ideal: 1280 }, 
                height: { ideal: 720 } 
            },
            audio: false
        };

        navigator.mediaDevices.getUserMedia(constraints)
        .then(stream => { 
            video.srcObject = stream;
            video.setAttribute("playsinline", true); // Vital para iOS Safari
            video.play();
        })
        .catch(err => { 
            alert("Error de cámara: Asegúrate de otorgar permisos de cámara y usar HTTPS."); 
        });

        // Captura inmediata al pulsar el botón de arriba
        snap.addEventListener('click', () => {
            if(video.videoWidth > 0) {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
                Streamlit.setComponentValue(dataUrl);
            } else {
                alert("La cámara aún está cargando. Intenta de nuevo en un segundo.");
            }
        });
    </script>
    """
    return components.html(html_code, height=540, scrolling=False)

# --- CONEXIÓN A DRIVE ---
def conectar_drive():
    info_claves = st.secrets["gcp_service_account"]
    credenciales = service_account.Credentials.from_service_account_info(info_claves)
    return build('drive', 'v3', credentials=credenciales)

def subir_a_drive(bytes_image, nombre_archivo, folder_id, creadenciales_dict):
    try:
        creds = service_account.Credentials.from_service_account_info(creadenciales_dict)
        service = build('drive', 'v3', credentials=creds)
        
        media = MediaIoBaseUpload(io.BytesIO(bytes_image), mimetype='image/jpeg', resumable=True)
        
        file_metadata = {
            'name': nombre_archivo,
            'parents': [folder_id]
        }
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        return file.get('id')
        
    except Exception as e:
        st.error(f"Error al subir a Google Drive: {e}")
        return None

# --- INTERFAZ GRÁFICA ---
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
        
    st.info("💡 Consejo: Pon la hoja en un lugar plano y bien iluminado antes de disparar.")

# PANTALLA B: Modo Cámara Activo (Sin Lag y Ajustado)
else:
    st.subheader("📷 Escáner Activo")
    
    if st.button("⬅️ Volver al Inicio"):
        st.session_state.modo_escaneo = False
        st.rerun()

    st.write("Apunta a la libreta y presiona el botón rojo superior:")
    
    # Desplegar el nuevo visor adaptado a teléfonos
    data_url = camara_ultra_rapida_js()

    # Procesar solo cuando data_url reciba la señal del botón
    if data_url and isinstance(data_url, str) and ";base64," in data_url:
        st.info("Procesando imagen con filtro avanzado...")
        
        try:
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

            # Filtro de Limpieza Avanzado
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

            # Vista previa del documento procesado
            st.image(img_final_color, caption="Vista previa del escaneo limpio", use_container_width=True)

            # Convertir a JPEG para subir
            _, buffer_limpio = cv2.imencode('.jpg', img_final_color)
            bytes_limpios = buffer_limpio.tobytes()

            nombre_archivo_drive = f"{nombre_base}_Limpio.jpg"
            folder_id = st.secrets["gcp_service_account"]["folder_id"] if "folder_id" in st.secrets["gcp_service_account"] else "ID_DE_TU_CARPETA"
            creadenciales_dict = st.secrets["gcp_service_account"]

            st.write("Subiendo a tu Google Drive...")
            id_drive = subir_a_drive(bytes_limpios, nombre_archivo_drive, folder_id, creadenciales_dict)
            
            if id_drive:
                st.balloons()
                st.success(f"🎉 ¡Guardado en Drive perfectamente!")
                st.session_state.modo_escaneo = False
                st.rerun()
                
        except Exception as error_procesamiento:
            st.error(f"Error al procesar la captura: {error_procesamiento}")
