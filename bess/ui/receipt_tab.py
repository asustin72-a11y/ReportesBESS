"""Pestaña Recibo (Streamlit)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from bess.cfe.capacity import calcular_criterio_cfe
from bess.cfe.daily_data import energia_diaria_tiene_sin_bess
from bess.cfe.energy_month import calcular_costo_energia_mes
from bess.cfe.receipt import (
    construir_datos_recibo_cfe,
    generar_recibo_pdf_bytes,
    nombre_archivo_recibo,
    render_html_recibo_cfe,
)
from bess.cfe.report_data import acumulados_tiene_demanda_sin_bess
from bess.cfe.receipt.css import css_recibo_cfe
from bess.tariffs.loader import cargar_tarifas
from bess.ui.components import render_selector_fecha_unica


def _inyectar_css_recibo():
    st.markdown(f"<style>{css_recibo_cfe()}</style>", unsafe_allow_html=True)


def render_recibo_escenario(fecha, prefijo, con_bess, tarifas, descargar_fn):
    escenario = "Con BESS" if con_bess else "Sin BESS"
    mes_label = fecha.strftime("%m/%Y")

    res_energia = calcular_costo_energia_mes(fecha, prefijo, con_bess=con_bess, tarifas=tarifas)
    if res_energia is None:
        st.warning(f"No hay datos de energía acumulada para {mes_label} ({escenario}).")
        return

    res_cfe = calcular_criterio_cfe(fecha, prefijo, con_bess=con_bess, tarifas=tarifas)
    datos = construir_datos_recibo_cfe(
        fecha, prefijo, con_bess, res_energia, res_cfe, tarifas
    )

    with st.container(border=False):
        st.markdown(render_html_recibo_cfe(datos), unsafe_allow_html=True)
        pdf_name = nombre_archivo_recibo(fecha, prefijo, con_bess)
        try:
            pdf_bytes = generar_recibo_pdf_bytes(datos)
        except Exception as exc:
            st.error(
                "No se pudo generar el PDF del recibo. "
                "La vista en pantalla sigue disponible."
            )
            st.caption(str(exc))
        else:
            descargar_fn(
                pdf_bytes,
                pdf_name,
                mime_type="application/pdf",
                etiqueta="Descargar recibo",
            )


def tab_recibo(df, prefijo, descargar_fn):
    """Recibo estimado con/sin BESS para el mes al día seleccionado."""
    _inyectar_css_recibo()
    if df is None or len(df) == 0:
        st.warning("No hay datos disponibles")
        return

    if "DATETIME" not in df.columns:
        df = df.copy()
        df["DATETIME"] = pd.to_datetime(df["FECHA_HORA"], format="%d/%m/%Y %H:%M")

    fecha_min = df["DATETIME"].min().date()
    fecha_max = df["DATETIME"].max().date()
    fecha_def = datetime.now().date() - timedelta(days=1)
    fecha_def = max(fecha_min, min(fecha_def, fecha_max))

    fecha_sel = render_selector_fecha_unica(
        "Recibo",
        "Fecha de corte para el acumulado mensual del recibo estimado.",
        "Fecha de corte",
        fecha_def,
        fecha_min,
        fecha_max,
        key=f"fecha_recibo_{prefijo}",
    )

    tarifas = cargar_tarifas()
    tab_sin, tab_con = st.tabs(["Sin BESS", "Con BESS"])

    with tab_sin:
        if not energia_diaria_tiene_sin_bess(prefijo):
            st.warning(
                "No hay columnas sin BESS en ENERGIA_*_POR_DIA.csv. "
                "Procesa los datos desde el panel de administración."
            )
        else:
            render_recibo_escenario(
                fecha_sel, prefijo, con_bess=False, tarifas=tarifas, descargar_fn=descargar_fn
            )

    with tab_con:
        render_recibo_escenario(
            fecha_sel, prefijo, con_bess=True, tarifas=tarifas, descargar_fn=descargar_fn
        )
