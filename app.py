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
        # Credenciales desde Secrets
        creds = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': nombre_archivo,
            'parents': [folder_id]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(bytes_image), mimetype='image/jpeg', resumable=True)
        
        # 1. Crear el archivo
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = file.get('id')
        
        # 2. EL TRUCO: Transferir propiedad a TU correo personal inmediatamente
        # Esto hace que el archivo cuente contra TU espacio de 15GB y NO contra el robot.
        permission = {
            'type': 'user',
            'role': 'owner',
            'emailAddress': 'fatesnub@gmail.com' # Tu correo personal
        }
        service.permissions().create(
            fileId=file_id,
            body=permission,
            transferOwnership=True
        ).execute()
        
        return file_id
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return None

# --- Interfaz ---
st.title("📝 Mi Libreta Inteligente")

archivo = st.file_uploader("Carga tu apunte", type=["jpg", "png"])

if archivo:
    # Procesamiento (Filtro base)
    bytes_data = archivo.read()
    img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    
    # Filtro aplicado (Sencillo para asegurar que corra)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_final = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    st.image(img_final, caption="Vista previa")
    
    if st.button("Guardar en Drive"):
        _, buffer = cv2.imencode('.jpg', img_final)
        # ID DE LA CARPETA (Cópialo de la URL)
        FOLDER_ID = "1-TWnbY_l9FBMmwqjjNawh_jjeUD1_UVP" 
        
        with st.spinner("Subiendo..."):
            res = subir_a_drive_infalible(buffer.tobytes(), "Apunte_Final.jpg", FOLDER_ID)
            if res:
                st.success("¡Éxito! Archivo guardado y propiedad transferida a tu cuenta.")
