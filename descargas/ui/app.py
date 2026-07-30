"""Aplicación Streamlit — Descarga de Perfiles."""

from __future__ import annotations

import streamlit as st

from descargas import NOMBRE_APP


def main() -> None:
    st.set_page_config(
        page_title=NOMBRE_APP,
        page_icon="📥",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    from descargas.ui.pages import run_pages

    run_pages()


if __name__ == "__main__":
    main()
