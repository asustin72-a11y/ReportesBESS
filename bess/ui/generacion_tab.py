"""Pestaña Generación: gráfica y resumen por periodo horario."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bess.config import rutas as rutas_mod
from bess.config.subestaciones import (
    recursos_generacion_subestacion,
    subestacion_por_id,
)
from bess.cfe.periods import periodo_por_fecha_hora
from bess.config.esquema_tarifa import esquema_tarifa_prefijo, esquema_tarifa_subestacion
from bess.core.numbers import fmt_kwh, sumar_energia
from bess.data.aggregates.generacion import ruta_energia_generacion_por_dia
from bess.charts.layout import _titulo_y_leyenda_externos, color_periodo
from bess.charts.trends import graficar_energia_diaria_por_periodo
from bess.config.theme import COLORES, PERIODO_BG
from bess.ui.chart_view import render_grafica_plotly
from bess.ui.components import section_header

_COLS_PERIODO = [
    ("BASE_REC", "Base"),
    ("INTERMEDIO_REC", "Intermedio"),
    ("PUNTA_REC", "Punta"),
]


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

def _cargar_generacion_diaria(sub_id: str, prefijo: str | None = None) -> pd.DataFrame | None:
    """Diario agregado de la subestación, o diario de un medidor (`ENERGIA_{prefijo}`)."""
    if prefijo:
        ruta = rutas_mod.ruta_energia_por_dia(prefijo, sub_id)
    else:
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


def _sumar_combinados_minuto(sub_id: str, prefijos: list[str]) -> pd.DataFrame | None:
    """Suma KWH_REC/KW de varios COMBINADO_POR_MINUTO por FECHA_HORA."""
    acumulado: pd.DataFrame | None = None
    for prefijo in prefijos:
        df = _cargar_combinado_minuto(sub_id, prefijo)
        if df is None or df.empty:
            continue
        parte = df[["FECHA_HORA", "DATETIME", "KWH_REC", "KW"]].copy()
        if acumulado is None:
            acumulado = parte
            continue
        merged = acumulado.merge(
            parte[["FECHA_HORA", "KWH_REC", "KW"]],
            on="FECHA_HORA",
            how="outer",
            suffixes=("_a", "_b"),
        )
        out = pd.DataFrame({
            "FECHA_HORA": merged["FECHA_HORA"],
            "KWH_REC": merged["KWH_REC_a"].fillna(0) + merged["KWH_REC_b"].fillna(0),
            "KW": merged["KW_a"].fillna(0) + merged["KW_b"].fillna(0),
        })
        out["DATETIME"] = pd.to_datetime(
            out["FECHA_HORA"], format="%d/%m/%Y %H:%M", errors="coerce"
        )
        acumulado = out.dropna(subset=["DATETIME"]).sort_values("DATETIME").reset_index(drop=True)
    return acumulado


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
    return graficar_energia_diaria_por_periodo(df, etiqueta)


def _serie_kw_periodo_con_ceros(
    datetimes: pd.Series,
    kw: pd.Series,
    activo: pd.Series,
) -> tuple[list, list]:
    """kW del periodo activo y 0 fuera, con bordes verticales (sin cruce en X).

    En el cambio de horario TOU se inserta un punto extra en el mismo instante
    (valor→0 o 0→valor) para que la bajada/subida sea vertical y no diagonal
    contra la serie del periodo siguiente.
    """
    xs: list = []
    ys: list = []
    prev_on = False
    dt_arr = datetimes.to_numpy()
    kw_arr = kw.to_numpy(dtype=float)
    on_arr = activo.to_numpy(dtype=bool)

    for i in range(len(on_arr)):
        t = dt_arr[i]
        v = float(kw_arr[i])
        on = bool(on_arr[i])
        if on:
            if not prev_on:
                # Subida vertical en el primer instante del periodo.
                xs.append(t)
                ys.append(0.0)
            xs.append(t)
            ys.append(v)
            prev_on = True
        else:
            if prev_on:
                # Bajada vertical en el último instante activo (no diagonal).
                xs.append(dt_arr[i - 1])
                ys.append(0.0)
            xs.append(t)
            ys.append(0.0)
            prev_on = False
    return xs, ys


def _grafica_linea_dia(df_min: pd.DataFrame, etiqueta: str, esquema_tarifa_id: str) -> go.Figure:
    """Perfil intradiario de generación (kW) con go.Scatter por periodo.

    Cada serie usa toda la línea temporal: kW activo y 0 fuera. En los bordes
    TOU la transición es vertical (mismo instante) para no cruzarse en X con
    el periodo siguiente, y sin diagonal que salte el hueco de punta.
    """
    plot = df_min.copy()
    if "DATETIME" not in plot.columns:
        plot["DATETIME"] = pd.to_datetime(
            plot["FECHA_HORA"], format="%d/%m/%Y %H:%M", errors="coerce"
        )
    plot = plot.dropna(subset=["DATETIME"]).sort_values("DATETIME")
    plot["KW"] = pd.to_numeric(plot["KW"], errors="coerce").fillna(0.0)
    plot["PERIODO"] = plot["FECHA_HORA"].map(
        lambda fh: periodo_por_fecha_hora(fh, esquema_tarifa_id)
    )

    fig = go.Figure()
    for periodo in ("Base", "Intermedio", "Punta"):
        mask = plot["PERIODO"] == periodo
        if not bool(mask.any()):
            continue
        if float(plot.loc[mask, "KW"].max()) <= 0:
            continue
        xs, ys = _serie_kw_periodo_con_ceros(plot["DATETIME"], plot["KW"], mask)
        color = color_periodo(periodo)
        fig.add_trace(go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            name=periodo,
            line=dict(color=color, width=2, shape="linear"),
            fill="tozeroy",
            fillcolor=PERIODO_BG.get(periodo, "rgba(149,165,166,0.14)"),
            connectgaps=False,
            hovertemplate=(
                f"<b>{periodo}</b><br>%{{x|%H:%M}}<br>%{{y:,.0f}} kW<extra></extra>"
            ),
        ))

    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(etiqueta)
    fig.update_layout(
        title=title_cfg,
        xaxis_title="Hora",
        yaxis_title="Potencia (kW)",
        height=420,
        hovermode="x unified",
        legend=legend_cfg,
        margin=dict(l=52, r=52, t=margin_t, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(tickformat="%H:%M", dtick=7200000, gridcolor="#eef2f6")
    fig.update_yaxes(
        tickformat=",.0f",
        gridcolor="#eef2f6",
        zeroline=True,
        zerolinecolor="#95a5a6",
        zerolinewidth=1,
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
        fila = _fila_kwh_por_periodo(grp, str(mes))
        fila["Mes"] = fila.pop("Concepto")
        filas.append(fila)
    if not filas:
        return pd.DataFrame()
    cols = ["Mes", "Base (kWh)", "Intermedio (kWh)", "Punta (kWh)", "Total (kWh)"]
    return pd.DataFrame(filas)[cols]


def _fila_kwh_por_periodo(df_slice: pd.DataFrame, concepto: str) -> dict:
    fila: dict = {"Concepto": concepto}
    total = 0.0
    for col, nombre in _COLS_PERIODO:
        if df_slice.empty or col not in df_slice.columns:
            val = 0.0
        else:
            val = float(df_slice[col].sum())
        fila[f"{nombre} (kWh)"] = f"{val:,.1f}"
        total += val
    fila["Total (kWh)"] = f"{total:,.1f}"
    return fila


def _tabla_resumen_dia(df: pd.DataFrame, fecha) -> pd.DataFrame:
    """Diario de la fecha seleccionada y acumulado del mes hasta esa fecha."""
    fecha_txt = fecha.strftime("%d/%m/%Y")
    df_dia = df[df["FECHA_DT"].dt.date == fecha]
    mask_acum = (
        (df["FECHA_DT"].dt.year == fecha.year)
        & (df["FECHA_DT"].dt.month == fecha.month)
        & (df["FECHA_DT"].dt.date <= fecha)
    )
    df_acum = df[mask_acum]
    return pd.DataFrame([
        _fila_kwh_por_periodo(df_dia, f"Día {fecha_txt}"),
        _fila_kwh_por_periodo(df_acum, f"Acumulado al {fecha_txt}"),
    ])


# ---------------------------------------------------------------------------
# Tarjetas métricas
# ---------------------------------------------------------------------------

def _render_metricas(df: pd.DataFrame):
    total_kwh = sumar_energia(df["TOTAL"])
    cols_met = st.columns(4)
    datos = [
        ("Base", "BASE_REC", color_periodo("Base")),
        ("Intermedio", "INTERMEDIO_REC", color_periodo("Intermedio")),
        ("Punta", "PUNTA_REC", color_periodo("Punta")),
        ("Total", "TOTAL", COLORES["primary"]),
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

    recursos = recursos_generacion_subestacion(sub.id)
    if not recursos:
        st.info(f"{sub.nombre} no tiene recurso de generación configurado.")
        return

    opciones = ["Total"] + [r.prefijo_reporte for r in recursos]
    etiquetas = {
        "Total": "Total",
        **{r.prefijo_reporte: r.etiqueta for r in recursos},
    }
    if len(recursos) == 1:
        seleccion = recursos[0].prefijo_reporte
        etiqueta_vista = recursos[0].etiqueta
    else:
        seleccion = st.selectbox(
            "Medidor",
            opciones,
            format_func=lambda x: etiquetas.get(x, x),
            key=f"gen_medidor_{sub.id}",
        )
        etiqueta_vista = etiquetas.get(seleccion, seleccion)

    if seleccion == "Total":
        df = _cargar_generacion_diaria(sub.id)
        prefijos_perfil = [r.prefijo_reporte for r in recursos]
    else:
        df = _cargar_generacion_diaria(sub.id, seleccion)
        if df is None:
            # Fallback al agregado si aún no hay diario por medidor.
            df = _cargar_generacion_diaria(sub.id)
        prefijos_perfil = [seleccion]

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
            f"{etiqueta_vista} · {sub.nombre} · {fecha_str}"
            if es_dia_unico
            else f"{etiqueta_vista} · {sub.nombre}"
        )
        section_header(titulo)

        _render_metricas(df_rango)

        if es_dia_unico:
            if len(prefijos_perfil) == 1:
                df_min = _cargar_combinado_minuto(sub.id, prefijos_perfil[0])
            else:
                df_min = _sumar_combinados_minuto(sub.id, prefijos_perfil)
            if df_min is not None:
                df_min_dia = _filtrar_dia_minuto(df_min, fecha_inicio)
                if not df_min_dia.empty:
                    fig = _grafica_linea_dia(
                        df_min_dia,
                        f"{etiqueta_vista} — Perfil de generación (kW)",
                        sub.esquema_tarifa_id,
                    )
                    render_grafica_plotly(
                        fig,
                        f"generacion_perfil_{sub.id}.png",
                        download_key=f"gen_line_{sub.id}",
                    )
                else:
                    st.info("Sin datos de perfil intradiario para este día.")
            else:
                st.info("Sin archivo de perfil por minuto. Ejecute Reportes.")

            section_header("Resumen del día", compact=True)
            df_tabla = _tabla_resumen_dia(df, fecha_inicio)
            st.dataframe(df_tabla, use_container_width=True, hide_index=True)
        else:
            fig = _grafica_barras_rango(
                df_rango, f"{etiqueta_vista} — kWh por día y periodo"
            )
            render_grafica_plotly(
                fig,
                f"generacion_barras_{sub.id}.png",
                download_key=f"gen_bar_{sub.id}",
            )

            section_header("Acumulado mensual por periodo", compact=True)
            df_tabla = _tabla_resumen_mes(df_rango)
            if df_tabla.empty:
                st.info("Sin datos para la tabla.")
            else:
                st.dataframe(df_tabla, use_container_width=True, hide_index=True)
