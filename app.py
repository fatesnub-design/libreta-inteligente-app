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
    h_img, w_img = img.shape[:2]
    
    # 2. CREAR MÁSCARA LIMPIA DE RUIDO (Para detectar el contorno dinámicamente)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Desenfoque pesado para fusionar las letras del periódico con su propio fondo blanco
    blur_detect = cv2.GaussianBlur(gray, (15, 15), 0)
    
    # Umbralizado fuerte: el marco negro se vuelve blanco (255) y el resto negro
    _, thresh_detect = cv2.threshold(blur_detect, 75, 255, cv2.THRESH_BINARY_INV)
    
    # Operación Morfológica de Clausura: cerramos cualquier corte hecho por sombras pesadas
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
    thresh_detect = cv2.morphologyEx(thresh_detect, cv2.MORPH_CLOSE, kernel_close)
    
    # 3. ENCONTRAR EL MARCO DE LA LIBRETA (Independiente del tamaño o distancia)
    cnts, _ = cv2.findContours(thresh_detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:3]
    
    screenCnt = None
    area_total = h_img * w_img
    
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.03 * peri, True)
        
        # Buscamos una estructura de 4 esquinas que represente un área lógica en la foto
        if len(approx) == 4 and cv2.contourArea(c) > (area_total * 0.25):
            screenCnt = approx
            break
            
    # 4. TRANSFORMACIÓN DE PERSPECTIVA (Si detecta el marco de forma dinámica)
    if screenCnt is not None:
        pts = screenCnt.reshape(4, 2)
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        (tl, tr, br, bl) = rect
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")
            
        M = cv2.getPerspectiveTransform(rect, dst)
        hoja_recortada = cv2.warpPerspective(orig, M, (maxWidth, maxHeight))
        # Ajuste fino: quitar 8 píxeles de los bordes del resultado para limpiar el remanente del marco negro
        hoja_recortada = hoja_recortada[8:maxHeight-8, 8:maxWidth-8]
        gray_final = cv2.cvtColor(hoja_recortada, cv2.COLOR_BGR2GRAY)
    else:
        # PLAN B AUTOMÁTICO REVISADO: Si la toma es destructiva, remueve un margen seguro proporcional
        ymin, ymax = int(h_img * 0.10), int(h_img * 0.88)
        xmin, xmax = int(w_img * 0.04), int(w_img * 0.96)
        hoja_recortada = orig[ymin:ymax, xmin:xmax]
        gray_final = cv2.cvtColor(hoja_recortada, cv2.COLOR_BGR2GRAY)

    # 5. PROCESAMIENTO DE TEXTO EQUILIBRADO (Lápiz nítido y fondo blanco puro)
    # Corrección de iluminación por división de fondo (aplana las sombras internas)
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31))
    background = cv2.dilate(gray_final, kernel_clean)
    background = cv2.medianBlur(background, 31)
    
    normalized = cv2.absdiff(gray_final, background)
    normalized = 255 - normalized
    
    # Realce local para trazos de lápiz claros
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(normalized)
    
    # Umbral adaptativo final balanceado (bloque intermedio de 37 para evitar roturas)
    final_scanned = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 37, 8
    )
    
    # 6. Guardar el archivo final limpio
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

