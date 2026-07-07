"""Sección Reportes: diario y acumulado."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from bess.charts.profile import graficar_perfil
from bess.config.subestaciones import ruta_combinado_por_prefijo, subestacion_por_prefijo
from bess.reports.dia_tipo import titulo_dia_tipo
from bess.config.theme import COLORES
from bess.core.dates import mascara_rango_operativo, serie_fecha_operativa
from bess.reports.accumulated import ReporteAcumuladoError, calcular_reporte_acumulado
from bess.reports.accumulated_pdf import generar_reporte_acumulado_pdf
from bess.ui.chart_view import render_grafica_plotly
from bess.ui.components import render_selector_fecha_unica, section_header, subnav_en_panel
from bess.ui.downloads import render_boton_descarga


def _estilizar_resumen_acumulado(df: pd.DataFrame):
    texto_cols = ("Concepto",)
    styler = df.style.set_properties(
        subset=list(texto_cols),
        **{"font-weight": "500", "text-align": "left"},
    )
    styler = styler.set_properties(
        subset=["Valor"],
        **{"text-align": "right", "font-variant-numeric": "tabular-nums"},
    )
    for idx, concepto in enumerate(df["Concepto"]):
        texto = str(concepto).lower()
        if "demanda" in texto:
            styler = styler.set_properties(
                subset=pd.IndexSlice[idx, :],
                **{
                    "background-color": "#e8f4f8",
                    "font-weight": "700",
                    "color": "#1a5276",
                },
            )
    if len(df) > 0:
        styler = styler.set_properties(
            subset=pd.IndexSlice[len(df) - 1, :],
            **{
                "background-color": "#d4edda",
                "font-weight": "700",
                "border-top": "2px solid #27ae60",
            },
        )
    styler = styler.set_table_styles(
        [
            {
                "selector": "thead th",
                "props": [
                    ("background-color", "#2c3e50"),
                    ("color", "white"),
                    ("font-weight", "700"),
                    ("text-align", "center"),
                    ("padding", "8px 10px"),
                ],
            },
            {"selector": "tbody td", "props": [("padding", "8px 10px")]},
        ],
        overwrite=False,
    )
    return styler


def _tarjeta_ahorro_demanda(kw: int, mxn: float) -> str:
    return f"""
    <div class="metric-card metric-card-total" style="border-top:4px solid {COLORES['primary']};">
        <div class="total-grid">
            <div class="total-item total-item-kw">
                <div class="item-label">Reducción de demanda BESS</div>
                <div class="value">{kw:,}</div>
                <div class="unit">kW (Shapley)</div>
            </div>
            <div class="total-item total-item-mxn">
                <div class="item-label">Ahorro en demanda</div>
                <div class="value">${mxn:,.2f}</div>
                <div class="unit">MXN</div>
            </div>
        </div>
    </div>
    """


def _mtime_fuente_reporte(prefijo: str) -> float:
    ruta_p = ruta_combinado_por_prefijo(prefijo)
    return ruta_p.stat().st_mtime if ruta_p and ruta_p.exists() else 0.0


@st.cache_data(show_spinner="Generando reporte acumulado PDF...")
def _pdf_acumulado_bytes(fecha_str: str, prefijo: str, _mtime_fuente: float):
    exito, ruta = generar_reporte_acumulado_pdf(fecha_str, prefijo)
    if not exito:
        raise RuntimeError(ruta)
    with open(ruta, "rb") as f:
        return f.read(), os.path.basename(ruta)


def tab_reporte_acumulado(df, prefijo: str):
    """Vista previa y PDF del reporte acumulado mensual (ahorros BESS)."""
    if df is None or len(df) == 0:
        st.warning("No hay datos disponibles para generar reportes")
        return

    if "DATETIME" not in df.columns:
        df = df.copy()
        df["DATETIME"] = pd.to_datetime(df["FECHA_HORA"], format="%d/%m/%Y %H:%M")

    fecha_min = serie_fecha_operativa(df["DATETIME"]).min()
    fecha_max = serie_fecha_operativa(df["DATETIME"]).max()
    fecha_def = datetime.now().date() - timedelta(days=1)
    fecha_def = max(fecha_min, min(fecha_def, fecha_max))

    sub = subestacion_por_prefijo(prefijo)
    sub_label = sub.nombre.replace("Subestación ", "") if sub else prefijo

    fecha_corte = render_selector_fecha_unica(
        "Reporte acumulado",
        "Ahorros del BESS del día 1 del mes a la fecha de corte: operación, arbitraje "
        "y reducción de capacidad atribuida al BESS (Shapley).",
        "Fecha de corte",
        fecha_def,
        fecha_min,
        fecha_max,
        key=f"fecha_reporte_acum_{prefijo}",
    )

    fecha_str = fecha_corte.strftime("%d/%m/%Y")
    mes_label = fecha_corte.strftime("%m/%Y")

    try:
        datos = calcular_reporte_acumulado(prefijo, fecha_corte)
    except ReporteAcumuladoError as exc:
        st.warning(str(exc))
        return

    section_header(
        f"Reporte acumulado BESS · {sub_label} · {mes_label}",
        f"Del 01/{mes_label} al {fecha_str} ({datos['dias']} días).",
    )

    if datos["shapley_error"]:
        st.caption(f"Shapley capacidad: {datos['shapley_error']}")

    if datos["shapley_disponible"]:
        with st.container(border=True):
            section_header(
                "Ahorro en demanda (capacidad BESS)",
                "Atribución Shapley del BESS al mes de corte.",
                compact=True,
            )
            st.markdown(
                _tarjeta_ahorro_demanda(datos["shapley_bess_kw"], datos["shapley_bess_mxn"]),
                unsafe_allow_html=True,
            )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['carga']};">
                <div class="label">Energía cargada</div>
                <div class="value">{datos['carga_total_kwh']:,}</div>
                <div class="sub">kWh acumulados</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['descarga']};">
                <div class="label">Energía descargada</div>
                <div class="value">{datos['descarga_total_kwh']:,}</div>
                <div class="sub">kWh acumulados</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['warning']};">
                <div class="label">Ahorro por arbitraje</div>
                <div class="value">${datos['arbitraje_mxn']:,.2f}</div>
                <div class="sub">MXN acumulado</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top:3px solid {COLORES['success']};">
                <div class="label">Ahorro total del mes</div>
                <div class="value">${datos['ahorro_total_mxn']:,.2f}</div>
                <div class="sub">Arbitraje + demanda</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    dia_tipo = datos.get("dia_tipo")
    if dia_tipo:
        df_dia = df[mascara_rango_operativo(df, dia_tipo["fecha"], dia_tipo["fecha"])].copy()
        if not df_dia.empty:
            gen_txt = " · incluye generación" if dia_tipo.get("incluye_generacion") else ""
            with st.container(border=True):
                section_header(
                    titulo_dia_tipo(prefijo),
                    f"{dia_tipo['dia_semana']} {dia_tipo['fecha_str']} · "
                    f"Carga {dia_tipo['carga_kwh']:,} kWh · "
                    f"Descarga {dia_tipo['descarga_kwh']:,} kWh{gen_txt}.",
                    compact=True,
                )
                fig = graficar_perfil(
                    df_dia,
                    prefijo,
                    titulo_dia_tipo(prefijo),
                )
                render_grafica_plotly(
                    fig,
                    f"reporte_acum_dia_tipo_{prefijo}_{dia_tipo['fecha']:%Y%m%d}.png",
                    download_key=f"dl_acum_dia_tipo_{prefijo}_{dia_tipo['fecha']:%Y%m%d}",
                )
        else:
            st.caption(f"No hay perfil minuto a minuto para el Día Tipo ({dia_tipo['fecha_str']}).")
    else:
        st.caption(
            "No se encontró un martes, miércoles o jueves anterior con carga y descarga BESS "
            "para el Día Tipo."
        )

    with st.container(border=True):
        section_header("Resumen de ahorros", compact=True)
        st.dataframe(
            _estilizar_resumen_acumulado(datos["tabla_resumen"]),
            use_container_width=True,
            hide_index=True,
        )

    with st.container(border=True):
        section_header("Arbitraje por periodo", compact=True)
        arb = datos["arbitraje"]
        c_a1, c_a2, c_a3, c_a4 = st.columns(4)
        for i, (periodo, valor) in enumerate(
            [
                ("Base", arb["base"]),
                ("Intermedio", arb["intermedio"]),
                ("Punta", arb["punta"]),
                ("Total", datos["arbitraje_mxn"]),
            ]
        ):
            with [c_a1, c_a2, c_a3, c_a4][i]:
                es_total = periodo == "Total"
                color = COLORES["primary"] if es_total else COLORES["success"]
                st.markdown(
                    f"""
                    <div class="metric-card" style="border-top:3px solid {color};">
                        <div class="label">{'Arbitraje ' + periodo if not es_total else 'Arbitraje total'}</div>
                        <div class="value">${valor:,.2f}</div>
                        <div class="sub">MXN</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    try:
        pdf_bytes, pdf_name = _pdf_acumulado_bytes(
            fecha_str, prefijo, _mtime_fuente_reporte(prefijo)
        )
        render_boton_descarga(
            pdf_bytes,
            pdf_name,
            mime_type="application/pdf",
            etiqueta="Generar Reporte Acumulado",
        )
    except RuntimeError as e:
        st.error(f"Error al generar el reporte: {e}")


def tab_reportes(df, prefijo: str, tab_diario_fn: Callable):
    """Pestañas Reporte diario y Reporte acumulado."""
    vista = subnav_en_panel(
        "Tipo de reporte",
        [("diario", "Reporte diario"), ("acum", "Reporte acumulado")],
        f"reportes_vista_{prefijo}",
    )
    if vista == "diario":
        tab_diario_fn(df, prefijo)
    elif vista == "acum":
        tab_reporte_acumulado(df, prefijo)
