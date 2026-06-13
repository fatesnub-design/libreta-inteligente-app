import streamlit as st
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json
import os

# Configuración visual de la app móvil
st.set_page_config(page_title="Mi Libreta Inteligente", page_icon="📝", layout="centered")
st.title("📝 Escáner de Apuntes Inteligente")
st.write("Toma una foto a tu hoja apuntando al código QR para procesarla automáticamente.")

# 1. Función para conectar con Google Drive usando el JSON de la cuenta de servicio
def conectar_drive():
    # En producción, Streamlit maneja los secretos de forma segura
    info_claves = st.secrets["gcp_service_account"]
    credenciales = service_account.Credentials.from_service_account_info(info_claves)
    servicio = build('drive', 'v3', credentials=credenciales)
    return servicio

# 2. Función para subir el archivo a una carpeta específica de Drive
def subir_a_drive(ruta_archivo_local, nombre_final):
    try:
        drive_service = conectar_drive()
        # ID de tu carpeta 'MiLibretaDigital' en Drive (lo sacas de la URL de la carpeta)
        ID_CARPETA_DRIVE = st.secrets["id_carpeta_drive"] 
        
        metadata_archivo = {
            'name': nombre_final,
            'parents': [ID_CARPETA_DRIVE]
        }
        media = MediaFileUpload(ruta_archivo_local, mimetype='image/png')
        archivo_subido = drive_service.files().create(body=metadata_archivo, media_body=media, fields='id').execute()
        return archivo_subido.get('id')
    except Exception as e:
        st.error(f"Error al subir a Google Drive: {e}")
        return None

# 3. INTERFAZ MÓVIL: Botón nativo para activar la cámara del celular
foto_capturada = st.camera_input("📷 Enfoca tu apunte y el QR")

if foto_capturada is not None:
    st.info("Procesando imagen con filtro avanzado...")
    
    # Convertir la foto de la cámara a un formato que OpenCV entienda
    bytes_data = foto_capturada.getvalue()
    img_array = np.frombuffer(bytes_data, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    # A. Buscar y decodificar el código QR de la hoja
    codigos_qr = decode(img)
    if codigos_qr:
        nombre_base = codigos_qr[0].data.decode('utf-8')
        st.success(f"🔗 Código QR detectado con éxito: **{nombre_base}**")
    else:
        nombre_base = "APUNTE_MANUAL"
        st.warning("⚠️ No se detectó código QR en la toma. Se guardará como 'APUNTE_MANUAL'.")

    # B. Aplicar tu filtro de Cierre Morfológico Avanzado (El chido multicolores)
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

    # Guardar el resultado localmente de manera temporal
    nombre_archivo_temp = f"{nombre_base}_Limpio.png"
    cv2.imwrite(nombre_archivo_temp, img_final_color)

    # C. Mostrar la previsualización del resultado limpio en la pantalla del cel
    st.image(img_final_color, caption="Vista previa del escaneo limpio", use_container_width=True)

    # D. Subir automáticamente a Google Drive
    st.write("Subiendo a tu Google Drive...")
    id_drive = subir_a_drive(nombre_archivo_temp, nombre_archivo_temp)
    
    if id_drive:
        st.balloons() # ¡Efecto de globos en el cel al tener éxito!
        st.success(f"🎉 ¡Guardado en Drive perfectamente! (ID: {id_drive})")
    
    # Limpieza del archivo temporal
    if os.path.exists(nombre_archivo_temp):
        os.remove(nombre_archivo_temp)
