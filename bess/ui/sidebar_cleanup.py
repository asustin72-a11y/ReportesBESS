"""Limpieza de residuos de navegación BESS al cambiar de módulo en la Suite."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

# Selectores de HTML/JS que BESS inyecta en el documento padre y sobreviven al rerun.
_SELECTORES_RESIDUO = (
    ".sidebar-guia, .sidebar-modulo, .sidebar-flujo, .sidebar-paso,"
    ".sidebar-guia-titulo, .sidebar-flujo-titulo, .sidebar-flujo-nota,"
    ".bess-floating-tip, #bess-nav-tooltip-root"
)

_CSS_OCULTAR = f"""
<style>
    {_SELECTORES_RESIDUO} {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        max-height: 0 !important;
        width: 0 !important;
        max-width: 0 !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
        opacity: 0 !important;
        pointer-events: none !important;
        position: fixed !important;
        top: -9999px !important;
        left: -9999px !important;
    }}
</style>
"""


def _emitir(markup: str) -> None:
    if hasattr(st, "html"):
        try:
            st.html(markup, height=0)
        except TypeError:
            st.html(markup)
    else:
        components.html(markup, height=0)


def limpiar_residuos_nav_bess(*, con_css: bool = True) -> None:
    """Elimina guía/tooltips BESS residuales (p. ej. al abrir otra app de la suite)."""
    if con_css:
        st.markdown(_CSS_OCULTAR, unsafe_allow_html=True)

    selectores = _SELECTORES_RESIDUO
    markup = f"""
    <script>
    (function () {{
      const d = window.parent && window.parent.document
        ? window.parent.document : document;
      function limpiar() {{
        d.querySelectorAll('{selectores}').forEach(function (el) {{
          el.remove();
        }});
        if (d.__bessNavTipObserver) {{
          try {{ d.__bessNavTipObserver.disconnect(); }} catch (e) {{}}
          d.__bessNavTipObserver = null;
          d.__bessNavTipReady = false;
        }}
        d.body.classList.remove('bess-rol-user-mode');
      }}
      limpiar();
      [50, 200, 600, 1200].forEach(function (ms) {{
        setTimeout(limpiar, ms);
      }});
    }})();
    </script>
    """
    _emitir(markup)
