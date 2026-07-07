import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from PIL import Image
import numpy as np
import io
import cv2

# --- 1. Configuración de la Página e Inyección de CSS (Guía Rocketbook) ---
st.set_page_config(page_title="Mi Libreta Inteligente", layout="centered")

# Este bloque inyecta la máscara verde fosforescente únicamente sobre la cámara en vivo
st.markdown("""
    <style>
    /* Ubica el contenedor de video nativo de Streamlit */
    div[data-testid="stCameraInput"] {
        position: relative;
        border: 2px solid #333;
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Dibuja la máscara verde translúcida de alineación */
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

# --- 2. Flujo de Autenticación Google ---
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

# --- 3. Función del Filtro de Escaneo Universal ---
def aplicar_filtro_escaneo(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Eliminación de iluminación compleja por división
    bg = cv2.GaussianBlur(gray, (51, 51), 0)
    normalized = cv2.divide(gray, bg, scale=255)
    
    # Filtrado bilateral para eliminar ruido digital
    smoothed = cv2.bilateralFilter(normalized, 9, 50, 50)
    
    # Binarización adaptativa de vecindario gigante (mantiene lápiz y quita sombras)
    final_scanned = cv2.adaptiveThreshold(
        smoothed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 71, 12
    )
    
    cleaned_img = Image.fromarray(final_scanned)
    buffered = io.BytesIO()
    cleaned_img.save(buffered, format="JPEG", quality=95)
    return buffered.getvalue()

# --- 4. Gestión de Estado de Credenciales ---
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
    # --- 5. Interfaz Principal para Usuarios Autenticados ---
    st.title("📝 Mi Libreta Inteligente")
    st.success("🔒 Conectado a tu Google Drive")
    st.write("---")
    
    # Implementación de pestañas para soportar ambos flujos (Producción vs Pruebas actuales)
    tab1, tab2 = st.tabs(["📸 Cámara en Vivo", "📁 Subir Archivo (Pruebas)"])
    
    imagen_para_procesar = None
    nombre_archivo = "escaneo.jpg"
    
    with tab1:
        st.write("Apunta con la cámara de tu dispositivo usando la guía verde:")
        foto_camara = st.camera_input("Tomar foto de la libreta")
        if foto_camara:
            imagen_para_procesar = foto_camara.getvalue()
            nombre_archivo = "Camara_Escaneo.jpg"
            
    with tab2:
        st.write("Sube aquí las imágenes que te pase tu compañero para realizar simulaciones de filtro:")
        archivo_subido = st.file_uploader("Elige una foto desde tu equipo", type=["png", "jpg", "jpeg"])
        if archivo_subido:
            imagen_para_procesar = archivo_subido.getvalue()
            nombre_archivo = archivo_subido.name

    # --- 6. Botón de Ejecución Único ---
    if imagen_para_procesar is not None:
        st.write("---")
        st.image(imagen_para_procesar, caption="Previsualización de la Captura", use_container_width=True)
        
        if st.button("Procesar y Guardar en Google Drive", type="primary"):
            with st.spinner("Procesando filtros avanzados de escaneo y subiendo a la nube..."):
                try:
                    # Aplicamos el filtro de Sauvola/División
                    imagen_limpia_bytes = aplicar_filtro_escaneo(imagen_para_procesar)
                    
                    # Desplegamos el escaneo final corregido
                    st.image(imagen_limpia_bytes, caption="Resultado Final Enviado a Drive", use_container_width=True)
                    
                    # Proceso de subida a la API de Drive
                    creds = st.session_state["credentials"]
                    service = build('drive', 'v3', credentials=creds)
                    
                    file_metadata = {'name': f"Limpio_{nombre_archivo}"}
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
                    
                    st.success(f"¡Escaneo procesado y guardado con éxito! ID de Drive: {file.get('id')}")
                    
                except Exception as e:
                    st.error(f"Hubo un error crítico al procesar o subir el archivo: {e}")
