import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- Lógica de Captura del Token ---
query_params = st.query_params
if "code" in query_params and "credentials" not in st.session_state:
    flow = get_oauth_flow()
    # Usamos el código de la URL para obtener el token
    flow.fetch_token(code=query_params["code"])
    
    # Guardamos las credenciales en la sesión
    st.session_state["credentials"] = flow.credentials
    st.success("¡Autenticación exitosa!")
    st.rerun() # Recargamos para limpiar la URL y mostrar la app funcionando

# Configuración del flujo OAuth
def get_oauth_flow():
    # Definimos la URL de forma explícita
    REDIRECT_URI = "https://libreta-inteligente-app-cuvw9pyvwfnahbhrvzjseb.streamlit.app/"
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI] # Asegúrate de que esto sea una lista
            }
        },
        scopes=["https://www.googleapis.com/auth/drive.file"],
        redirect_uri=REDIRECT_URI # <--- ¡ESTA ES LA LÍNEA QUE FALTA!
    )
    return flow
    
# --- Interfaz ---
st.title("📝 Mi Libreta Inteligente")

# Añade esto justo antes de generar la URL de autorización
st.write("---")
st.write("Configuración del Flujo:")
st.write(f"Client ID: {st.secrets['GOOGLE_CLIENT_ID']}")
st.write(f"Redirect URI real en el objeto flow: {get_oauth_flow().redirect_uri}")
st.write("---")

# Si no hay credenciales, mostramos botón de Login
if 'credentials' not in st.session_state:
    flow = get_oauth_flow()
    auth_url, _ = flow.authorization_url(prompt='select_account')
    st.markdown(f'[Haz clic aquí para conectar tu Google Drive]({auth_url})')
    
    # Aquí iría la lógica para capturar el 'code' de la URL y generar el token
else:
    st.success("¡Conectado a tu cuenta!")
    # Aquí va tu lógica de subir archivo usando 'credentials'
