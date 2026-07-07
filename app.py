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

# --- Inicializar el Lector de OCR en Caché ---
@st.cache_resource
def cargar_lector_ocr():
    return easyocr.Reader(['es', 'en'], gpu=False)

reader = cargar_lector_ocr()

# --- Inicializar Variables de Sesión para las Materias (Lista Dinámica) ---
if "lista_materias" not in st.session_state:
    # Empezamos con unas por defecto, pero ahora es una lista indexada
    st.session_state["lista_materias"] = ["Matemáticas", "Física", "Química", "Personal / Notas"]

# --- CONFIGURACIÓN DINÁMICA EN LA BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Configuración de Destinos")
    st.write("Gestiona tus materias o carpetas en el orden de las casillas de tu hoja:")
    
    # 1. Formulario para añadir una nueva materia
    nueva_materia = st.text_input("Añadir nueva materia o sección:")
    if st.button("➕ Agregar a la Libreta"):
        if nueva_materia.strip() != "":
            if nueva_materia.strip() not in st.session_state["lista_materias"]:
                st.session_state["lista_materias"].append(nueva_materia.strip())
                st.success(f"¡'{nueva_materia}' agregada!")
                st.rerun()
            else:
                st.warning("Ese destino ya existe en la lista.")

    st.write("---")
    st.subheader("📋 Mapeo de Casillas Actuales")
    
    # 2. Mostrar la lista con el número de casilla correspondiente
    if st.session_state["lista_materias"]:
        for i, materia in enumerate(st.session_state["lista_materias"]):
            st.write(f"**Casilla {i+1}:** {materia}")
            
        # Botón opcional para limpiar la lista y empezar de cero
        if st.button("🗑️ Limpiar todas las materias"):
            st.session_state["lista_materias"] = []
            st.rerun()
    else:
        st.info("No has agregado materias aún. Usa el cuadro de arriba.")

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

