"""Botones de descarga HTML (PDF, PNG, etc.)."""

from __future__ import annotations

import base64
import html

import streamlit.components.v1 as components


def render_boton_descarga(
    archivo_bytes: bytes,
    nombre_archivo: str,
    mime_type: str,
    etiqueta: str,
    altura: int = 76,
):
    """Botón de descarga en iframe (mismo estilo que el reporte PDF)."""
    archivo_b64 = base64.b64encode(archivo_bytes).decode()
    nombre_seguro = html.escape(nombre_archivo, quote=True)
    etiqueta_segura = html.escape(etiqueta)
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                background: transparent;
                font-family: "Source Sans Pro", sans-serif;
            }}
            .reporte-dl-box {{
                max-width: 320px;
                margin: 12px auto 0;
                background: linear-gradient(135deg, #1e8449 0%, #27ae60 100%);
                padding: 10px 14px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(39, 174, 96, 0.28);
            }}
            .reporte-dl-btn,
            .reporte-dl-btn:link,
            .reporte-dl-btn:visited,
            .reporte-dl-btn:hover,
            .reporte-dl-btn:active {{
                display: block;
                width: 100%;
                box-sizing: border-box;
                background: #ffffff;
                color: #000000;
                padding: 0.55rem 0.85rem;
                border-radius: 6px;
                font-weight: 700;
                font-size: 1.05rem;
                text-decoration: none;
                text-align: center;
                line-height: 1.35;
            }}
            .reporte-dl-btn:hover {{
                background: #eafaf1;
            }}
        </style>
        </head>
        <body>
        <div class="reporte-dl-box">
            <a class="reporte-dl-btn"
               href="data:{mime_type};base64,{archivo_b64}"
               download="{nombre_seguro}">
                {etiqueta_segura}
            </a>
        </div>
        </body>
        </html>
        """,
        height=altura,
    )
