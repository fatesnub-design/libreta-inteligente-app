import streamlit as st
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Configuración visual
st.set_page_config(page_title="Mi Libreta Inteligente", layout="centered")

def subir_a_drive_infalible(bytes_image, nombre_archivo, folder_id):
    try:
        # Usamos las credenciales directamente de tus secretos
        creds = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': nombre_archivo,
            'parents': [folder_id]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(bytes_image), mimetype='image/jpeg', resumable=True)
        
        # Subida directa forzando la creación
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        return file.get('id')
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return None

# --- Interfaz ---
st.title("📝 Mi Libreta Inteligente")

# Modo Escaneo
archivo = st.file_uploader("Carga tu apunte", type=["jpg", "png"])

if archivo:
    # Procesamiento (Filtro que ya comprobamos que funciona)
    bytes_data = archivo.read()
    img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    
    # Filtro aplicado
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bg = cv2.medianBlur(cv2.dilate(gray, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))), 21)
    img_final = cv2.convertScaleAbs(cv2.divide(img, cv2.merge([bg, bg, bg]), scale=255), alpha=1.05)
    
    st.image(img_final)
    
    if st.button("Guardar en Drive"):
        _, buffer = cv2.imencode('.jpg', img_final)
        # ID de tu carpeta: Ponlo aquí directamente para evitar errores de lectura
        FOLDER_ID = "1-TWnbY_l9FBMmwqjjNawh_jjeUD1_UVP" 
        
        with st.spinner("Subiendo..."):
            res = subir_a_drive_infalible(buffer.tobytes(), "Apunte_Final.jpg", FOLDER_ID)
            if res:
                st.success("¡Éxito! Archivo guardado.")
