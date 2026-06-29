import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from PIL import Image
from skimage.filters import threshold_local
import numpy as np
import io
import cv2

# 1. Definimos la función primero (sin ejecutarla)
def get_oauth_flow():
    REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
    
    flow = Flow.from_client_config(
        {
            "installed": {
                "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri=REDIRECT_URI
    )
    
    # ESTO ES LO QUE ELIMINA EL ERROR:
    # Forzamos a que no haya verificador de código.
    flow.code_verifier = None
    return flow

# 2. 
# --- Función de Filtro de Escaneo Mejorada ---
def aplicar_filtro_escaneo(image_bytes):
    # 1. Convertir bytes a formato OpenCV
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    orig = img.copy()
    
    # 2. Preprocesamiento enfocado en estructuras grandes
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    
    # Umbralizado adaptativo para resaltar el contorno grueso del marco
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 21, 5)
    
    # 3. FILTRADO RECTANGULAR POR ÁREA (Aquí destruimos el periódico)
    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    h_img, w_img = img.shape[:2]
    area_total = h_img * w_img
    
    x_final, y_final, w_final, h_final = None, None, None, None
    max_area = 0
    
    for c in cnts:
        # Obtenemos la caja de cada contorno detectado
        x, y, w, h = cv2.boundingRect(c)
        area_c = w * h
        
        # El marco de la libreta DEBE ser grande (más del 35% de la foto) 
        # pero menor que la imagen completa (para no agarrar el borde de la foto)
        if area_c > (area_total * 0.35) and area_c < (area_total * 0.98):
            if area_c > max_area:
                max_area = area_c
                x_final, y_final, w_final, h_final = x, y, w, h

    # 4. EJECUTAR EL RECORTE
    if x_final is not None:
        # Ajustamos un margen interno de 8 píxeles para limpiar el borde negro exterior si queda chueco
        x_min = max(0, x_final + 8)
        y_min = max(0, y_final + 8)
        x_max = min(w_img, x_final + w_final - 8)
        y_max = min(h_img, y_final + h_final - 8)
        
        hoja_recortada = orig[y_min:y_max, x_min:x_max]
        gray_final = cv2.cvtColor(hoja_recortada, cv2.COLOR_BGR2GRAY)
    else:
        # PLAN B INVISIBLE: Si por la luz extrema no se halló la caja gigante, 
        # rebanamos rígidamente un 9% superior/inferior para asegurar que se vaya el periódico.
        margin_h = int(h_img * 0.09)
        margin_w = int(w_img * 0.04)
        hoja_recortada = orig[margin_h:h_img-margin_h, margin_w:w_img-margin_w]
        gray_final = cv2.cvtColor(hoja_recortada, cv2.COLOR_BGR2GRAY)

    # 5. FILTRO DE LIMPIEZA SUAVE (El que ya te dejó el texto perfecto)
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    dilated_img = cv2.dilate(gray_final, kernel_clean)
    bg_img = cv2.medianBlur(dilated_img, 25)
    
    diff_img = cv2.absdiff(gray_final, bg_img)
    diff_img = 255 - diff_img
    normalized_img = cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    
    _, thresholded = cv2.threshold(normalized_img, 225, 255, cv2.THRESH_TRUNC)
    final_scanned = cv2.normalize(thresholded, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    
    # 6. Guardar y enviar de vuelta en bytes
    cleaned_img = Image.fromarray(final_scanned)
    buffered = io.BytesIO()
    cleaned_img.save(buffered, format="JPEG", quality=95)
    return buffered.getvalue()

# --- Lógica de Autenticación Definitiva ---
if "credentials" not in st.session_state:
    
    # Si el botón de conectar no se ha tocado, creamos el flujo inicial
    if "oauth_flow" not in st.session_state:
        st.session_state["oauth_flow"] = get_oauth_flow()
        
    # Usamos SIEMPRE el mismo objeto de la sesión para que no pierda el PKCE
    flow = st.session_state["oauth_flow"]
    auth_url, _ = flow.authorization_url(prompt='select_account')
    
    st.markdown(f"[Haz clic aquí para obtener tu código]({auth_url})")
    codigo = st.text_input("Pega aquí el código que te dio Google:")
    
    if st.button("Conectar"):
        try:
            # Usamos el flujo guardado en memoria que SÍ tiene el verifier original
            st.session_state["oauth_flow"].fetch_token(code=codigo)
            st.session_state["credentials"] = st.session_state["oauth_flow"].credentials
            st.success("¡Conectado exitosamente!")
            st.rerun()
        except Exception as e:
            st.error(f"Error al conectar: {e}")
            # Si falló, borramos el flujo viejo para generar uno limpio al recargar
            del st.session_state["oauth_flow"]

# 3. Interfaz de usuario
st.title("📝 Mi Libreta Inteligente")

if "credentials" not in st.session_state:
    # Generamos la URL solo si el usuario aún no está conectado
    flow = get_oauth_flow()
    auth_url, _ = flow.authorization_url(prompt='select_account')
    st.markdown(f'[Haz clic aquí para conectar tu Google Drive]({auth_url})')
else:
    st.success("¡Conectado a tu cuenta!")
    st.header("Subir nuevo escaneo inteligente")
    
    archivo_subido = st.file_uploader("Elige una foto de tu libreta", type=["png", "jpg", "jpeg"])
    
    if archivo_subido is not None:
        original_bytes = archivo_subido.read()
        
        # Muestra la foto que me mandaste tal cual
        st.image(original_bytes, caption="Foto Original", use_container_width=True)
        
        if st.button("Procesar y Guardar en Google Drive"):
            with st.spinner("Procesando filtros de escaneo y subiendo..."):
                try:
                    # Aplica la limpieza
                    imagen_limpia_bytes = aplicar_filtro_escaneo(original_bytes)
                    
                    # Te muestra el resultado limpio en la pantalla
                    st.image(imagen_limpia_bytes, caption="Resultado del Escaneo Limpio", use_container_width=True)
                    
                    # Sube el archivo limpio a Drive
                    creds = st.session_state["credentials"]
                    service = build('drive', 'v3', credentials=creds)
                    
                    file_metadata = {'name': f"Escaneo_{archivo_subido.name}"}
                    media = MediaIoBaseUpload(
                        io.BytesIO(imagen_limpia_bytes), 
                        mimetype='image/jpeg', 
                        resumable=True
                    )
                    
                    file = service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    
                    st.success(f"¡Escaneo guardado con éxito! ID en Drive: {file.get('id')}")
                    
                except Exception as e:
                    st.error(f"Hubo un error al procesar o subir: {e}")

