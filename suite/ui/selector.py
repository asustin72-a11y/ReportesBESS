"""Selector de módulo tras el login de la Suite."""

from __future__ import annotations

import streamlit as st

from bess.config.users import ETIQUETA_ROL
from bess.ui.auth import get_usuarios
from bess.ui.components import boton_cerrar_sesion, obtener_logo_html
from bess.ui.styles import aplicar_estilos
from suite import (
    MODULO_ANALISIS_PERFIL,
    MODULO_BESS,
    MODULO_CONSULTAR_TARIFA,
    MODULO_DESCARGAS,
    MODULO_GRANJA,
    NOMBRE_SUITE,
    SUBTITULO_SUITE,
    VERSION,
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
                    <p class="app-header-sub">{rol_tipo}: {nombre} ·
                       {SUBTITULO_SUITE} · v{VERSION}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
        boton_cerrar_sesion(key="suite_hdr_logout")

    st.markdown("##### Elija el módulo")
    st.caption(
        "Misma sesión y base de datos. Puede cambiar de módulo en cualquier momento."
    )

    def _tarjeta(
        titulo: str,
        caption: str,
        boton: str,
        key: str,
        modulo: str,
    ) -> None:
        with st.container(border=True):
            st.markdown(f"### {titulo}")
            st.caption(caption)
            if st.button(
                boton,
                type="primary",
                use_container_width=True,
                key=key,
            ):
                st.session_state["suite_modulo"] = modulo
                st.session_state.pop("sidebar_inicial_aplicada", None)
                st.rerun()

    r1 = st.columns(3)
    with r1[0]:
        _tarjeta(
            "BESS",
            "Subestaciones, demanda, arbitraje, recibo CFE, pipeline de sync "
            "y reportes de batería.",
            "Abrir BESS",
            "suite_abrir_bess",
            MODULO_BESS,
        )
    with r1[1]:
        _tarjeta(
            "Granja Solar",
            "21 MEGAs · energía e ingresos DIST · dashboard y reportes PDF "
            "diario / mensual.",
            "Abrir Granja",
            "suite_abrir_granja",
            MODULO_GRANJA,
        )
    with r1[2]:
        _tarjeta(
            "Descargas API",
            "Perfiles Clientes (ISOL), Granja (Farm) y Porteo → CSV. "
            "Disponible para todos los usuarios.",
            "Abrir Descargas",
            "suite_abrir_descargas",
            MODULO_DESCARGAS,
        )

    r2 = st.columns(3)
    with r2[0]:
        _tarjeta(
            "Análisis de Perfil",
            "Perfiles cincominutales · tarifas T01 / GDMTH / DIST · "
            "PDF, CSV recibo y calidad de datos.",
            "Abrir Análisis",
            "suite_abrir_analisis",
            MODULO_ANALISIS_PERFIL,
        )
    with r2[1]:
        _tarjeta(
            "Consultar Tarifa",
            "Cuotas vigentes en CFE (Hogar, Negocio, Industria, Agrícola) "
            "y descarga de reportes CSV.",
            "Abrir Tarifas",
            "suite_abrir_tarifas",
            MODULO_CONSULTAR_TARIFA,
        )
