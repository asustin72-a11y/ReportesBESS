"""Aplicación Streamlit — Suite IUSASOL (BESS + Granja + Descargas)."""

from __future__ import annotations

import streamlit as st

from suite import (
    MODULO_BESS,
    MODULO_DESCARGAS,
    MODULO_GRANJA,
    NOMBRE_SUITE,
    SUBTITULO_SUITE,
)


def main() -> None:
    st.set_page_config(
        page_title=NOMBRE_SUITE,
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    from bess.ui.catalog_check import validar_catalogo_al_arranque

    if not validar_catalogo_al_arranque():
        return

    from bess.ui.auth import init_session, login, preparar_ui_login, restaurar_ui_app
    from bess.ui.styles import aplicar_estilos_login
    from suite.ui.selector import render_selector_modulos

    init_session()

    if st.session_state.pop("_logout_pendiente", False):
        st.cache_data.clear()
        for key in (
            "autenticado",
            "usuario",
            "rol",
            "seccion_activa",
            "modo_vista",
            "sidebar_inicial_aplicada",
            "suite_modulo",
        ):
            st.session_state.pop(key, None)
        st.session_state.autenticado = False
        st.rerun()

    if not st.session_state.get("autenticado", False):
        preparar_ui_login()
        aplicar_estilos_login()
        login(titulo=NOMBRE_SUITE, subtitulo=SUBTITULO_SUITE)
        if not st.session_state.get("autenticado", False):
            return
        st.rerun()

    modulo = st.session_state.get("suite_modulo")
    if modulo not in (MODULO_BESS, MODULO_GRANJA, MODULO_DESCARGAS):
        restaurar_ui_app(restaurar_sidebar=False)
        render_selector_modulos()
        return

    if modulo == MODULO_BESS:
        from bess.ui.pages import main as bess_main

        bess_main(desde_suite=True)
        return

    if modulo == MODULO_GRANJA:
        from granja.ui.pages import run_pages as granja_main

        granja_main(desde_suite=True)
        return

    from descargas.ui.pages import run_pages as descargas_main

    descargas_main(desde_suite=True)


if __name__ == "__main__":
    main()
