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

# 2. Lógica de captura del token (aquí es donde evitamos que falle al inicio)
query_params = st.query_params
if "code" in query_params and "credentials" not in st.session_state:
    flow = get_oauth_flow() # Ahora sí existe
    flow.fetch_token(code=query_params["code"])
    st.session_state["credentials"] = flow.credentials
    st.rerun()

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
