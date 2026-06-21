import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# 1. Definimos la función primero (sin ejecutarla)
def get_oauth_flow():
    REDIRECT_URI = "https://libreta-inteligente-app-cuvw9pyvwfnahbhrvzjseb.streamlit.app/"
    return Flow.from_client_config(
        {
            "web": {
                "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI]
            }
        },
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri=REDIRECT_URI
    )

# --- Lógica de Captura del Token ---
query_params = st.query_params
code = query_params.get("code")

if code and "credentials" not in st.session_state:
    try:
        flow = get_oauth_flow()
        # Intercambiamos el código por el token
        flow.fetch_token(code=code)
        st.session_state["credentials"] = flow.credentials
        
        # EL TRUCO: Limpiar la URL para que no intente usar el mismo código otra vez
        st.query_params.clear() 
        st.rerun()
    except Exception as e:
        st.error(f"Error al obtener el token: {e}")
        st.warning("El código ya expiró o fue usado. Por favor, intenta conectar de nuevo.")
        # Limpiamos si falla para que el usuario pueda volver a intentar
        if "code" in st.query_params:
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
