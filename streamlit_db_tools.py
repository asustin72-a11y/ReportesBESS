"""Punto de entrada: Herramientas Base de Datos (app Streamlit aislada)."""

import sys


def _configurar_salida_consola():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError, TypeError):
            pass


_configurar_salida_consola()

import streamlit as st

st.set_page_config(
    page_title="BESS · Herramientas BD",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    from bess.config.users import rol_es_superadmin
    from bess.ui.auth import init_session, login, logout, preparar_ui_login, restaurar_ui_app
    from bess.ui.db_tools.page import main as run_db_tools

    init_session()

    if not st.session_state.autenticado:
        preparar_ui_login()
        login()
        return

    if not rol_es_superadmin(st.session_state.get("rol")):
        st.error("Solo superadministradores pueden usar Herramientas BD.")
        if st.button("Cerrar sesión"):
            logout()
        return

    restaurar_ui_app()

    with st.sidebar:
        st.markdown("### Herramientas BD")
        st.caption(f"Usuario: **{st.session_state.usuario}** ({st.session_state.rol})")
        if st.button("Cerrar sesión", use_container_width=True):
            logout()

    run_db_tools()


main()
