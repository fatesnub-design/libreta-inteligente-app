import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from PIL import Image
import numpy as np
import io
import cv2
import easyocr
import re

# --- Configuración de la Página e Inyección de CSS (Guía Rocketbook) ---
st.set_page_config(page_title="Mi Libreta Inteligente", layout="centered")

st.markdown("""
    <style>
    div[data-testid="stCameraInput"] {
        position: relative;
        border: 2px solid #333;
        border-radius: 8px;
        overflow: hidden;
    }
    div[data-testid="stCameraInput"]::after {
        content: "Alinea el marco de la libreta aquí";
        position: absolute;
        top: 10%;
        left: 8%;
        width: 84%;
        height: 75%;
        border: 3px dashed #00ff00;
        border-radius: 12px;
        pointer-events: none;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #00ff00;
        font-weight: bold;
        background-color: rgba(0, 0, 0, 0.1);
        font-family: sans-serif;
        font-size: 15px;
        text-shadow: 1px 1px 3px #000;
        box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.3);
    }
    </style>
""", unsafe_allow_html=True)

# --- Inicializar el Lector de OCR en Caché (Para que no recargue en cada clic) ---
@st.cache_resource
def cargar_lector_ocr():
    # Inicializa el lector para idioma español ('es') e inglés ('en')
    return easyocr.Reader(['es', 'en'], gpu=False)

reader = cargar_lector_ocr()

# --- Flujo de Autenticación Google ---
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
    flow.code_verifier = None
    return flow

# --- FUNCIÓN NUEVA: Extraer Título por OCR ---
def extraer_titulo_ocr(image_bytes):
    # 1. Convertir bytes a OpenCV
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    
    # MODIFICACIÓN: Ampliamos el rango al 22% para asegurar que entre todo el renglón
    recorte_superior = img[0:int(h * 0.22), 0:w]
    
    # 2. Pasar el recorte al lector OCR
    resultados = reader.readtext(recorte_superior)
    
    texto_detectado = ""
    for (bbox, texto, probabilidad) in resultados:
        # Hacemos la limpieza más inteligente para remover "Nombre" o "Nombre:" si aparecen
        texto_limpio_bloque = re.sub(r'(?i)nombre\s*:?', '', texto)
        
        # Bajamos ligeramente la probabilidad a 0.30 para que acepte trazos de lápiz más tenues
        if probabilidad > 0.30 and len(texto_limpio_bloque.strip()) > 2:
            texto_detectado += " " + texto_limpio_bloque
            
    # 3. Limpieza final de espacios y caracteres prohibidos
    texto_final = texto_detectado.strip()
    texto_final = re.sub(r'[\\/*?:"<>|]', "", texto_final)
    
    # Reemplazar múltiples espacios por uno solo
    texto_final = " ".join(texto_final.split())
    
    # Si de verdad no leyó nada, dejamos el respaldo seguro
    if not texto_final:
        texto_final = "Escaneo_Sin_Nombre"
        
    return texto_final

# --- Función del Filtro de Escaneo Universal ---
def aplicar_filtro_escaneo(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bg = cv2.GaussianBlur(gray, (51, 51), 0)
    normalized = cv2.divide(gray, bg, scale=255)
    
    smoothed = cv2.bilateralFilter(normalized, 9, 50, 50)
    
    final_scanned = cv2.adaptiveThreshold(
        smoothed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 71, 12
    )
    
    cleaned_img = Image.fromarray(final_scanned)
    buffered = io.BytesIO()
    cleaned_img.save(buffered, format="JPEG", quality=95)
    return buffered.getvalue()

# --- Gestión de Estado de Credenciales ---
if "credentials" not in st.session_state:
    st.title("📝 Conectar Aplicación")
    if "oauth_flow" not in st.session_state:
        st.session_state["oauth_flow"] = get_oauth_flow()
        
    flow = st.session_state["oauth_flow"]
    auth_url, _ = flow.authorization_url(prompt='select_account')
    
    st.markdown(f"[Haz clic aquí para obtener tu código de verificación de Google]({auth_url})")
    codigo = st.text_input("Pega aquí el código que te dio Google:")
    
    if st.button("Conectar cuenta"):
        try:
            st.session_state["oauth_flow"].fetch_token(code=codigo)
            st.session_state["credentials"] = st.session_state["oauth_flow"].credentials
            st.success("¡Conectado exitosamente!")
            st.rerun()
        except Exception as e:
            st.error(f"Error al conectar: {e}")
            if "oauth_flow" in st.session_state:
                del st.session_state["oauth_flow"]
else:
    # --- Interfaz Principal ---
    st.title("📝 Mi Libreta Inteligente")
    st.success("🔒 Conectado a tu Google Drive")
    st.write("---")
    
    tab1, tab2 = st.tabs(["📸 Cámara en Vivo", "📁 Subir Archivo (Pruebas)"])
    
    imagen_para_procesar = None
    
    with tab1:
        st.write("Apunta con la cámara de tu dispositivo usando la guía verde:")
        foto_camara = st.camera_input("Tomar foto de la libreta")
        if foto_camara:
            imagen_para_procesar = foto_camara.getvalue()
            
    with tab2:
        st.write("Sube aquí las imágenes de simulación:")
        archivo_subido = st.file_uploader("Elige una foto desde tu equipo", type=["png", "jpg", "jpeg"])
        if archivo_subido:
            imagen_para_procesar = archivo_subido.getvalue()

    # --- Botón de Ejecución Único ---
    if imagen_para_procesar is not None:
        st.write("---")
        st.image(imagen_para_procesar, caption="Previsualización de la Captura", use_container_width=True)
        
        if st.button("Procesar y Guardar en Google Drive", type="primary"):
            with st.spinner("Leyendo título a mano y aplicando filtros avanzados..."):
                try:
                    # 1. PASO NUEVO: Extraemos el título del papel usando OCR antes de aplicar filtros destructivos
                    titulo_detectado = extraer_titulo_ocr(imagen_para_procesar)
                    st.info(f"🔎 Título detectado por OCR: **{titulo_detectado}**")
                    
                    # 2. Aplicamos el filtro de limpieza
                    imagen_limpia_bytes = aplicar_filtro_escaneo(imagen_para_procesar)
                    st.image(imagen_limpia_bytes, caption="Resultado Final Enviado a Drive", use_container_width=True)
                    
                    # 3. Proceso de subida a la API de Drive usando el título dinámico
                    creds = st.session_state["credentials"]
                    service = build('drive', 'v3', credentials=creds)
                    
                    # El nombre del archivo ahora es el título detectado por la IA
                    file_metadata = {'name': f"{titulo_detectado}.jpg"}
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
                    
                    st.success(f"¡Escaneo guardado con éxito como '{titulo_detectado}.jpg'! ID: {file.get('id')}")
                    
                except Exception as e:
                    st.error(f"Hubo un error crítico al procesar o subir el archivo: {e}")
