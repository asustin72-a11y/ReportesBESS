"""Autenticación Streamlit."""

from __future__ import annotations

import streamlit as st

from bess.config.users import (
    ERROR_SIN_USUARIOS,
    cargar_usuarios_fuente_externa,
    verificar_password,
)
import streamlit.components.v1 as components

from bess.ui.components import obtener_logo_html
from bess.ui.styles import aplicar_estilos_login

_ERROR_SIN_USUARIOS = ERROR_SIN_USUARIOS


@st.cache_resource(show_spinner=False)
def get_usuarios() -> dict:
    """Usuarios desde SQLite; bootstrap secrets/env si la tabla estaba vacía."""
    from bess.data.users_db import ensure_usuarios_listo, leer_usuarios_dict

    ensure_usuarios_listo()
    usuarios = leer_usuarios_dict(solo_activos=True)
    if not usuarios:
        usuarios = cargar_usuarios_fuente_externa() or {}
    if not usuarios:
        raise RuntimeError(_ERROR_SIN_USUARIOS)
    return usuarios


def init_session():
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.usuario = None
        st.session_state.rol = None
        st.session_state.modo_vista = "reporteador"


def _emitir_script_ui(markup: str) -> None:
    if hasattr(st, "html"):
        try:
            st.html(markup, height=0)
        except TypeError:
            st.html(markup)
    else:
        components.html(markup, height=0)


def _inyectar_limpieza_ui_sesion():
    """Quita restos de sidebar y tooltips al volver al login."""
    js = r"""
    (function () {
        function doc() {
            return window.parent && window.parent.document ? window.parent.document : document;
        }

        function limpiar() {
            const d = doc();
            d.body.classList.add('bess-login-mode');

            d.querySelectorAll(
                '.bess-floating-tip, #bess-nav-tooltip-root, .sidebar-guia, .sidebar-modulo,'
                + '.sidebar-flujo, .sidebar-paso, .sidebar-guia-titulo, .sidebar-flujo-titulo'
            ).forEach(function (el) {
                el.remove();
            });

            if (d.__bessNavTipObserver) {
                try { d.__bessNavTipObserver.disconnect(); } catch (e) {}
                d.__bessNavTipObserver = null;
                d.__bessNavTipReady = false;
            }

            const sidebar = d.querySelector('section[data-testid="stSidebar"]');
            if (sidebar) {
                sidebar.style.setProperty('display', 'none', 'important');
                sidebar.style.setProperty('visibility', 'hidden', 'important');
                sidebar.style.setProperty('width', '0', 'important');
                sidebar.style.setProperty('min-width', '0', 'important');
                sidebar.style.setProperty('max-width', '0', 'important');
                sidebar.style.setProperty('overflow', 'hidden', 'important');
                sidebar.setAttribute('aria-hidden', 'true');
                sidebar.querySelectorAll(
                    '[data-testid="stSidebarUserContent"], [data-testid="stSidebarContent"]'
                ).forEach(function (node) {
                    node.innerHTML = '';
                });
            }

            d.querySelectorAll(
                '[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],'
                + '[data-testid="stExpandSidebarButton"]'
            ).forEach(function (el) {
                el.style.setProperty('display', 'none', 'important');
                el.style.setProperty('visibility', 'hidden', 'important');
            });

            const main = d.querySelector('[data-testid="stAppViewContainer"] > .main');
            if (main) {
                main.style.setProperty('margin-left', '0', 'important');
                main.style.setProperty('padding-left', '0', 'important');
            }
        }

        limpiar();
        [0, 40, 120, 300, 700, 1500, 3000].forEach(function (ms) {
            setTimeout(limpiar, ms);
        });

        const d = doc();
        if (d.__bessLoginCleanerObs) return;
        const app = d.querySelector('[data-testid="stApp"]') || d.body;
        d.__bessLoginCleanerObs = new MutationObserver(function () {
            if (d.body.classList.contains('bess-login-mode')) limpiar();
        });
        d.__bessLoginCleanerObs.observe(app, { childList: true, subtree: true });
    })();
    """
    _emitir_script_ui(f"<script>{js}</script>")


def _inyectar_salir_modo_login(*, restaurar_sidebar: bool = True):
    """Quita modo login; opcionalmente restaura la sidebar (solo admin/superadmin)."""
    restaurar_js = "true" if restaurar_sidebar else "false"
    js = f"""
    (function () {{
        const RESTAURAR_SIDEBAR = {restaurar_js};
        const d = window.parent && window.parent.document ? window.parent.document : document;
        d.body.classList.remove('bess-login-mode');
        if (d.__bessLoginCleanerObs) {{
            try {{ d.__bessLoginCleanerObs.disconnect(); }} catch (e) {{}}
            d.__bessLoginCleanerObs = null;
        }}
        if (!RESTAURAR_SIDEBAR) return;
        const sidebar = d.querySelector('section[data-testid="stSidebar"]');
        if (sidebar) {{
            sidebar.style.removeProperty('display');
            sidebar.style.removeProperty('visibility');
            sidebar.style.removeProperty('width');
            sidebar.style.removeProperty('min-width');
            sidebar.style.removeProperty('max-width');
            sidebar.style.removeProperty('overflow');
            sidebar.removeAttribute('aria-hidden');
        }}
        d.querySelectorAll(
            '[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],'
            + '[data-testid="stExpandSidebarButton"]'
        ).forEach(function (el) {{
            el.style.removeProperty('display');
            el.style.removeProperty('visibility');
        }});
    }})();
    """
    _emitir_script_ui(f"<script>{js}</script>")


def _preparar_sidebar_login():
    """Oculta por completo el contenido residual de la barra lateral."""
    with st.sidebar:
        st.markdown(
            """
            <style>
            body.bess-login-mode section[data-testid="stSidebar"],
            body.bess-login-mode section[data-testid="stSidebar"] * {
                display: none !important;
                visibility: hidden !important;
                max-height: 0 !important;
                overflow: hidden !important;
            }
            </style>
            <div class="bess-login-sidebar-placeholder" aria-hidden="true"></div>
            """,
            unsafe_allow_html=True,
        )


def preparar_ui_login():
    """Limpia sidebar y aplica estilos de login (llamar antes de login())."""
    _preparar_sidebar_login()
    aplicar_estilos_login()
    _inyectar_limpieza_ui_sesion()


def restaurar_ui_app(*, restaurar_sidebar: bool = True):
    """Quita el modo login del DOM tras autenticarse."""
    _inyectar_salir_modo_login(restaurar_sidebar=restaurar_sidebar)


def login():
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
                        st.session_state.pop("sidebar_inicial_aplicada", None)
                        st.cache_data.clear()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")


def logout():
    st.cache_data.clear()
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.rol = None
    st.session_state.pop("seccion_activa", None)
    st.session_state.pop("modo_vista", None)
    st.session_state.pop("sidebar_inicial_aplicada", None)
    # Recarga completa del navegador: única forma fiable de vaciar la sidebar en Streamlit.
    _emitir_script_ui(
        """
        <script>
        (function () {
            const w = window.parent && window.parent !== window ? window.parent : window;
            w.setTimeout(function () { w.location.reload(); }, 80);
        })();
        </script>
        """
    )
    st.stop()
