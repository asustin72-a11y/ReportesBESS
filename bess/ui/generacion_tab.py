"""Pestaña Generación: gráfica y resumen por periodo horario."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bess.config import rutas as rutas_mod
from bess.config.subestaciones import (
    recurso_generacion_subestacion,
    subestacion_por_id,
)
from bess.config.theme import COLORES
from bess.cfe.periods import obtener_periodo_por_fecha_hora
from bess.core.numbers import fmt_kwh, sumar_energia
from bess.data.aggregates.generacion import ruta_energia_generacion_por_dia
from bess.charts.layout import _titulo_y_leyenda_externos
from bess.ui.components import section_header

_COLORES_PERIODO_RGBA = {
    "Base": "rgba(52,152,219,1)",
    "Intermedio": "rgba(241,196,15,1)",
    "Punta": "rgba(231,76,60,1)",
}

_FILL_PERIODO_RGBA = {
    "Base": "rgba(52,152,219,0.14)",
    "Intermedio": "rgba(241,196,15,0.18)",
    "Punta": "rgba(231,76,60,0.14)",
}

_COLS_PERIODO = [
    ("BASE_REC", "Base"),
    ("INTERMEDIO_REC", "Intermedio"),
    ("PUNTA_REC", "Punta"),
]


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

def _cargar_generacion_diaria(sub_id: str) -> pd.DataFrame | None:
    ruta = ruta_energia_generacion_por_dia(sub_id)
    if not ruta.exists():
        return None
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    if "FECHA" not in df.columns:
        return None
    df["FECHA_DT"] = pd.to_datetime(df["FECHA"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["FECHA_DT"])
    for col, _ in _COLS_PERIODO:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0.0
    df["TOTAL"] = sum(df[c] for c, _ in _COLS_PERIODO)
    return df.sort_values("FECHA_DT").reset_index(drop=True)


def _cargar_combinado_minuto(sub_id: str, prefijo_reporte: str) -> pd.DataFrame | None:
    """Carga COMBINADO_POR_MINUTO_{prefijo}.csv (resolución 5 min)."""
    nombre = f"COMBINADO_POR_MINUTO_{prefijo_reporte}.csv"
    ruta = rutas_mod.ruta_reporte(sub_id, nombre)
    if not ruta.exists():
        return None
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    if "FECHA_HORA" not in df.columns or "KWH_REC" not in df.columns:
        return None
    df["DATETIME"] = pd.to_datetime(df["FECHA_HORA"], format="%d/%m/%Y %H:%M", errors="coerce")
    df = df.dropna(subset=["DATETIME"])
    df["KWH_REC"] = pd.to_numeric(df["KWH_REC"], errors="coerce").fillna(0)
    df["KW"] = df["KWH_REC"] * 12
    return df.sort_values("DATETIME").reset_index(drop=True)


def _filtrar_rango(df: pd.DataFrame, inicio, fin) -> pd.DataFrame:
    mask = (df["FECHA_DT"].dt.date >= inicio) & (df["FECHA_DT"].dt.date <= fin)
    return df[mask].copy()


def _filtrar_dia_minuto(df: pd.DataFrame, fecha) -> pd.DataFrame:
    mask = df["DATETIME"].dt.date == fecha
    return df[mask].copy()


# ---------------------------------------------------------------------------
# Gráficas
# ---------------------------------------------------------------------------

def _grafica_barras_rango(df: pd.DataFrame, etiqueta: str) -> go.Figure:
    fig = go.Figure()
    for col, nombre in _COLS_PERIODO:
        fig.add_trace(go.Bar(
            x=df["FECHA_DT"],
            y=df[col],
            name=nombre,
            marker_color=_COLORES_PERIODO_RGBA[nombre],
        ))
    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(etiqueta, font_size=14)
    fig.update_layout(
        barmode="stack",
        xaxis_title="Fecha",
        yaxis_title="kWh",
        title=title_cfg,
        legend=legend_cfg,
        margin=dict(l=40, r=20, t=margin_t, b=60),
        height=380,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _grafica_linea_dia(df_min: pd.DataFrame, etiqueta: str) -> go.Figure:
    """Perfil intradiario de generación (kW) con go.Scatter por periodo."""
    periodos = df_min["FECHA_HORA"].apply(obtener_periodo_por_fecha_hora)

    fig = go.Figure()
    for periodo in ("Base", "Intermedio", "Punta"):
        mask = periodos == periodo
        if not mask.any():
            continue
        seg = df_min[mask]
        fig.add_trace(go.Scatter(
            x=seg["DATETIME"],
            y=seg["KW"],
            mode="lines",
            name=periodo,
            line=dict(color=_COLORES_PERIODO_RGBA[periodo], width=2),
            fill="tozeroy",
            fillcolor=_FILL_PERIODO_RGBA[periodo],
        ))

    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(etiqueta, font_size=14)
    fig.update_layout(
        title=title_cfg,
        xaxis_title="Hora",
        yaxis_title="kW",
        legend=legend_cfg,
        margin=dict(l=40, r=20, t=margin_t, b=60),
        height=380,
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------

def _tabla_resumen_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Acumulado por mes y periodo."""
    df = df.copy()
    df["MES"] = df["FECHA_DT"].dt.to_period("M")
    filas: list[dict] = []
    for mes, grp in df.groupby("MES"):
        fila: dict = {"Mes": str(mes)}
        total = 0.0
        for col, nombre in _COLS_PERIODO:
            val = float(grp[col].sum())
            fila[nombre] = val
            total += val
        fila["Total"] = total
        filas.append(fila)
    if not filas:
        return pd.DataFrame()
    out = pd.DataFrame(filas)
    for col_num in ["Base", "Intermedio", "Punta", "Total"]:
        if col_num in out.columns:
            out[col_num] = out[col_num].map(lambda v: f"{v:,.1f}")
    return out


