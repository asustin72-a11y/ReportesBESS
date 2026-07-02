"""Pestaña Participación Capacidad (Shapley CFE)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from bess.cfe.shapley import ParticipacionCapacidadError, calcular_participacion_capacidad
from bess.config.subestaciones import (
    recurso_generacion_subestacion,
    soporta_participacion_capacidad,
    subestacion_por_id,
)
from bess.core.dates import serie_fecha_operativa
from bess.ui.components import render_selector_fecha_unica, section_header


def tab_participacion_capacidad(df, subestacion_id: str):
    sub = subestacion_por_id(subestacion_id)
    if not sub or not soporta_participacion_capacidad(subestacion_id):
        st.info(
            "Participación de capacidad requiere generación o cogeneración en la subestación. "
            "IUSA 2 (granja solar) e IUSA 1 (cogeneración) están soportadas."
        )
        return

    if "DATETIME" not in df.columns:
        df = df.copy()
        df["DATETIME"] = pd.to_datetime(df["FECHA_HORA"], format="%d/%m/%Y %H:%M")

    fecha_min = serie_fecha_operativa(df["DATETIME"]).min()
    fecha_max = serie_fecha_operativa(df["DATETIME"]).max()
    fecha_def = datetime.now().date() - timedelta(days=1)
    fecha_def = max(fecha_min, min(fecha_def, fecha_max))

    recurso = recurso_generacion_subestacion(subestacion_id)
    recurso_label = recurso.etiqueta.lower() if recurso else "generación"
    fecha_sel = render_selector_fecha_unica(
        "Participación Capacidad",
        f"Acumulado mensual hasta la fecha de corte. Shapley sobre capacidad CFE "
        f"({recurso_label} vs BESS).",
        "Fecha de corte",
        fecha_def,
        fecha_min,
        fecha_max,
        key=f"fecha_participacion_{subestacion_id}",
    )

    mes_label = fecha_sel.strftime("%m/%Y")
    section_header(
        f"Participación capacidad · {sub.nombre.replace('Subestación ', '')} · {mes_label}",
        "Atribución Shapley de la reducción de capacidad facturable CFE.",
    )

    try:
        resultado = calcular_participacion_capacidad(subestacion_id, fecha_sel)
    except ParticipacionCapacidadError as exc:
        st.warning(str(exc))
        if sub.cogeneracion_csv and not sub.ruta_cogeneracion_lectura().exists():
            st.caption(
                f"Sincronice el medidor **{sub.cogeneracion_nombre}** (API) desde el panel admin "
                f"para generar `{sub.cogeneracion_csv}`."
            )
        return

    cfg = resultado["config"]
    skw = resultado["shapley_kw"]
    smxn = resultado["shapley_mxn"]
    pct = resultado["participacion_pct"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Ahorro capacidad", f"{int(skw['total']):,} kW")
    with c2:
        st.metric(
            f"Shapley {cfg.etiqueta_generacion}",
            f"{skw['generacion']:,.0f} kW",
            f"{pct['generacion']:.1f} %",
        )
    with c3:
        st.metric(
            "Shapley BESS",
            f"{skw['bess']:,.0f} kW",
            f"{pct['bess']:.1f} %",
        )
    with c4:
        st.metric("Ahorro (MXN)", f"${smxn['total']:,.2f}")

    st.markdown(
        f"""<div class="cap-tarifa">
        Tarifa capacidad: <b>${resultado['tarifa_cap']:,.2f}/kW</b> ·
        Días: <b>{resultado['dias']}</b> ·
        Criterio que limita Dcb: <b>{resultado['criterio_limitante']}</b>
        </div>""",
        unsafe_allow_html=True,
    )

    tab_esc, tab_shap, tab_met = st.tabs([
        "Escenarios CFE",
        "Shapley",
        "Metodología",
    ])

    with tab_esc:
        st.dataframe(resultado["criterio_cfe"], use_container_width=True, hide_index=True)

    with tab_shap:
        st.dataframe(resultado["shapley"], use_container_width=True, hide_index=True)

    with tab_met:
        st.dataframe(resultado["metodologia"], use_container_width=True, hide_index=True)
