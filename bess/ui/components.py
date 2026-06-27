"""Componentes reutilizables de la UI Streamlit."""

from __future__ import annotations

import base64
import os

import streamlit as st

from bess.config.paths import DIRECTORIO_BASE


def section_header(titulo, descripcion="", compact=False):
    cls = "section-title-sm" if compact else "section-title"
    html = f'<p class="{cls}">{titulo}</p>'
    if descripcion:
        html += f'<p class="section-desc">{descripcion}</p>'
    st.markdown(html, unsafe_allow_html=True)


def metric_compact(label, value):
    st.markdown(
        f'<div class="metric-compact"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def html_tarifas_sidebar(tarifas, mes):
    items = [
        ("Base", f"${tarifas.get('Base', {}).get(mes, 0):.4f}"),
        ("Intermedio", f"${tarifas.get('Intermedio', {}).get(mes, 0):.4f}"),
        ("Punta", f"${tarifas.get('Punta', {}).get(mes, 0):.4f}"),
        ("Capacidad", f"${tarifas.get('Capacidad', {}).get(mes, 0):,.2f}"),
    ]
    celdas = "".join(
        f'<div class="sidebar-tarifa-item"><div class="label">{lbl}</div>'
        f'<div class="value">{val}</div></div>'
        for lbl, val in items
    )
    return f'<div class="sidebar-tarifas-grid">{celdas}</div>'


def render_selector_fecha_unica(
    titulo, descripcion, label, fecha_def, fecha_min, fecha_max, key,
    metric_label=None, metric_fn=None,
):
    """Panel compacto con un solo date_input y métrica auxiliar opcional."""
    with st.container(border=True):
        st.markdown(
            '<span class="panel-fecha-unica-anchor" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        section_header(titulo, descripcion, compact=True)
        if metric_label and metric_fn:
            col_fecha, col_info = st.columns([3, 1])
            with col_fecha:
                fecha = st.date_input(
                    label, value=fecha_def, min_value=fecha_min, max_value=fecha_max, key=key,
                )
            with col_info:
                metric_compact(metric_label, metric_fn(fecha))
        else:
            fecha = st.date_input(
                label, value=fecha_def, min_value=fecha_min, max_value=fecha_max, key=key,
            )
    return fecha


def obtener_logo_html(width=110):
    logo_path = os.path.join(DIRECTORIO_BASE, "Logo IUSASOL.png")
    if not os.path.exists(logo_path):
        logo_path = os.path.join(DIRECTORIO_BASE, "LogoIUSASOL.png")
    if not os.path.exists(logo_path):
        return ""
    with open(logo_path, "rb") as logo_file:
        logo_b64 = base64.b64encode(logo_file.read()).decode()
    mime = "image/png" if logo_path.lower().endswith(".png") else "image/jpeg"
    return (
        f'<img src="data:{mime};base64,{logo_b64}" width="{width}" '
        f'alt="IUSASOL" style="display:block;" />'
    )
