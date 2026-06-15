import streamlit as st
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

# Configuración visual de la app móvil
st.set_page_config(page_title="Mi Libreta Inteligente", page_icon="📝", layout="centered")

# --- CONEXIÓN A DRIVE ---
def conectar_drive():
    info_claves = st.secrets["gcp_service_account"]
    credenciales = service_account.Credentials.from_service_account_info(info_claves)
    return build('drive', 'v3', credentials=credenciales)

def subir_a_drive(bytes_image, nombre_archivo, folder_id, creadenciales_dict):
    try:
        # Autenticación con los Secrets de la cuenta de servicio
        creds = service_account.Credentials.from_service_account_info(creadenciales_dict)
        service = build('drive', 'v3', credentials=creds)
        
        # Preparar el archivo en memoria
        media = MediaIoBaseUpload(io.BytesIO(bytes_image), mimetype='image/jpeg', resumable=True)
        
        # Datos del archivo en Drive
        file_metadata = {
            'name': nombre_archivo,
            'parents': [folder_id]
        }
        
        # Crear y subir el archivo en la carpeta compartida
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True  # <-- Esta línea soluciona el error de cuota de almacenamiento
        ).execute()
        
        return file.get('id')
        
    except Exception as e:
        st.error(f"Error al subir a Google Drive: {e}")
        return None

# --- INTERFAZ GRÁFICA MÓVIL ---
st.title("📝 Mi Libreta Inteligente")

# Usamos el estado de Streamlit para saber si el usuario quiere escanear o estar en el menú
if "modo_escaneo" not in st.session_state:
    st.session_state.modo_escaneo = False

# PANTALLA A: Menú de Inicio Principal
if not st.session_state.modo_escaneo:
    st.write("¡Bienvenido, Carlos! Organiza tus apuntes de la universidad al instante.")
    
    # Botón grande para activar la acción
    st.write("")
    if st.button("🚀 EMPEZAR A ESCANEAR APUNTES", use_container_width=True):
        st.session_state.modo_escaneo = True
        st.rerun() # Recarga la app para mostrar la cámara
        
    st.info("💡 Consejo: Al presionar el botón, asegúrate de enfocar la hoja completa bajo buena luz para que el filtro limpie bien el fondo.")

# PANTALLA B: Modo Cámara Activo
else:
    st.subheader("📷 Escáner Activo")
    
    # Botón para regresar al menú si te arrepientes
    if st.button("⬅️ Volver al Inicio"):
        st.session_state.modo_escaneo = False
        st.rerun()

    foto_capturada = st.camera_input("Encuadra la hoja completa incluyendo el QR")

    if foto_capturada is not None:
        st.info("Procesando imagen con filtro avanzado...")
        
        bytes_data = foto_capturada.getvalue()
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

        # Filtro de Limpieza avanzado
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

        nombre_archivo_temp = f"{nombre_base}_Limpio.png"
        cv2.imwrite(nombre_archivo_temp, img_final_color)

        st.image(img_final_color, caption="Vista previa del escaneo limpio", use_container_width=True)

        st.write("Subiendo a tu Google Drive...")
        id_drive = subir_a_drive(nombre_archivo_temp, nombre_archivo_temp)
        
        if id_drive:
            st.balloons()
            st.success(f"🎉 ¡Guardado en Drive perfectamente!")
            # Regresamos al menú inicial automáticamente tras el éxito
            st.session_state.modo_escaneo = False
        
        if os.path.exists(nombre_archivo_temp):
            os.remove(nombre_archivo_temp)
