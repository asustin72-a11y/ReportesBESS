"""Aplicación Streamlit — Consultar Tarifa (app hermana de la suite)."""

from __future__ import annotations

import streamlit as st

from tarifas_cfe import NOMBRE_APP


def main() -> None:
    st.set_page_config(
        page_title=f"{NOMBRE_APP} · IUSASOL",
        page_icon="💲",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    from bess.ui.catalog_check import validar_catalogo_al_arranque

    if not validar_catalogo_al_arranque():
        return

    from tarifas_cfe.ui.pages import run_pages

    run_pages()


if __name__ == "__main__":
    main()
