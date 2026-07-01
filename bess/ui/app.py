"""Aplicación Streamlit BESS."""

from __future__ import annotations

import warnings

import streamlit as st

st.set_page_config(
    page_title="BESS · Sistema de Energía",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main():
    from bess.ui.catalog_check import validar_catalogo_al_arranque

    if not validar_catalogo_al_arranque():
        return

    from bess.ui.pages import main as run_pages

    run_pages()


if __name__ == "__main__":
    main()
