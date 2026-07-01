"""Autenticación Streamlit."""

from __future__ import annotations

import streamlit as st

from bess.config.users import (
    cargar_usuarios_desde_env,
    parse_usuarios_json,
    parse_usuarios_mapping,
    verificar_password,
)
from bess.ui.components import obtener_logo_html
from bess.ui.styles import aplicar_estilos_login

_ERROR_SIN_USUARIOS = (
    'No hay usuarios configurados. Defina `[users]` en `.streamlit/secrets.toml` '
    'o la variable de entorno `BESS_USERS` (JSON). '
    'Vea `.streamlit/secrets.toml.example`.'
)


@st.cache_resource(show_spinner=False)
def get_usuarios() -> dict:
    """Usuarios desde secrets de Streamlit o variable BESS_USERS."""
    usuarios = _cargar_desde_streamlit_secrets()
    if usuarios is None:
        usuarios = cargar_usuarios_desde_env()
    if not usuarios:
        raise RuntimeError(_ERROR_SIN_USUARIOS)
    return usuarios


def _cargar_desde_streamlit_secrets() -> dict | None:
    from streamlit.errors import StreamlitSecretNotFoundError

    try:
        secrets = st.secrets
    except StreamlitSecretNotFoundError:
        return None

    try:
        users = secrets['users']
        return parse_usuarios_mapping({k: dict(v) for k, v in users.items()})
    except (StreamlitSecretNotFoundError, KeyError):
        pass

    try:
        return parse_usuarios_json(str(secrets['BESS_USERS']))
    except (StreamlitSecretNotFoundError, KeyError):
        return None


def init_session():
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.usuario = None
        st.session_state.rol = None


def login():
    aplicar_estilos_login()
    st.markdown('<div class="login-page-marker"></div>', unsafe_allow_html=True)

    try:
        usuarios = get_usuarios()
    except (RuntimeError, ValueError) as exc:
        _, col, _ = st.columns([3, 4, 3])
        with col:
            st.error(str(exc))
        return

    _, col, _ = st.columns([3, 4, 3])
    with col:
        logo_html = obtener_logo_html(288)
        logo_block = (
            f'<div class="login-logo-wrap">'
            f'<div style="background:white;border-radius:10px;padding:8px 14px;'
            f'box-shadow:0 1px 4px rgba(0,0,0,0.04);">{logo_html}</div></div>'
            if logo_html else ''
        )
        st.markdown(f"""
        <div class="login-brand">
            {logo_block}
            <h1 class="login-title">BESS · Sistema de Energía</h1>
            <p class="login-subtitle">Sistema de Procesamiento y Reportes de Energía</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            with st.form("login"):
                usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
                password = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
                submit = st.form_submit_button("Iniciar Sesión", use_container_width=True, type="primary")

                if submit and usuario and password:
                    registro = usuarios.get(usuario)
                    if registro and verificar_password(password, registro['password']):
                        st.session_state.autenticado = True
                        st.session_state.usuario = usuario
                        st.session_state.rol = registro['rol']
                        st.cache_data.clear()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")


def logout():
    st.cache_data.clear()
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.rol = None
    st.rerun()
