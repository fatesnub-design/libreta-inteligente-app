import streamlit as st
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import os
import io

# Configuración visual de la app móvil
st.set_page_config(page_title="Mi Libreta Inteligente", page_icon="📝", layout="centered")

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
        
        # EXPLICACIÓN DEL CAMBIO: Forzamos supportsAllDrives=True y mantenemos los metadatos limpios
        # para que el archivo herede el almacenamiento directo de tu carpeta contenedora personal.
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        return file.get('id')
        
    except Exception as e:
        st.error(f"🚨 Error dentro de la función subir_a_drive: {e}")
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
        
    st.info("💡 Consejo: Al avanzar, selecciona 'Cámara' para capturar la hoja o súbela desde tu galería.")

# PANTALLA B: Modo Escaneo Activo
else:
    st.subheader("📷 Escáner Activo")
    
    if st.button("⬅️ Volver al Inicio"):
        st.session_state.modo_escaneo = False
        st.rerun()

    st.write("Presiona abajo para cargar o tomar la foto de tu apunte:")
    
    archivo_capturado = st.file_uploader(
        "Captura la hoja completa con el QR", 
        type=["jpg", "jpeg", "png"]
    )

    if archivo_capturado is not None:
        st.info("Procesando imagen con filtro avanzado...")
        
        try:
            bytes_data = archivo_capturado.read()
            img_array = np.frombuffer(bytes_data, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if img is None:
                st.error("🚨 OpenCV no pudo decodificar la imagen.")
            else:
                # Escaneo de QR
                codigos_qr = decode(img)
                if codigos_qr:
                    nombre_base = codigos_qr[0].data.decode('utf-8')
                    st.success(f"🔗 Código QR detectado: **{nombre_base}**")
                else:
                    nombre_base = "APUNTE_MANUAL"
                    st.warning("⚠️ No se detectó código QR. Se guardará como 'APUNTE_MANUAL'.")

                # --- FILTRO MÁGICO QUE CONSERVA COLORES VIVOS ---
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
                dilated = cv2.dilate(gray, kernel)
                bg_img = cv2.medianBlur(dilated, 21)
                img_normalizada = cv2.divide(img, cv2.merge([bg_img, bg_img, bg_img]), scale=255)
                img_final_color = cv2.convertScaleAbs(img_normalizada, alpha=1.05, beta=0)

                # Mostrar resultado estable en pantalla
                st.image(img_final_color, caption="Vista previa del escaneo limpio", use_container_width=True)

                # Convertir a Bytes para Drive
                _, buffer_limpio = cv2.imencode('.jpg', img_final_color)
                bytes_limpios = buffer_limpio.tobytes()

                # Envío a Drive (Usa el ID de tu carpeta "Prueba Libreta")
                nombre_archivo_drive = f"{nombre_base}_Limpio.jpg"
                creadenciales_dict = st.secrets["gcp_service_account"]
                
                # Coloca aquí el ID largo de la carpeta "Prueba Libreta" que obtuviste de la URL
                folder_id = "1-TWnbY_l9FBMmwqjjNawh_jjeUD1_UVP"

                st.write("Subiendo a tu Google Drive...")
                id_drive = subir_a_drive(bytes_limpios, nombre_archivo_drive, folder_id, creadenciales_dict)
                
                if id_drive:
                    st.balloons()
                    st.success(f"🎉 ¡Guardado en Drive perfectamente!")
                    st.info("Ya puedes presionar 'Volver al Inicio' arriba.")
                
        except Exception as error_procesamiento:
            st.error(f"💥 Error: {error_procesamiento}")
