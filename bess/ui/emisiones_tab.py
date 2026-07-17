"""Pestaña Emisiones CO₂ (Streamlit)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bess.charts.layout import _titulo_y_leyenda_externos
from bess.cfe.emisiones import (
    CITA_FACTORES_EMISION,
    EF_GAS_PLANO_KG_KWH,
    FACTORES_EMISION,
    calcular_huella_carbono_mes,
)
from bess.config.theme import COLORES
from bess.reports.emisiones_pdf import generar_emisiones_pdf_bytes, nombre_archivo_emisiones
from bess.ui.chart_view import render_grafica_plotly
from bess.ui.components import render_selector_fecha_unica, section_header

# Subíndice Unicode (st.metric / Plotly / dataframes no renderizan HTML).
_CO2 = "CO₂"

_COLOR_CON = COLORES.get("secondary", "#2e86c1")
_COLOR_SIN = COLORES.get("punta", "#e74c3c")
_COLOR_GEN = COLORES.get("carga", "#2ecc71")


def _layout_grafica_emisiones(*, title: str, yaxis_title: str, height: int = 380, showlegend: bool = True) -> dict:
    """Título y leyenda separados en el margen superior."""
    title_cfg, legend_cfg, margin_t = _titulo_y_leyenda_externos(
        title,
        show_legend=showlegend,
    )
    layout = dict(
        title=title_cfg,
        yaxis_title=yaxis_title,
        margin=dict(t=margin_t, b=44, l=54, r=24),
        height=height,
        showlegend=showlegend,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    if showlegend and legend_cfg is not None:
        layout["legend"] = legend_cfg
    return layout


def _fmt_kwh(v: float) -> str:
    return f"{v:,.0f}"


def _fmt_t(v: float | None, *, con_signo: bool = False) -> str:
    if v is None:
        return "—"
    if con_signo and v > 0:
        return f"+{v:,.2f}"
    return f"{v:,.2f}"


def _fmt_pct(v: float | None, *, con_signo: bool = False) -> str:
    if v is None:
        return "—"
    if con_signo and v > 0:
        return f"+{v:,.2f}%"
    return f"{v:,.2f}%"


def _delta_ahorro(ahorro: float | None, pct: float | None = None) -> str | None:
    if ahorro is None:
        return None
    pct_txt = f" ({_fmt_pct(pct)})" if pct is not None else ""
    if abs(ahorro) < 0.005:
        return f"casi neutro{pct_txt}"
    if ahorro > 0:
        return f"-{_fmt_t(ahorro)} t{pct_txt} vs Sin BESS"
    return f"+{_fmt_t(abs(ahorro))} t{pct_txt} vs Sin BESS (empeora)"


def _grafica_co2_comparacion(datos: dict) -> go.Figure:
    periodos = [f["etiqueta"] for f in datos["por_periodo"]]
    con = [f["co2_con_t"] for f in datos["por_periodo"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Con BESS", x=periodos, y=con, marker_color=_COLOR_CON))
    if datos.get("tiene_sin_bess"):
        sin = [f.get("co2_sin_t", 0) for f in datos["por_periodo"]]
        fig.add_trace(go.Bar(name="Sin BESS", x=periodos, y=sin, marker_color=_COLOR_SIN))
    fig.update_layout(
        barmode="group",
        **_layout_grafica_emisiones(
            title="Emisiones por periodo: Con BESS vs Sin BESS",
            yaxis_title=f"t {_CO2}",
            height=380,
        ),
    )
    return fig


def _grafica_totales_comparacion(datos: dict) -> go.Figure:
    if datos.get("tiene_sin_bess"):
        labels = ["Sin BESS", "Con BESS"]
        vals = [datos.get("co2_sin_t") or 0, datos["co2_con_t"]]
        colors = [_COLOR_SIN, _COLOR_CON]
    else:
        labels = ["Con BESS"]
        vals = [datos["co2_con_t"]]
        colors = [_COLOR_CON]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=vals,
            marker_color=colors,
            text=[f"{v:,.2f} t" for v in vals],
            textposition="outside",
        )
    )
    fig.update_layout(
        **_layout_grafica_emisiones(
            title=f"Huella mensual total (t {_CO2})",
            yaxis_title=f"t {_CO2}",
            height=380,
            showlegend=False,
        ),
    )
    return fig


def _grafica_energia(datos: dict) -> go.Figure:
    """Consumo de red Con/Sin BESS agrupado; generación apilada (igual en ambos)."""
    periodos = [f["etiqueta"] for f in datos["por_periodo"]]
    con = [f["consumo_con_kwh"] / 1000.0 for f in datos["por_periodo"]]
    sin = (
        [f.get("consumo_sin_kwh", 0) / 1000.0 for f in datos["por_periodo"]]
        if datos.get("tiene_sin_bess")
        else None
    )
    gen = (
        [f["generacion_kwh"] / 1000.0 for f in datos["por_periodo"]]
        if datos.get("tiene_generacion")
        else None
    )
    etiq_gen = datos.get("generacion_etiqueta") or "Generacion"

    fig = go.Figure()
    if gen is not None:
        fig.add_trace(
            go.Bar(
                name=etiq_gen,
                x=periodos,
                y=gen,
                marker_color=_COLOR_GEN,
                offsetgroup="con",
                legendgroup="gen",
            )
        )
        fig.add_trace(
            go.Bar(
                name="Consumo red · Con BESS",
                x=periodos,
                y=con,
                marker_color=_COLOR_CON,
                offsetgroup="con",
                base=gen,
                legendgroup="con",
            )
        )
    else:
        fig.add_trace(
            go.Bar(
                name="Consumo red · Con BESS",
                x=periodos,
                y=con,
                marker_color=_COLOR_CON,
                offsetgroup="con",
                legendgroup="con",
            )
        )
    if sin is not None:
        if gen is not None:
            fig.add_trace(
                go.Bar(
                    name=etiq_gen,
                    x=periodos,
                    y=gen,
                    marker_color=_COLOR_GEN,
                    offsetgroup="sin",
                    legendgroup="gen",
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Bar(
                    name="Consumo red · Sin BESS",
                    x=periodos,
                    y=sin,
                    marker_color=_COLOR_SIN,
                    offsetgroup="sin",
                    base=gen,
                    legendgroup="sin",
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    name="Consumo red · Sin BESS",
                    x=periodos,
                    y=sin,
                    marker_color=_COLOR_SIN,
                    offsetgroup="sin",
                    legendgroup="sin",
                )
            )

    fig.update_layout(
        barmode="group",
        **_layout_grafica_emisiones(
            title="Energia por periodo (MWh)",
            yaxis_title="MWh",
            height=360,
        ),
    )
    return fig


def tab_emisiones(df, prefijo, descargar_fn):
    """Reporte de emisiones CO₂ del mes al dia de corte."""
    section_header(
        "Emisiones CO<sub>2</sub>",
        "Comparacion de huella Scope 2: consumo de red Con BESS vs Sin BESS.",
    )

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
        "Emisiones",
        "Fecha de corte para el acumulado mensual de emisiones.",
        "Fecha de corte",
        fecha_def,
        fecha_min,
        fecha_max,
        key=f"fecha_emisiones_{prefijo}",
    )

    datos = calcular_huella_carbono_mes(fecha_sel, prefijo)
    if datos is None:
        st.warning(
            "No hay datos de energia diaria para el mes seleccionado. "
            "Genere reportes desde el panel de administracion."
        )
        return

    st.caption(
        f"{datos['subestacion_nombre']} · "
        f"Factores: Base {FACTORES_EMISION['base']:.2f} / "
        f"Inter {FACTORES_EMISION['intermedio']:.2f} / "
        f"Punta {FACTORES_EMISION['punta']:.2f} kg {_CO2}/kWh · "
        f"{datos['dias_mes']} dia(s) del mes"
    )

    # ----- 1. Comparacion Con vs Sin BESS -----
    st.markdown("### 1. Comparacion de emisiones: Con BESS vs Sin BESS")
    if not datos["tiene_sin_bess"]:
        st.warning(
            "No hay columnas Sin BESS en ENERGIA_*_POR_DIA.csv; "
            "solo se muestra la huella Con BESS."
        )

    col_sin, col_con, col_delta = st.columns(3)
    with col_sin:
        st.metric(
            "Huella Sin BESS",
            f"{_fmt_t(datos.get('co2_sin_t'))} t {_CO2}" if datos["tiene_sin_bess"] else "—",
        )
        if datos["tiene_sin_bess"] and datos.get("total_consumo_sin_kwh") is not None:
            st.caption(f"Consumo: {datos['total_consumo_sin_kwh'] / 1000:,.2f} MWh")
    with col_con:
        st.metric("Huella Con BESS", f"{datos['co2_con_t']:,.2f} t {_CO2}")
        st.caption(f"Consumo: {datos['total_consumo_con_kwh'] / 1000:,.2f} MWh")
    with col_delta:
        ahorro = datos.get("ahorro_bess_t")
        pct = datos.get("ahorro_bess_pct")
        valor_efecto = "—"
        if ahorro is not None:
            valor_efecto = f"{_fmt_t(ahorro, con_signo=True)} t"
            if pct is not None:
                valor_efecto = f"{valor_efecto} ({_fmt_pct(pct, con_signo=True)})"
        st.metric(
            f"Efecto BESS en {_CO2}",
            valor_efecto,
            delta=_delta_ahorro(ahorro, pct),
            delta_color="normal" if (ahorro or 0) >= 0 else "inverse",
            help="Sin BESS - Con BESS. Positivo = el BESS reduce emisiones. "
            "% = ahorro / huella Sin BESS.",
        )

    filas_co2 = []
    for f in datos["por_periodo"]:
        row = {
            "Periodo": f["etiqueta"],
            f"EF (kg {_CO2}/kWh)": f"{f['ef_kg_kwh']:.2f}",
            f"{_CO2} Sin BESS (t)": _fmt_t(f.get("co2_sin_t")) if datos["tiene_sin_bess"] else "—",
            f"{_CO2} Con BESS (t)": _fmt_t(f["co2_con_t"]),
        }
        if datos["tiene_sin_bess"]:
            row["Ahorro (t)"] = _fmt_t(f.get("ahorro_t"), con_signo=True)
            row["Ahorro (%)"] = _fmt_pct(f.get("ahorro_pct"), con_signo=True)
        filas_co2.append(row)
    total_row = {
        "Periodo": "Total",
        f"EF (kg {_CO2}/kWh)": "—",
        f"{_CO2} Sin BESS (t)": _fmt_t(datos.get("co2_sin_t")) if datos["tiene_sin_bess"] else "—",
        f"{_CO2} Con BESS (t)": _fmt_t(datos["co2_con_t"]),
    }
    if datos["tiene_sin_bess"]:
        total_row["Ahorro (t)"] = _fmt_t(datos.get("ahorro_bess_t"), con_signo=True)
        total_row["Ahorro (%)"] = _fmt_pct(datos.get("ahorro_bess_pct"), con_signo=True)
    filas_co2.append(total_row)
    st.dataframe(pd.DataFrame(filas_co2), use_container_width=True, hide_index=True)

    g1, g2 = st.columns(2)
    with g1:
        render_grafica_plotly(
            _grafica_totales_comparacion(datos),
            "emisiones_totales",
            download_key=f"em_tot_{prefijo}",
        )
    with g2:
        render_grafica_plotly(
            _grafica_co2_comparacion(datos),
            "emisiones_periodo",
            download_key=f"em_per_{prefijo}",
        )

    # ----- 2. Generacion -----
    st.markdown("### 2. Generacion local")
    if datos["tiene_generacion"]:
        etiq = datos.get("generacion_etiqueta") or "Generacion"
        tipo = datos.get("generacion_tipo")
        st.metric(f"Energia · {etiq}", f"{datos['total_generacion_kwh'] / 1000:,.2f} MWh")
        if tipo == "gas":
            g1, g2, g3 = st.columns(3)
            with g1:
                st.metric(
                    "Si esa energia viniera de la red",
                    f"{datos['co2_gen_desplazado_t']:,.2f} t {_CO2}",
                    help="kWh cogeneracion x EF Marcado por periodo (Base/Inter/Punta).",
                )
            with g2:
                st.metric(
                    "Emisiones cogeneracion (plano)",
                    f"{datos['co2_gen_local_t']:,.2f} t {_CO2}",
                    help=f"Escenario plano: {EF_GAS_PLANO_KG_KWH:.2f} kg {_CO2}/kWh x kWh generados.",
                )
            with g3:
                neto = datos["co2_gen_neto_t"]
                pct_gen = datos.get("co2_gen_neto_pct")
                valor_neto = f"{neto:,.2f} t {_CO2}"
                if pct_gen is not None:
                    valor_neto = f"{valor_neto} ({_fmt_pct(pct_gen, con_signo=True)})"
                st.metric(
                    "Beneficio neto vs red",
                    valor_neto,
                    help=(
                        f"{_CO2} red - {_CO2} gas plano. "
                        "% = beneficio / emisiones si viniera de la red. "
                        "Positivo = la cogen emite menos que tomar esa energia de la red."
                    ),
                )
            st.caption(
                f"**{etiq}**: compara emisiones locales (EF plano "
                f"**{EF_GAS_PLANO_KG_KWH:.2f} kg {_CO2}/kWh**) contra las emisiones de red "
                f"Marcado (Base {FACTORES_EMISION['base']:.2f} / "
                f"Inter {FACTORES_EMISION['intermedio']:.2f} / "
                f"Punta {FACTORES_EMISION['punta']:.2f}) si esos kWh se consumieran de la red."
            )
        else:
            st.metric(
                f"{_CO2} de red desplazado (neto)",
                f"{datos['co2_gen_neto_t']:,.2f} t {_CO2}",
                help="Solar: sin combustion local; el neto iguala el desplazamiento de red.",
            )
            st.caption(
                f"**{etiq}**: beneficio = kWh que dejan de importarse de la red "
                "al EF Marcado del periodo (sin emisiones locales de combustion)."
            )
    else:
        st.caption("Esta subestacion no tiene recurso de generacion configurado.")

    # ----- 3. Balance energetico -----
    st.markdown("### 3. Balance energetico por periodo")
    filas_ene = []
    gen_col = datos.get("generacion_etiqueta") or "Generacion"
    for f in datos["por_periodo"]:
        row = {
            "Periodo": f["etiqueta"],
            "Consumo Sin BESS (kWh)": _fmt_kwh(f.get("consumo_sin_kwh", 0))
            if datos["tiene_sin_bess"]
            else "—",
            "Consumo Con BESS (kWh)": _fmt_kwh(f["consumo_con_kwh"]),
            f"{gen_col} (kWh)": _fmt_kwh(f["generacion_kwh"]),
        }
        if datos.get("netmetering"):
            row["REC (kWh)"] = _fmt_kwh(f["rec_kwh"])
            row["ENT (kWh)"] = _fmt_kwh(f["ent_kwh"])
        filas_ene.append(row)
    st.dataframe(pd.DataFrame(filas_ene), use_container_width=True, hide_index=True)
    if datos.get("tiene_generacion"):
        st.caption(
            f"En la grafica, **{gen_col}** es la base de cada barra; arriba va el consumo "
            "de red Con BESS / Sin BESS (la generacion local no depende del escenario BESS)."
        )
    render_grafica_plotly(
        _grafica_energia(datos),
        "emisiones_energia",
        download_key=f"em_ene_{prefijo}",
    )

    # ----- 4. Factores y cita -----
    st.markdown("### 4. Factores de emision")
    st.markdown(
        f"- **Base:** {FACTORES_EMISION['base']:.2f} kg {_CO2}/kWh  \n"
        f"- **Intermedio:** {FACTORES_EMISION['intermedio']:.2f} kg {_CO2}/kWh  \n"
        f"- **Punta:** {FACTORES_EMISION['punta']:.2f} kg {_CO2}/kWh"
    )
    st.caption(datos.get("cita_factores") or CITA_FACTORES_EMISION)

    try:
        pdf_bytes = generar_emisiones_pdf_bytes(datos)
    except Exception as exc:
        st.error("No se pudo generar el PDF de emisiones. La vista en pantalla sigue disponible.")
        st.caption(str(exc))
    else:
        descargar_fn(
            pdf_bytes,
            nombre_archivo_emisiones(fecha_sel, prefijo, datos["escenario_id"]),
            mime_type="application/pdf",
            etiqueta="Descargar reporte de emisiones",
        )
