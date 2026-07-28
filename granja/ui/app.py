"""Aplicación Streamlit Granja Solar (entrada local)."""

from __future__ import annotations

import streamlit as st

from granja.config import CAPACIDAD_MW, NOMBRE_APP


def main() -> None:
    st.set_page_config(
        page_title=NOMBRE_APP,
        page_icon="☀️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    from bess.ui.catalog_check import validar_catalogo_al_arranque

    if not validar_catalogo_al_arranque():
        return

    from granja.ui.pages import run_pages

    run_pages()


if __name__ == "__main__":
    main()
