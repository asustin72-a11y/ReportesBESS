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
    VERSION,
)

# (titulo, key, modulo)
_OPERACION = (
    ("BESS", "suite_abrir_bess", MODULO_BESS),
    ("Granja Solar", "suite_abrir_granja", MODULO_GRANJA),
)

_HERRAMIENTAS = (
    ("Descargas API", "suite_abrir_descargas", MODULO_DESCARGAS),
    ("Análisis de Perfil", "suite_abrir_analisis", MODULO_ANALISIS_PERFIL),
    ("Consultar Tarifa", "suite_abrir_tarifas", MODULO_CONSULTAR_TARIFA),
)

_KEYS_MODULO = (
    "suite_abrir_bess",
    "suite_abrir_granja",
    "suite_abrir_descargas",
    "suite_abrir_analisis",
    "suite_abrir_tarifas",
)


def _estilos_selector() -> None:
    # Estilos por key de Streamlit (st-key-...); el botón es la tarjeta.
    selectores = ",\n        ".join(
        f'.st-key-{k} button, div[class*="st-key-{k}"] button' for k in _KEYS_MODULO
    )
    selectores_inner = ",\n        ".join(
        f'.st-key-{k} button p, .st-key-{k} button div, .st-key-{k} button span, '
        f'div[class*="st-key-{k}"] button p, div[class*="st-key-{k}"] button div, '
        f'div[class*="st-key-{k}"] button span'
        for k in _KEYS_MODULO
    )
    selectores_hover = ",\n        ".join(
        f'.st-key-{k} button:hover, div[class*="st-key-{k}"] button:hover'
        for k in _KEYS_MODULO
    )
    st.markdown(
        f"""
        <style>
        .suite-welcome-marker {{ display: none; }}
        .suite-hero {{
            display: flex;
            align-items: center;
            gap: 20px;
            background: linear-gradient(135deg, #1a5276 0%, #2e86c1 100%);
            border-radius: 14px;
            padding: 22px 26px;
            margin-bottom: 8px;
            color: #fff;
        }}
        .suite-hero-logo {{
            flex-shrink: 0;
            background: #fff;
            border-radius: 10px;
            padding: 8px 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        .suite-hero h1 {{
            margin: 0;
            font-size: 200%;
            font-weight: 700;
            color: #fff;
            letter-spacing: -0.02em;
        }}
        .suite-hero p {{
            margin: 6px 0 0;
            font-size: 0.92rem;
            color: rgba(255,255,255,0.92);
            line-height: 1.4;
        }}
        .suite-hero-meta {{
            margin-top: 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
        }}
        .suite-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.18);
            border: 1px solid rgba(255,255,255,0.35);
            color: #fff;
            font-size: 0.78rem;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 999px;
        }}
        .suite-group {{
            margin: 18px 0 6px;
        }}
        .suite-group-title {{
            font-size: 15px;
            font-weight: 600;
            color: #1a5276;
            margin: 0 0 4px 0;
            padding-bottom: 6px;
            border-bottom: 2px solid #e8ecef;
        }}
        .suite-group-desc {{
            font-size: 12px;
            color: #718096;
            margin: 0 0 12px 0;
        }}
        {selectores} {{
            background: #ffffff !important;
            background-color: #ffffff !important;
            color: #1a5276 !important;
            border: 2px solid #c5d4de !important;
            border-top: 5px solid #1a5276 !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            min-height: 120px !important;
            height: auto !important;
            padding: 28px 18px !important;
            white-space: pre-line !important;
            text-align: center !important;
            font-size: 200% !important;
            font-weight: 700 !important;
            line-height: 1.3 !important;
            transition: box-shadow 0.15s ease, border-color 0.15s ease,
                        transform 0.15s ease !important;
        }}
        {selectores_inner} {{
            font-size: inherit !important;
            font-weight: 700 !important;
        }}
        {selectores_hover} {{
            border-color: #2e86c1 !important;
            border-top-color: #2e86c1 !important;
            border-width: 2px !important;
            border-top-width: 5px !important;
            color: #1a5276 !important;
            background: #f8fafc !important;
            background-color: #f8fafc !important;
            box-shadow: 0 6px 18px rgba(26, 82, 118, 0.14) !important;
            transform: translateY(-1px);
        }}
        @media (max-width: 768px) {{
            .suite-hero {{
                flex-direction: column;
                align-items: flex-start;
                padding: 16px 18px;
            }}
            .suite-hero h1 {{ font-size: 1.55rem !important; }}
            .suite-hero p {{ font-size: 0.85rem; }}
            .suite-group-title {{ font-size: 14px; }}
            /* Apilar tarjetas de módulos en una columna */
            [data-testid="stHorizontalBlock"]:has([class*="st-key-suite_abrir"]) {{
                flex-direction: column !important;
                flex-wrap: wrap !important;
                gap: 0.55rem !important;
            }}
            [data-testid="stHorizontalBlock"]:has([class*="st-key-suite_abrir"])
                > [data-testid="column"] {{
                flex: 0 0 100% !important;
                min-width: 100% !important;
                max-width: 100% !important;
                width: 100% !important;
            }}
            {selectores} {{
                min-height: 72px !important;
                padding: 18px 14px !important;
                font-size: 1.25rem !important;
                font-weight: 700 !important;
            }}
            /* Logout centrado a ancho completo */
            [data-testid="stHorizontalBlock"]:has(.st-key-suite_hdr_logout),
            [data-testid="stHorizontalBlock"]:has([class*="st-key-suite_hdr_logout"]) {{
                justify-content: center !important;
            }}
            [data-testid="stHorizontalBlock"]:has([class*="st-key-suite_hdr_logout"])
                > [data-testid="column"] {{
                flex: 0 0 100% !important;
                min-width: 100% !important;
                max-width: 100% !important;
            }}
        }}
        @media (max-width: 480px) {{
            .suite-hero h1 {{ font-size: 1.35rem !important; }}
            {selectores} {{
                font-size: 1.15rem !important;
                min-height: 64px !important;
            }}
        }}
        </style>
        <div class="suite-welcome-marker"></div>
        """,
        unsafe_allow_html=True,
    )


