"""Estilos CSS (mismo lenguaje visual que bess/ui/styles.py)."""

from __future__ import annotations

import streamlit as st

from analisis_perfil.theme import COLORES


def aplicar_estilos() -> None:
    p = COLORES["primary"]
    s = COLORES["secondary"]
    st.markdown(
        f"""
    <style>
        [data-testid="stAppViewContainer"] > .main .block-container {{
            max-width: 1200px !important;
            padding-top: 1.2rem !important;
            padding-bottom: 2rem !important;
        }}
        [data-testid="stSidebar"] {{
            background: #f8fafc;
            border-right: 1px solid #e2e8f0;
        }}
        /* Controles del módulo viven en el área principal (usuarios sin sidebar). */
        [data-testid="stSidebar"] [data-testid="stSidebarContent"]:empty,
        section[data-testid="stSidebar"]:has([data-testid="stSidebarNavItems"]:only-child) {{
            min-width: 0;
        }}
        .ius-header {{
            display: flex;
            align-items: center;
            gap: 18px;
            background: linear-gradient(135deg, {p}, {s});
            padding: 18px 22px;
            border-radius: 12px;
            margin-bottom: 18px;
            color: #fff;
        }}
        .ius-header-brand {{
            background: #fff;
            color: {p};
            font-weight: 800;
            font-size: 0.95rem;
            letter-spacing: 0.04em;
            padding: 10px 14px;
            border-radius: 10px;
            line-height: 1.1;
        }}
        .ius-header-title {{
            margin: 0;
            font-size: 1.45rem;
            font-weight: 700;
        }}
        .ius-header-sub {{
            margin: 4px 0 0;
            font-size: 0.88rem;
            opacity: 0.92;
        }}
        .section-header {{
            margin: 1.65rem 0 0.85rem 0;
            padding: 14px 18px;
            background: linear-gradient(90deg, #e8f2f9 0%, #f8fafc 70%);
            border: 1px solid #c5d0da;
            border-left: 6px solid {p};
            border-radius: 10px;
            box-shadow: 0 1px 2px rgba(26, 82, 118, 0.05);
        }}
        .section-header:first-of-type,
        .section-header.first {{
            margin-top: 0.35rem;
        }}
        .section-header .section-title {{
            margin: 0;
            padding: 0;
            border-bottom: none;
        }}
        .section-title {{
            font-size: 1.4rem;
            font-weight: 700;
            letter-spacing: -0.015em;
            color: {p};
            margin: 1.4rem 0 10px 0;
            padding: 0 0 10px 0;
            border-bottom: 3px solid {s};
            line-height: 1.3;
        }}
        .section-desc {{
            font-size: 0.92rem;
            color: #4a5568;
            margin: 0 0 14px 0;
            line-height: 1.5;
        }}
        .metric-chip {{
            background: #eef6fc;
            border: 1px solid #a8d4ee;
            border-radius: 10px;
            padding: 10px 14px;
            margin-bottom: 8px;
        }}
        .metric-chip strong {{
            color: {p};
        }}
        .metric-card {{
            background: white;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
            border: 1px solid #e8ecef;
            margin-bottom: 10px;
        }}
        .metric-card .label {{
            font-size: 13px;
            color: #718096;
            font-weight: 500;
        }}
        .metric-card .value {{
            font-size: 22px;
            font-weight: 700;
            color: #1a202c;
            line-height: 1.25;
            margin-top: 4px;
        }}
        .metric-card .sub {{
            font-size: 12px;
            color: #a0aec0;
            margin-top: 4px;
            line-height: 1.35;
        }}
        .metric-card .periodos {{
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid #e8ecef;
            text-align: left;
            font-size: 12px;
            color: #4a5568;
        }}
        .metric-card .periodos div {{
            display: flex;
            justify-content: space-between;
            gap: 8px;
            padding: 2px 0;
        }}
        .grupo-resumen-titulo {{
            font-size: 1.1rem;
            font-weight: 700;
            color: {p};
            margin: 0 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid {s};
            text-align: center;
        }}
        .resumen-bidi-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px 16px;
            align-items: start;
        }}
        .resumen-bidi-grid > .metric-card {{
            margin-bottom: 0;
        }}
        .fecha-resumen {{
            background: #eaf4fb;
            border-left: 4px solid {p};
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 13px;
            color: #4a5568;
            margin-bottom: 14px;
        }}
        hr {{
            margin: 1.5rem 0 !important;
            border: none !important;
            border-top: 2px solid #cbd5e1 !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-color: #c5d0da !important;
            border-width: 1.5px !important;
            border-radius: 12px !important;
            background: #ffffff;
            margin-bottom: 1.15rem !important;
            padding-top: 0.35rem;
        }}
        div.stButton > button[kind="primary"] {{
            background: {p};
            border-color: {p};
        }}
        div.stButton > button[kind="primary"]:hover {{
            background: #154360;
            border-color: #154360;
        }}
        .stDownloadButton > button {{
            border: 1px solid #a8d4ee;
            color: {p};
        }}
        @media (max-width: 768px) {{
            [data-testid="stAppViewContainer"] > .main .block-container {{
                padding-left: 0.6rem !important;
                padding-right: 0.6rem !important;
                padding-top: 0.75rem !important;
            }}
            .ius-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
                padding: 14px 14px;
            }}
            .ius-header-title {{ font-size: 1.15rem; }}
            .ius-header-sub {{ font-size: 0.8rem; }}
            .section-title {{ font-size: 1.15rem; }}
            .section-header {{ padding: 10px 12px; }}
            .resumen-bidi-grid {{
                grid-template-columns: 1fr !important;
            }}
            [data-testid="stHorizontalBlock"]:has(.suite-session-bar-marker) {{
                flex-wrap: wrap !important;
            }}
            [data-testid="stHorizontalBlock"]:has(.suite-session-bar-marker)
                > [data-testid="column"] {{
                flex: 0 0 100% !important;
                min-width: 100% !important;
                max-width: 100% !important;
            }}
            div[data-testid="stDataFrame"] {{
                overflow-x: auto !important;
                max-width: 100% !important;
            }}
        }}
        @media (max-width: 480px) {{
            .ius-header-title {{ font-size: 1.05rem; }}
            .section-title {{ font-size: 1.05rem; }}
        }}
    </style>
    """,
        unsafe_allow_html=True,
    )


def render_header(titulo: str, subtitulo: str) -> None:
    st.markdown(
        f"""
        <div class="ius-header">
          <div class="ius-header-brand">IUSASOL</div>
          <div>
            <p class="ius-header-title">{titulo}</p>
            <p class="ius-header-sub">{subtitulo}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(titulo: str, *, first: bool = False) -> None:
    """Título de sección principal con barra visual de separación."""
    cls = "section-header first" if first else "section-header"
    st.markdown(
        f'<div class="{cls}"><p class="section-title">{titulo}</p></div>',
        unsafe_allow_html=True,
    )
