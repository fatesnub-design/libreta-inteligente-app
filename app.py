import streamlit as st
import cv2
import numpy as np
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# 1. Configuración de Drive
def subir_a_drive_directo(bytes_image, nombre_archivo, folder_id):
    try:
        creds = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])
        service = build('drive', 'v3', credentials=creds)
        
        # Metadata para que el archivo se guarde directamente en tu carpeta
        file_metadata = {
            'name': nombre_archivo,
            'parents': [folder_id]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(bytes_image), mimetype='image/jpeg', resumable=True)
        
        # Intentamos subir. Si falla por cuota, es porque Google Drive 
        # está restringiendo al robot en una cuenta personal.
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return file.get('id')
    except Exception as e:
        return str(e)

# 2. Interfaz y lógica
st.title("📝 Mi Libreta Inteligente")
archivo = st.file_uploader("Carga tu apunte", type=["jpg", "png"])

if archivo:
    bytes_data = archivo.read()
    img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    
    # Filtro aplicado
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, img_final = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    
    st.image(img_final)
    
    if st.button("Guardar en Drive"):
        _, buffer = cv2.imencode('.jpg', img_final)
        FOLDER_ID = "1-TWnbY_l9FBMmwqjjNawh_jjeUD1_UVP"
        
        with st.spinner("Subiendo..."):
            resultado = subir_a_drive_directo(buffer.tobytes(), "Apunte_Final.jpg", FOLDER_ID)
            
            if "id" in resultado or len(resultado) > 20: # Éxito
                st.success("¡Éxito! Archivo guardado.")
            else:
                st.error(f"Error detectado: {resultado}")
                st.info("💡 Si el error persiste, la única opción en cuentas personales es usar el almacenamiento de Firebase.")
