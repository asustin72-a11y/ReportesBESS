"""Aplicación Streamlit Análisis de Perfil (app hermana de la suite)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from analisis_perfil import NOMBRE_APP

# Asegura imports del pipeline (scripts hermanos del paquete).
_PKG = Path(__file__).resolve().parents[1]
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))


def main() -> None:
    st.set_page_config(
        page_title=f"{NOMBRE_APP} · IUSASOL",
        page_icon="⚡",
        layout="wide",
        # Controles en área principal; sidebar de la suite es para admin.
        initial_sidebar_state="collapsed",
    )

    from bess.ui.catalog_check import validar_catalogo_al_arranque

    if not validar_catalogo_al_arranque():
        return

    from analisis_perfil.ui.pages import run_pages

    run_pages()


if __name__ == "__main__":
    main()
