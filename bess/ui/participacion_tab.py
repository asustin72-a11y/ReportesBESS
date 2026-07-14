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
from bess.config.theme import COLORES
from bess.core.dates import serie_fecha_operativa
from bess.core.numbers import fmt_kwh, redondear_mxn_energia
from bess.ui.components import render_selector_fecha_unica, section_header, subnav_en_panel

_CODIGOS_ESCENARIO = ("D0", "Dc", "Db", "Dcb")
_LABEL_CRITERIO = {
    "punta": "Demanda punta",
    "factor_carga": "DemandaCalculadaCFE",
}


def _fmt_mxn(val: float) -> str:
    return f"${redondear_mxn_energia(val):,.2f}"


def _fmt_kw(val) -> str:
    return f"{int(val):,}"


def _formatear_escenarios_cfe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.insert(0, "Código", list(_CODIGOS_ESCENARIO[: len(out)]))
    out["Energía (kWh)"] = out["Energía (kWh)"].map(fmt_kwh)
    for col in ("Demanda punta (kW)", "DemandaCalculadaCFE (kW)", "Capacidad CFE (kW)"):
        out[col] = out[col].map(_fmt_kw)
    out["Criterio aplicado"] = (
        out["Criterio aplicado"].map(_LABEL_CRITERIO).fillna(out["Criterio aplicado"])
    )
    out["Costo capacidad (MXN)"] = out["Costo capacidad (MXN)"].map(_fmt_mxn)
    return out


def _estilizar_tabla(
    df: pd.DataFrame,
    *,
    texto_cols: tuple[str, ...] = (),
    centro_cols: tuple[str, ...] = (),
    destacar_idx: int | None = None,
) -> pd.io.formats.style.Styler:
    texto_cols = texto_cols or (df.columns[0],)
    numeric_cols = [c for c in df.columns if c not in texto_cols and c not in centro_cols]
    styler = df.style
    for col in texto_cols:
        if col in df.columns:
            styler = styler.set_properties(
                subset=[col],
                **{"font-weight": "500", "text-align": "left"},
            )
    for col in centro_cols:
        if col in df.columns:
            styler = styler.set_properties(
                subset=[col],
                **{"text-align": "center", "color": "#4a5568"},
            )
    for col in numeric_cols:
        styler = styler.set_properties(
            subset=[col],
            **{"text-align": "right", "font-variant-numeric": "tabular-nums"},
        )
    if destacar_idx is not None and 0 <= destacar_idx < len(df):
        styler = styler.set_properties(
            subset=pd.IndexSlice[destacar_idx, :],
            **{
                "background-color": "#e8f4f8",
                "font-weight": "600",
                "border-top": "2px solid #1a5276",
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
                    ("white-space", "nowrap"),
                ],
            },
            {"selector": "tbody td", "props": [("padding", "8px 10px")]},
        ],
        overwrite=False,
    )
    return styler