def _abrir_modulo(modulo: str) -> None:
    st.session_state["suite_modulo"] = modulo
    st.session_state.pop("sidebar_inicial_aplicada", None)
    st.rerun()


def _tarjeta(titulo: str, key: str, modulo: str) -> None:
    if st.button(
        titulo,
        key=key,
        use_container_width=True,
        type="secondary",
    ):
        _abrir_modulo(modulo)


def _fila_modulos(items: tuple) -> None:
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            _tarjeta(*item)


def render_selector_modulos() -> None:
    aplicar_estilos()
    _estilos_selector()

    logo_html = obtener_logo_html(200)
    usuario = st.session_state.get("usuario", "")
    try:
        nombre = get_usuarios().get(usuario, {}).get("nombre", usuario)
    except Exception:
        nombre = usuario
    rol = st.session_state.get("rol")
    rol_tipo = ETIQUETA_ROL.get(rol or "user", "Usuario")

    logo_block = (
        f'<div class="suite-hero-logo">{logo_html}</div>' if logo_html else ""
    )

    st.markdown(
        f"""
        <div class="suite-hero">
            {logo_block}
            <div>
                <h1>{NOMBRE_SUITE}</h1>
                <p>Misma sesión y base de datos · elija un módulo para continuar</p>
                <div class="suite-hero-meta">
                    <span class="suite-badge">{rol_tipo}: {nombre}</span>
                    <span class="suite-badge">v{VERSION}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="suite-group">
            <div class="suite-group-title">Operación</div>
            <p class="suite-group-desc">Reporteadores principales de planta y granja.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _fila_modulos(_OPERACION)

    st.markdown(
        """
        <div class="suite-group">
            <div class="suite-group-title">Herramientas</div>
            <p class="suite-group-desc">Descargas, análisis de perfiles y consulta de tarifas CFE.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _fila_modulos(_HERRAMIENTAS)

    st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
    _, col_logout, _ = st.columns([2, 1.2, 2])
    with col_logout:
        boton_cerrar_sesion(key="suite_hdr_logout")
