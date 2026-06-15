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
        
        # Sube vinculando la propiedad al dueño de la carpeta destino
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True  # Rompe el bloqueo de cuota
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
        
    st.info("💡 Consejo: Al avanzar, selecciona 'Cámara' para tomar la foto en alta definición y sin retrasos.")

# PANTALLA B: Modo Escaneo Activo (Uploader Nativo Totalmente Compatible)
else:
    st.subheader("📷 Escáner Activo")
    
    if st.button("⬅️ Volver al Inicio"):
        st.session_state.modo_escaneo = False
        st.rerun()

    st.write("Presiona abajo para tomar la foto de tu apunte:")
    
    # Este componente abre la app de la cámara del celular directamente al interactuar en móviles
    archivo_capturado = st.file_uploader(
        "Selecciona 'Cámara' para capturar la hoja completa con el QR", 
        type=["jpg", "jpeg", "png"]
    )

    if archivo_capturado is not None:
        st.info("Procesando imagen con filtro avanzado...")
        
        try:
            # Leer los bytes del archivo cargado
            bytes_data = archivo_capturado.read()
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

            # Filtro de Limpieza Avanzado (Filtro Mágico de OpenCV)
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

            # Mostrar resultado limpio en pantalla
            st.image(img_final_color, caption="Vista previa del escaneo limpio", use_container_width=True)

            # Convertir de OpenCV a Bytes para Google Drive
            _, buffer_limpio = cv2.imencode('.jpg', img_final_color)
            bytes_limpios = buffer_limpio.tobytes()

            # Configuración de rutas usando los Secrets de Streamlit
            nombre_archivo_drive = f"{nombre_base}_Limpio.jpg"
            folder_id = st.secrets["gcp_service_account"]["folder_id"] if "folder_id" in st.secrets["gcp_service_account"] else "1-TWnbY_l9FBMmwqjjNawh_jjeUD1_UVP"
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
