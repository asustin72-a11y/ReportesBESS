"""Selector de módulo tras el login de la Suite."""

from __future__ import annotations

import streamlit as st

from bess.config.users import ETIQUETA_ROL
from bess.ui.auth import get_usuarios
from bess.ui.components import boton_cerrar_sesion, obtener_logo_html
from bess.ui.styles import aplicar_estilos
from suite import (
    MODULO_BESS,
    MODULO_DESCARGAS,
    MODULO_GRANJA,
    NOMBRE_SUITE,
    SUBTITULO_SUITE,
)


def render_selector_modulos() -> None:
    aplicar_estilos()
    logo_html = obtener_logo_html(220)
    usuario = st.session_state.get("usuario", "")
    try:
        nombre = get_usuarios().get(usuario, {}).get("nombre", usuario)
    except Exception:
        nombre = usuario
    rol = st.session_state.get("rol")
    rol_tipo = ETIQUETA_ROL.get(rol or "user", "Usuario")

    logo_block = (
        f'<div style="flex-shrink:0;background:white;border-radius:8px;'
        f'padding:4px 8px;">{logo_html}</div>'
        if logo_html
        else ""
    )
    c1, c2 = st.columns([6, 1.3])
    with c1:
        st.markdown(
            f"""
            <div class="app-header">
                {logo_block}
                <div>
                    <h1 class="app-header-title">{NOMBRE_SUITE}</h1>
                    <p class="app-header-sub">{rol_tipo}: {nombre} · {SUBTITULO_SUITE}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
        boton_cerrar_sesion(key="suite_hdr_logout")

    st.markdown("##### Elija el módulo")
    st.caption("Misma sesión y base de datos. Puede cambiar de módulo en cualquier momento.")

    col_bess, col_granja, col_descargas = st.columns(3)
    with col_bess:
        with st.container(border=True):
            st.markdown("### BESS")
            st.caption(
                "Subestaciones, demanda, arbitraje, recibo CFE, pipeline de sync "
                "y reportes de batería."
            )
            if st.button(
                "Abrir BESS",
                type="primary",
                use_container_width=True,
                key="suite_abrir_bess",
            ):
                st.session_state["suite_modulo"] = MODULO_BESS
                st.session_state.pop("sidebar_inicial_aplicada", None)
                st.rerun()
    with col_granja:
        with st.container(border=True):
            st.markdown("### Granja Solar")
            st.caption(
                "21 MEGAs · energía e ingresos DIST · dashboard y reportes PDF "
                "diario / mensual."
            )
            if st.button(
                "Abrir Granja",
                type="primary",
                use_container_width=True,
                key="suite_abrir_granja",
            ):
                st.session_state["suite_modulo"] = MODULO_GRANJA
                st.session_state.pop("sidebar_inicial_aplicada", None)
                st.rerun()
    with col_descargas:
        with st.container(border=True):
            st.markdown("### Descargas API")
            st.caption(
                "Perfiles Clientes (ISOL), Granja (Farm) y Porteo → CSV. "
                "Disponible para todos los usuarios."
            )
            if st.button(
                "Abrir Descargas",
                type="primary",
                use_container_width=True,
                key="suite_abrir_descargas",
            ):
                st.session_state["suite_modulo"] = MODULO_DESCARGAS
                st.session_state.pop("sidebar_inicial_aplicada", None)
                st.rerun()