def _tabla_resumen_dia(df_dia: pd.DataFrame) -> pd.DataFrame:
    """Resumen de un solo día: kWh por periodo."""
    fila: dict = {}
    total = 0.0
    for col, nombre in _COLS_PERIODO:
        val = float(df_dia[col].sum()) if col in df_dia.columns else 0.0
        fila[nombre] = f"{val:,.1f}"
        total += val
    fila["Total"] = f"{total:,.1f}"
    return pd.DataFrame([fila])


# ---------------------------------------------------------------------------
# Tarjetas métricas
# ---------------------------------------------------------------------------

def _render_metricas(df: pd.DataFrame):
    total_kwh = sumar_energia(df["TOTAL"])
    cols_met = st.columns(4)
    datos = [
        ("Base", "BASE_REC", _COLORES_PERIODO_RGBA["Base"]),
        ("Intermedio", "INTERMEDIO_REC", _COLORES_PERIODO_RGBA["Intermedio"]),
        ("Punta", "PUNTA_REC", _COLORES_PERIODO_RGBA["Punta"]),
        ("Total", "TOTAL", "rgba(25,118,210,1)"),
    ]
    for col_st, (label, col_df, color) in zip(cols_met, datos):
        val = fmt_kwh(sumar_energia(df[col_df])) if col_df != "TOTAL" else fmt_kwh(total_kwh)
        with col_st:
            st.markdown(
                f'<div class="metric-card" style="border-top:3px solid {color}">'
                f'<div class="label">{label}</div>'
                f'<div class="value">{val}</div>'
                f'<div class="sub">kWh</div></div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Tab principal
# ---------------------------------------------------------------------------

def tab_generacion(sub_id: str | None = None):
    """Pestaña Generación para la subestación seleccionada."""
    if sub_id is None:
        sub_id = st.session_state.get("subestacion_principal", "")

    sub = subestacion_por_id(sub_id)
    if sub is None:
        st.warning("Subestación no encontrada.")
        return

    rec = recurso_generacion_subestacion(sub.id)
    if rec is None:
        st.info(f"{sub.nombre} no tiene recurso de generación configurado.")
        return

    df = _cargar_generacion_diaria(sub.id)
    if df is None or df.empty:
        st.warning("No hay datos de generación. Ejecute Verificar → Filtrar → Reportes.")
        return

    fecha_min_global = df["FECHA_DT"].min().date()
    fecha_max_global = df["FECHA_DT"].max().date()
    fecha_def = min(datetime.now().date() - timedelta(days=1), fecha_max_global)
    fecha_def = max(fecha_def, fecha_min_global)

    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            fecha_inicio = st.date_input(
                "Desde",
                fecha_def,
                min_value=fecha_min_global,
                max_value=fecha_max_global,
                key="gen_desde",
            )
        with col2:
            fecha_fin = st.date_input(
                "Hasta",
                fecha_def,
                min_value=fecha_min_global,
                max_value=fecha_max_global,
                key="gen_hasta",
            )
        with col3:
            dias = (fecha_fin - fecha_inicio).days + 1
            st.metric("Días", dias)

    if fecha_fin < fecha_inicio:
        st.warning("La fecha final debe ser posterior o igual a la inicial.")
        return

    es_dia_unico = fecha_inicio == fecha_fin

    df_rango = _filtrar_rango(df, fecha_inicio, fecha_fin)
    if df_rango.empty:
        st.info("Sin datos en el rango seleccionado.")
        return

    with st.container(border=True):
        fecha_str = fecha_inicio.strftime("%d/%m/%Y") if es_dia_unico else ""
        titulo = (
            f"{rec.etiqueta} · {sub.nombre} · {fecha_str}"
            if es_dia_unico
            else f"{rec.etiqueta} · {sub.nombre}"
        )
        section_header(titulo)

        _render_metricas(df_rango)

        if es_dia_unico:
            df_min = _cargar_combinado_minuto(sub.id, rec.prefijo_reporte)
            if df_min is not None:
                df_min_dia = _filtrar_dia_minuto(df_min, fecha_inicio)
                if not df_min_dia.empty:
                    fig = _grafica_linea_dia(
                        df_min_dia,
                        f"{rec.etiqueta} — Perfil de generación (kW)",
                    )
                    st.plotly_chart(fig, use_container_width=True, key=f"gen_line_{sub.id}", theme=None)
                else:
                    st.info("Sin datos de perfil intradiario para este día.")
            else:
                st.info("Sin archivo de perfil por minuto. Ejecute Reportes.")

            section_header("Resumen del día", compact=True)
            df_tabla = _tabla_resumen_dia(df_rango)
            st.dataframe(df_tabla, use_container_width=True, hide_index=True)
        else:
            fig = _grafica_barras_rango(df_rango, f"{rec.etiqueta} — kWh por día y periodo")
            st.plotly_chart(fig, use_container_width=True, key=f"gen_bar_{sub.id}", theme=None)

            section_header("Acumulado mensual por periodo", compact=True)
            df_tabla = _tabla_resumen_mes(df_rango)
            if df_tabla.empty:
                st.info("Sin datos para la tabla.")
            else:
                st.dataframe(df_tabla, use_container_width=True, hide_index=True)
