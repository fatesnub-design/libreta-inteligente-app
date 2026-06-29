import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# 1. Definimos la función primero (sin ejecutarla)
def get_oauth_flow():
    # En Desktop App, Google usa esta URL estándar para redirigir
    REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
    
    flow = Flow.from_client_config(
        {
            "installed": { # Cambiamos 'web' por 'installed' para el flujo de Desktop
                "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri=REDIRECT_URI
    )
    return flow

# --- Lógica de Captura del Token ---
query_params = st.query_params
code = query_params.get("code")

if code and "credentials" not in st.session_state:
    try:
        flow = get_oauth_flow()
        
        # AQUÍ ESTÁ EL CAMBIO: 
        # Forzamos la obtención del token pasando el código directamente 
        # y eliminando la dependencia de estados previos que fallan.
        flow.fetch_token(code=code, include_client_id=True)
        
        st.session_state["credentials"] = flow.credentials
        
        # Limpiamos los parámetros para que la URL se vea limpia
        st.query_params.clear()
        st.rerun()
        
    except Exception as e:
        st.error(f"Error al obtener el token: {e}")
        # Si falla, limpiamos para permitir reintento
        st.query_params.clear()

# 3. Interfaz de usuario
st.title("📝 Mi Libreta Inteligente")

if "credentials" not in st.session_state:
    # Generamos la URL solo si el usuario aún no está conectado
    flow = get_oauth_flow()
    auth_url, _ = flow.authorization_url(prompt='select_account')
    st.markdown(f'[Haz clic aquí para conectar tu Google Drive]({auth_url})')
else:
    st.success("¡Conectado a tu cuenta!")
    # Aquí iría tu lógica de tu app principal...