# --- Extraer Título por OCR ---
def extraer_titulo_ocr(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    
    recorte_superior = img[0:int(h * 0.22), 0:w]
    resultados = reader.readtext(recorte_superior)
    
    texto_acumulado = ""
    for (bbox, texto, probabilidad) in resultados:
        texto_limpio_bloque = re.sub(r'(?i)nombre\s*:?', '', texto).strip()
        if probabilidad > 0.30 and len(texto_limpio_bloque) > 2:
            texto_acumulado += " " + texto_limpio_bloque
            
    texto_final = " ".join(texto_acumulado.split()).strip()
    
    if len(texto_final) > 35:
        texto_final = texto_final[:35]
        if " " in texto_final:
            texto_final = texto_final.rsplit(" ", 1)[0]
            
    palabras = texto_final.split()
    conectores_prohibidos = ["si", "la", "el", "con", "de", "un", "y", "a", "q"]
    if palabras and palabras[-1].lower() in conectores_prohibidos:
        palabras.pop()
    
    texto_final = " ".join(palabras)
    texto_final = re.sub(r'[\\/*?:"<>|.]', "", texto_final).strip()
    
    if not texto_final:
        texto_final = "Escaneo_Sin_Nombre"
    else:
        texto_final = texto_final.title()
        
    return texto_final

# --- Función de Detección Real OMR con OpenCV ---
def detectar_materia_marcada(image_bytes):
    # 1. Convertir la imagen a escala de grises
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    
    # 2. Recortar la franja inferior (donde están los números y círculos)
    # Tomamos del 90% al 98% de la altura total de la hoja corregida
    recorte_inferior = img[int(h * 0.90):int(h * 0.98), 0:w]
    
    # 3. Preprocesar para binarizar (Blanco y Negro puro)
    gray = cv2.cvtColor(recorte_inferior, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    # 4. Dividir el ancho en 8 columnas iguales
    ancho_columna = w // 8
    pixeles_por_casilla = []
    
    for i in range(8):
        # Aislar la columna actual
        x_inicio = i * ancho_columna
        x_fin = (i + 1) * ancho_columna
        casilla = thresh[0:recorte_inferior.shape[0], x_inicio:x_fin]
        
        # Contar cuántos píxeles están marcados (blancos en la imagen invertida)
        total_pixeles = cv2.countNonZero(casilla)
        pixeles_por_casilla.append(total_pixeles)
        
    # 5. Encontrar cuál casilla tiene la mayor cantidad de trazo
    casilla_marcada_idx = np.argmax(pixeles_por_casilla)
    max_pixeles = pixeles_por_casilla[casilla_marcada_idx]
    
    # Umbral de seguridad: Si la casilla más marcada no tiene suficientes píxeles, 
    # asumimos que la hoja se dejó vacía por error.
    if max_pixeles < 50: 
        return "General"
        
    # 6. Mapear el índice (0 a 7) con tu lista dinámica de Streamlit
    if st.session_state["lista_materias"] and casilla_marcada_idx < len(st.session_state["lista_materias"]):
        materia_final = st.session_state["lista_materias"][casilla_marcada_idx]
    else:
        # Si la casilla marcada no tiene materia asignada aún en la app
        materia_final = f"Casilla_{casilla_marcada_idx + 1}"
        
    return materia_final

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
        st.write("Apunta con la cámara de tu dispositivo:")
        foto_camara = st.camera_input("Tomar foto de la libreta")
        if foto_camara:
            imagen_para_procesar = foto_camara.getvalue()
            
    with tab2:
        st.write("Sube aquí las imágenes de simulación:")
        archivo_subido = st.file_uploader("Elige una foto desde tu equipo", type=["png", "jpg", "jpeg"])
        if archivo_subido:
            imagen_para_procesar = archivo_subido.getvalue()

# =========================================================================
# 1. FUNCIÓN DE DRIVE (Debe estar alineada totalmente a la izquierda)
# =========================================================================
def obtener_o_crear_carpeta_drive(service, nombre_carpeta):
    # 1. Buscar si la carpeta ya existe
    query = f"name = '{nombre_carpeta}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    resultados = service.files().list(q=query, fields="files(id)").execute()
    files = resultados.get('files', [])
    
    if files:
        # Si ya existe, devolvemos su ID
        return files[0]['id']
    else:
        # Si no existe, la creamos desde cero
        metadata_carpeta = {
            'name': nombre_carpeta,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        carpeta = service.files().create(body=metadata_carpeta, fields='id').execute()
        return carpeta.get('id')


# =========================================================================
# 2. CONTROL DE FLUJO E INTERFAZ DE CONFIRMACIÓN 
# (Alineado correctamente a la izquierda o dentro de tu condicional de imagen)
# =========================================================================
if imagen_para_procesar is not None:
    st.write("---")
    st.image(imagen_para_procesar, caption="Previsualización de la Captura", use_container_width=True)
    
    # Botón inicial para activar el análisis por IA
    if st.button("🔍 Analizar Escaneo", type="secondary"):
        with st.spinner("Leyendo hoja con Inteligencia Artificial..."):
            # Guardamos los resultados del análisis en el estado de la sesión
            st.session_state["ocr_titulo_detectado"] = extraer_titulo_ocr(imagen_para_procesar)
            st.session_state["omr_materia_detectada"] = detectar_materia_marcada(imagen_para_procesar)
            st.session_state["analisis_listo"] = True

    # Si la IA ya analizó la imagen, desplegamos el panel de control manual
    if st.session_state.get("analisis_listo", False):
        st.markdown("### 🛠️ Panel de Verificación Manual")
        st.info("Revisa si la IA leyó todo correctamente. Puedes editar los campos si es necesario antes de subir.")
        
        # 1. Campo editable para el Título
        titulo_verificado = st.text_input(
            "📝 Título del documento:", 
            value=st.session_state.get("ocr_titulo_detectado", "Escaneo_Sin_Nombre")
        )
        
        # 2. Menú desplegable para la Materia/Carpeta Destino
        opciones_carpetas = st.session_state["lista_materias"] if st.session_state["lista_materias"] else ["General"]
        
        # Intentamos preseleccionar la que detectó el OMR, si no, la primera de la lista
        materia_detectada = st.session_state.get("omr_materia_detectada", "General")
        idx_preseleccionado = 0
        if materia_detectada in opciones_carpetas:
            idx_preseleccionado = opciones_carpetas.index(materia_detectada)
            
        materia_verificada = st.selectbox(
            "📁 Carpeta de destino en Drive:",
            options=opciones_carpetas,
            index=idx_preseleccionado
        )
        
        st.write("")
        # 3. BOTÓN CRÍTICO DEFINITIVO
        if st.button("🚀 Confirmar y Guardar en Google Drive", type="primary"):
            with st.spinner("Subiendo archivo limpio a tu nube..."):
                try:
                    # Aplicar Filtro de limpieza
                    imagen_limpia_bytes = aplicar_filtro_escaneo(imagen_para_procesar)
                    
                    # Conectar a la API de Drive
                    creds = st.session_state["credentials"]
                    service = build('drive', 'v3', credentials=creds)
                    
                    # Obtener o crear la carpeta usando el valor VERIFICADO por el usuario
                    id_carpeta_destino = obtener_o_crear_carpeta_drive(service, materia_verificada)
                    
                    # Metadatos con el título VERIFICADO por el usuario
                    file_metadata = {
                        'name': f"{titulo_verificado}.jpg",
                        'parents': [id_carpeta_destino]
                    }
                    
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
                    
                    # 1. Mostramos el mensaje de éxito estático
                    st.success(f"¡Excelente! Guardado con éxito en **{materia_verificada}** como '{titulo_verificado}.jpg'")
                    
                    # 2. Desactivamos el panel de edición para el siguiente escaneo
                    st.session_state["analisis_listo"] = False
                    
                except Exception as e:
                    st.error(f"Hubo un error crítico al subir: {e}")