def _estilizar_escenarios_cfe(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    return _estilizar_tabla(
        df,
        texto_cols=("Código", "Escenario"),
        centro_cols=("Criterio aplicado",),
        destacar_idx=len(df) - 1 if len(df) else None,
    )


def _estilizar_participantes(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    return _estilizar_tabla(
        df,
        texto_cols=("Participante",),
        centro_cols=("Participación",),
        destacar_idx=0 if len(df) else None,
    )


def _estilizar_concepto_valor(df: pd.DataFrame, filas_destacadas: tuple[int, ...]) -> pd.io.formats.style.Styler:
    styler = _estilizar_tabla(df, texto_cols=("Concepto",), centro_cols=())
    for idx in filas_destacadas:
        if 0 <= idx < len(df):
            concepto = str(df.iloc[idx].get("Concepto", ""))
            peso = "700" if "Ahorro" in concepto or "Reducción" in concepto else "600"
            styler = styler.set_properties(
                subset=pd.IndexSlice[idx, :],
                **{"background-color": "#f0f7fa", "font-weight": peso},
            )
    return styler


def _tarjeta_participante(label: str, kw: int, mxn: float, pct: float, color: str) -> str:
    return f"""
    <div class="metric-card" style="border-top:4px solid {color};">
        <div class="label">{label}</div>
        <div class="value">{kw:,} kW</div>
        <div class="sub" style="font-size:14px; color:#4a5568; margin-top:4px;">
            {_fmt_mxn(mxn)} MXN
        </div>
        <div class="sub">{pct:.1f} % del ahorro</div>
    </div>
    """


def _tarjeta_ahorro_total(kw: int, mxn: float, color: str) -> str:
    return f"""
    <div class="metric-card metric-card-total" style="border-top:4px solid {color}; margin-bottom: 0.5rem;">
        <div class="label">Ahorro total de capacidad (D0 − Dcb)</div>
        <div class="total-grid">
            <div class="total-item total-item-kw">
                <div class="item-label">Ahorro de capacidad</div>
                <div class="value">{kw:,}</div>
                <div class="unit">kW</div>
            </div>
            <div class="total-item total-item-mxn">
                <div class="item-label">Costo evitado</div>
                <div class="value">{_fmt_mxn(mxn)}</div>
                <div class="unit">MXN</div>
            </div>
        </div>
    </div>
    """


def tab_participacion_capacidad(df, subestacion_id: str):
    sub = subestacion_por_id(subestacion_id)
    if not sub or not soporta_participacion_capacidad(subestacion_id):
        st.info(
            "Participación de capacidad requiere un recurso de generación en la subestación."
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
        "Ahorro en capacidad (kW) y costo (MXN) atribuido por participante — Shapley.",
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

    st.markdown(
        _tarjeta_ahorro_total(
            int(skw["total"]),
            float(smxn["total"]),
            COLORES["primary"],
        ),
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            _tarjeta_participante(
                cfg.etiqueta_generacion,
                int(skw["generacion"]),
                float(smxn["generacion"]),
                float(pct["generacion"]),
                COLORES["success"],
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _tarjeta_participante(
                "BESS",
                int(skw["bess"]),
                float(smxn["bess"]),
                float(pct["bess"]),
                COLORES["secondary"],
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""<div class="cap-tarifa">
        Días: <b>{resultado['dias']}</b> ·
        Criterio que limita Dcb: <b>{resultado['criterio_limitante']}</b> ·
        Capacidad D0: <b>{resultado['cap']['d0']:,} kW</b> →
        Dcb: <b>{resultado['cap']['dcb']:,} kW</b> ·
        Tarifa capacidad: <b>{_fmt_mxn(float(resultado['tarifa_cap']))}/kW</b>
        </div>""",
        unsafe_allow_html=True,
    )

    vista = subnav_en_panel(
        "Participación capacidad",
        [
            ("part", "Participación"),
            ("esc", "Escenarios CFE"),
            ("shap_mxn", "Shapley (MXN)"),
            ("shap_kw", "Shapley (kW)"),
            ("met", "Metodología"),
        ],
        f"participacion_vista_{subestacion_id}",
    )

    if vista == "part":
        st.dataframe(
            _estilizar_participantes(resultado["participantes"]),
            use_container_width=True,
            hide_index=True,
        )

    elif vista == "esc":
        df_esc = _formatear_escenarios_cfe(resultado["criterio_cfe"])
        st.dataframe(
            _estilizar_escenarios_cfe(df_esc),
            use_container_width=True,
            hide_index=True,
        )

    elif vista == "shap_mxn":
        st.dataframe(
            _estilizar_concepto_valor(resultado["shapley_mxn_tabla"], (6, 7, 8)),
            use_container_width=True,
            hide_index=True,
        )

    elif vista == "shap_kw":
        st.dataframe(
            _estilizar_concepto_valor(resultado["shapley_kw_tabla"], (5, 6, 7)),
            use_container_width=True,
            hide_index=True,
        )

    elif vista == "met":
        st.dataframe(
            _estilizar_tabla(
                resultado["metodologia"],
                texto_cols=("Concepto", "Detalle"),
            ),
            use_container_width=True,
            hide_index=True,
        )
