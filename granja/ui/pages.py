"""Páginas Streamlit del reporteador Granja (local)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

from bess.config.users import ETIQUETA_ROL, rol_es_superadmin, verificar_password
from bess.charts.layout import sanear_figura_plotly
from bess.core.numbers import fmt_kwh, redondear_kwh
from bess.ui.auth import (
    get_usuarios,
    init_session,
    preparar_ui_login,
    restaurar_ui_app,
)
from bess.ui.components import obtener_logo_html
from bess.ui.sidebar import _ajustar_sidebar_por_rol
from bess.ui.styles import aplicar_estilos, aplicar_estilos_login

from granja import __version__ as VERSION
from granja.config import CAPACIDAD_MW, FECHA_INICIO_SYNC, NOMBRE_APP
from granja.config.meters import NOMBRES_MEGA
from granja.data.aggregates import (
    acumulado_mes,
    anios_con_datos,
    perfil_potencia_dia,
    rango_fechas_disponibles,
    resumen_rango,
)
from granja.data.catalogo import asegurar_megas_en_catalogo
from granja.data.sync import sincronizar_megas_con_lock
from granja.reports.daily_pdf import generar_pdf_diario
from granja.reports.monthly_pdf import (
    generar_pdf_mensual_energia,
    generar_pdf_mensual_ingresos,
)

_MESES_ES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_COLS_ENERGIA = ("Base", "Intermedio", "Punta", "Total")
_COLS_INGRESO = ("Ingreso_Base", "Ingreso_Intermedio", "Ingreso_Punta", "Ingreso_Total")

_RENAME_TABLA = {
    "etiqueta": "Medidor",
    "fecha": "Fecha",
    "Base": "Base (kWh)",
    "Intermedio": "Intermedio (kWh)",
    "Punta": "Punta (kWh)",
    "Total": "Total (kWh)",
    "Ingreso_Base": "Ingreso Base ($)",
    "Ingreso_Intermedio": "Ingreso Intermedio ($)",
    "Ingreso_Punta": "Ingreso Punta ($)",
    "Ingreso_Total": "Ingreso Total ($)",
}


def _fmt_mxn(valor: float) -> str:
    """Vista: MXN a entero half-up (≥0.5 arriba), igual que kWh."""
    return f"${redondear_kwh(valor):,}"


def _fmt_kwh_tabla(valor) -> str:
    return f"{redondear_kwh(valor):,}"


def _plotly_chart(fig, **kwargs) -> None:
    """st.plotly_chart con leyenda/hover seguros (evita cuelgues del navegador)."""
    sanear_figura_plotly(fig)
    kwargs.setdefault("use_container_width", True)
    st.plotly_chart(fig, **kwargs)


def _vista_energia_ingreso(df: pd.DataFrame) -> pd.DataFrame:
    """Copia numérica para gráficas: kWh y MXN a enteros (half-up ≥0.5)."""
    out = df.copy()
    for col in _COLS_ENERGIA:
        if col in out.columns:
            out[col] = out[col].map(lambda v: redondear_kwh(v))
    for col in _COLS_INGRESO:
        if col in out.columns:
            out[col] = out[col].map(lambda v: redondear_kwh(v))
    return out


def _tabla_energia_ingreso(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla para pantalla: miles, $ en ingresos y unidades en encabezados."""
    num = _vista_energia_ingreso(df)
    out = num.copy()
    if "medidor_id" in out.columns:
        out = out.drop(columns=["medidor_id"])
    for col in _COLS_ENERGIA:
        if col in out.columns:
            out[col] = out[col].map(_fmt_kwh_tabla)
    for col in _COLS_INGRESO:
        if col in out.columns:
            out[col] = out[col].map(_fmt_mxn)
    if "fecha" in out.columns:
        out["fecha"] = out["fecha"].astype(str)
    renombrar = {k: v for k, v in _RENAME_TABLA.items() if k in out.columns}
    out = out.rename(columns=renombrar)
    preferido = [
        "Fecha",
        "Medidor",
        "Base (kWh)",
        "Intermedio (kWh)",
        "Punta (kWh)",
        "Total (kWh)",
        "Ingreso Base ($)",
        "Ingreso Intermedio ($)",
        "Ingreso Punta ($)",
        "Ingreso Total ($)",
    ]
    cols = [c for c in preferido if c in out.columns] + [
        c for c in out.columns if c not in preferido
    ]
    return out[cols]


def _fmt_precio(valor: float) -> str:
    return f"{float(valor):.4f}"


def _fmt_fecha_es(dia: date) -> str:
    return f"{dia.day} de {_MESES_ES[dia.month]} de {dia.year}"


def _fmt_rango_es(desde: date, hasta: date) -> str:
    if desde == hasta:
        return _fmt_fecha_es(desde)
    return f"{_fmt_fecha_es(desde)} → {_fmt_fecha_es(hasta)}"


def _banner_periodo(
    desde: date,
    hasta: date,
    *,
    min_d: date | None = None,
    max_d: date | None = None,
    etiqueta: str = "Periodo de consulta",
) -> None:
    """Resalta el rango de fechas que está alimentando la vista."""
    dias_n = (hasta - desde).days + 1
    rango_txt = _fmt_rango_es(desde, hasta)
    dias_txt = f"{dias_n} día" if dias_n == 1 else f"{dias_n} días"
    disponible = ""
    if min_d is not None and max_d is not None:
        disponible = (
            f'<div style="margin-top:6px;font-size:12px;opacity:0.85;">'
            f"Datos disponibles: {min_d.strftime('%d/%m/%Y')} – "
            f"{max_d.strftime('%d/%m/%Y')}</div>"
        )
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#1a5276,#2e86c1);
                    color:white;border-radius:12px;padding:14px 18px;
                    margin:6px 0 16px 0;box-shadow:0 2px 8px rgba(26,82,118,0.25);">
            <div style="font-size:12px;font-weight:600;letter-spacing:0.04em;
                        text-transform:uppercase;opacity:0.9;">{etiqueta}</div>
            <div style="font-size:22px;font-weight:700;line-height:1.25;margin-top:4px;">
                {rango_txt}
            </div>
            <div style="font-size:13px;margin-top:4px;opacity:0.95;">{dias_txt}</div>
            {disponible}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _clamp_fecha(dia: date, min_d: date, max_d: date) -> date:
    return max(min_d, min(dia, max_d))


def _aplicar_rango_session(key: str, desde: date, hasta: date, min_d: date, max_d: date) -> None:
    d0 = _clamp_fecha(desde, min_d, max_d)
    d1 = _clamp_fecha(hasta, min_d, max_d)
    if d0 > d1:
        d0, d1 = d1, d0
    st.session_state[f"{key}_desde_input"] = d0
    st.session_state[f"{key}_hasta_input"] = d1


def _rango_atajo(atajo: str, min_d: date, max_d: date) -> tuple[date, date]:
    """Devuelve (desde, hasta) para un atajo de periodo."""
    if atajo == "ultimo":
        return max_d, max_d
    if atajo == "ayer":
        ayer = _clamp_fecha(max_d - timedelta(days=1), min_d, max_d)
        return ayer, ayer
    if atajo == "7d":
        return _clamp_fecha(max_d - timedelta(days=6), min_d, max_d), max_d
    if atajo == "mes":
        return _clamp_fecha(date(max_d.year, max_d.month, 1), min_d, max_d), max_d
    if atajo == "mesant":
        primero_mes = date(max_d.year, max_d.month, 1)
        fin_ant = primero_mes - timedelta(days=1)
        ini_ant = date(fin_ant.year, fin_ant.month, 1)
        return _clamp_fecha(ini_ant, min_d, max_d), _clamp_fecha(fin_ant, min_d, max_d)
    return min_d, max_d


def _atajo_coincide(atajo: str, d0: date, d1: date, min_d: date, max_d: date) -> bool:
    desde, hasta = _rango_atajo(atajo, min_d, max_d)
    return d0 == desde and d1 == hasta


def _selector_fecha(*, key: str, dias_antes_del_ultimo: int = 0) -> date | None:
    """Selector de un día con formato local y botones anterior/siguiente."""
    rango = _rango_fechas_cached()
    if rango is None:
        st.info(
            "No hay perfiles de MEGAs en la base local. "
            "Sincroniza desde la barra lateral (superadmin) o el cron."
        )
        return None
    min_d, max_d = rango
    state_key = f"{key}_input"
    if state_key not in st.session_state:
        st.session_state[state_key] = _clamp_fecha(
            max_d - timedelta(days=max(dias_antes_del_ultimo, 0)),
            min_d,
            max_d,
        )

    st.markdown("##### Fecha del reporte")
    c_prev, c_fecha, c_next, c_hoy = st.columns([1, 2.5, 1, 1.2])
    with c_prev:
        if st.button("◀ Día ant.", key=f"{key}_prev", use_container_width=True):
            st.session_state[state_key] = _clamp_fecha(
                st.session_state[state_key] - timedelta(days=1), min_d, max_d
            )
            st.rerun()
    with c_next:
        if st.button("Día sig. ▶", key=f"{key}_next", use_container_width=True):
            st.session_state[state_key] = _clamp_fecha(
                st.session_state[state_key] + timedelta(days=1), min_d, max_d
            )
            st.rerun()
    with c_hoy:
        if st.button("Último día", key=f"{key}_ultimo", use_container_width=True):
            st.session_state[state_key] = max_d
            st.rerun()
    with c_fecha:
        elegido = st.date_input(
            "Fecha",
            min_value=min_d,
            max_value=max_d,
            format="DD/MM/YYYY",
            key=state_key,
            label_visibility="collapsed",
        )

    dia = elegido if isinstance(elegido, date) else st.session_state[state_key]
    _banner_periodo(
        dia,
        dia,
        min_d=min_d,
        max_d=max_d,
        etiqueta="Fecha del reporte",
    )
    return dia


def _selector_rango(*, key: str) -> tuple[date, date] | None:
    """Desde/Hasta + atajos. Solo confirma el rango al pulsar Consultar (o un atajo)."""
    rango = _rango_fechas_cached()
    if rango is None:
        st.info(
            "No hay perfiles de MEGAs en la base local. "
            "Sincroniza desde la barra lateral (superadmin) o el cron."
        )
        return None

    min_d, max_d = rango
    k_desde = f"{key}_desde_input"
    k_hasta = f"{key}_hasta_input"
    k_aplicado = f"{key}_aplicado"
    if k_desde not in st.session_state:
        st.session_state[k_desde] = max_d
    if k_hasta not in st.session_state:
        st.session_state[k_hasta] = max_d
    # Por defecto: último día disponible (ya consultado).
    if k_aplicado not in st.session_state:
        st.session_state[k_aplicado] = (max_d, max_d)

    d_prev = st.session_state[k_desde]
    h_prev = st.session_state[k_hasta]
    if isinstance(d_prev, date) and isinstance(h_prev, date) and d_prev > h_prev:
        d_prev, h_prev = h_prev, d_prev

    etiquetas = (
        ("Actual", "ultimo"),
        ("Ayer", "ayer"),
        ("7 días", "7d"),
        ("Mes actual", "mes"),
        ("Mes ant.", "mesant"),
        ("Todo", "todo"),
    )
    activo = next(
        (
            atajo
            for _, atajo in etiquetas
            if isinstance(d_prev, date)
            and isinstance(h_prev, date)
            and _atajo_coincide(atajo, d_prev, h_prev, min_d, max_d)
        ),
        None,
    )

    st.markdown("##### Periodo de consulta")
    st.caption(
        "Elige un atajo o ajusta Desde / Hasta y pulsa Consultar. "
        "Formato: día/mes/año."
    )

    from bess.ui.components import marcar_fila_controles

    # Marcador dentro de la 1.ª columna (display:none vía CSS) para anclar
    # estilos a la fila sin alterar alturas ni gaps.
    atajos_cols = st.columns(6, gap="small")
    with atajos_cols[0]:
        marcar_fila_controles()
    for col, (label, atajo) in zip(atajos_cols, etiquetas):
        with col:
            tipo = "primary" if atajo == activo else "secondary"
            if st.button(
                label,
                key=f"{key}_atajo_{atajo}",
                use_container_width=True,
                type=tipo,
            ):
                d0_a, d1_a = _rango_atajo(atajo, min_d, max_d)
                _aplicar_rango_session(key, d0_a, d1_a, min_d, max_d)
                st.session_state[k_aplicado] = (d0_a, d1_a)
                st.rerun()

    # Misma rejilla de 6 unidades que los atajos: 2+2+1+1.
    c1, c2, c3, c4 = st.columns(
        [2, 2, 1, 1],
        gap="small",
        vertical_alignment="bottom",
    )
    with c1:
        marcar_fila_controles()
        desde = st.date_input(
            "Desde",
            min_value=min_d,
            max_value=max_d,
            format="DD/MM/YYYY",
            key=k_desde,
        )
    with c2:
        hasta = st.date_input(
            "Hasta",
            min_value=min_d,
            max_value=max_d,
            format="DD/MM/YYYY",
            key=k_hasta,
        )

    d0 = desde if isinstance(desde, date) else st.session_state[k_desde]
    d1 = hasta if isinstance(hasta, date) else st.session_state[k_hasta]
    if d0 > d1:
        d0, d1 = d1, d0

    dias_n = (d1 - d0).days + 1
    with c3:
        st.markdown(
            f'<div class="periodo-dias">'
            f'<div class="periodo-dias-lbl">Días</div>'
            f'<div class="periodo-dias-val">{dias_n}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    with c4:
        if st.button(
            "Consultar",
            type="primary",
            key=f"{key}_consultar",
            use_container_width=True,
        ):
            # No tocar k_desde/k_hasta: el widget ya está instanciado.
            # Si venían invertidos, d0/d1 ya están ordenados aquí.
            st.session_state[k_aplicado] = (d0, d1)
            st.rerun()

    _banner_periodo(d0, d1, min_d=min_d, max_d=max_d)

    aplicado = st.session_state.get(k_aplicado)
    if not isinstance(aplicado, tuple) or len(aplicado) != 2:
        st.info("Selecciona el periodo y pulsa **Consultar** para generar la vista.")
        return None

    a0, a1 = aplicado
    if a0 != d0 or a1 != d1:
        st.info("El periodo cambió. Pulsa **Consultar** para actualizar la vista.")
        return None

    return a0, a1


def _kpi_card(label: str, value: str, sub: str = "", *, color: str = "#1a5276") -> str:
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="metric-card" style="border-top:3px solid {color}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f"{sub_html}</div>"
    )


def _render_kpis_dashboard(resumen: dict, *, un_dia: bool, desde: date, hasta: date) -> None:
    if un_dia:
        acum = acumulado_mes(desde)
        kpis = [
            ("Energía del periodo", fmt_kwh(resumen["energia_total"]), "kWh", "#1a5276"),
            ("Ingreso del periodo (DIST)", _fmt_mxn(resumen["ingreso_total"]), "MXN", "#0e9f6e"),
            ("Energía mes (acum.)", fmt_kwh(acum["energia_kwh"]), "kWh", "#2563eb"),
            ("Ingreso mes (acum.)", _fmt_mxn(acum["ingreso_mxn"]), "MXN", "#059669"),
        ]
    else:
        dias_n = (hasta - desde).days + 1
        promedio = resumen["energia_total"] / dias_n if dias_n else 0.0
        kpis = [
            ("Energía del periodo", fmt_kwh(resumen["energia_total"]), "kWh", "#1a5276"),
            ("Ingreso del periodo (DIST)", _fmt_mxn(resumen["ingreso_total"]), "MXN", "#0e9f6e"),
            ("Días del periodo", f"{dias_n}", "días", "#2563eb"),
            ("Promedio diario", fmt_kwh(promedio), "kWh/día", "#059669"),
        ]

    cols = st.columns(4)
    for col, (label, value, sub, color) in zip(cols, kpis):
        with col:
            st.markdown(_kpi_card(label, value, sub, color=color), unsafe_allow_html=True)

    st.markdown("##### Por periodo DIST")
    periodos = [
        ("Base", resumen["energia_base"], resumen["ingreso_base"], "#3498db"),
        ("Intermedio", resumen["energia_intermedio"], resumen["ingreso_intermedio"], "#f39c12"),
        ("Punta", resumen["energia_punta"], resumen["ingreso_punta"], "#e74c3c"),
    ]
    cols_p = st.columns(3)
    for col, (nombre, kwh, mxn, color) in zip(cols_p, periodos):
        with col:
            st.markdown(
                _kpi_card(
                    nombre,
                    f"{fmt_kwh(kwh)} kWh",
                    _fmt_mxn(mxn),
                    color=color,
                ),
                unsafe_allow_html=True,
            )

    if resumen.get("precios"):
        precios = resumen["precios"]
        st.caption(
            f"Tarifa DIST del mes: Base ${_fmt_precio(precios.get('Base', 0))} · "
            f"Intermedio ${_fmt_precio(precios.get('Intermedio', 0))} · "
            f"Punta ${_fmt_precio(precios.get('Punta', 0))} MXN/kWh"
        )
    else:
        st.caption("Tarifa DIST aplicada por mes de cada día del rango.")


@st.cache_data(ttl=120, show_spinner=False)
def _rango_fechas_cached() -> tuple[date, date] | None:
    return rango_fechas_disponibles()


@st.cache_data(ttl=120, show_spinner=False)
def _resumen_rango_cached(desde_iso: str, hasta_iso: str) -> dict:
    return resumen_rango(desde_iso, hasta_iso)


def _tab_dashboard() -> None:
    rango = _selector_rango(key="granja_rango_dashboard")
    if rango is None:
        return
    desde, hasta = rango
    un_dia = desde == hasta

    with st.spinner("Calculando energía e ingresos DIST…"):
        resumen = _resumen_rango_cached(desde.isoformat(), hasta.isoformat())
    detalle = resumen["detalle"]
    por_dia = resumen["por_dia"]

    etiqueta_periodo = _fmt_rango_es(desde, hasta)

    _render_kpis_dashboard(resumen, un_dia=un_dia, desde=desde, hasta=hasta)

    if detalle.empty:
        st.warning("Sin datos de energía para el periodo seleccionado.")
        return

    vista_graf = _vista_energia_ingreso(detalle)

    fig = px.bar(
        vista_graf,
        x="etiqueta",
        y="Total",
        title=f"Energía generada por MEGA — {etiqueta_periodo}",
        labels={"etiqueta": "MEGA", "Total": "kWh"},
    )
    max_v = float(vista_graf["Total"].max()) if len(vista_graf) else 0
    min_v = float(vista_graf["Total"].min()) if len(vista_graf) else 0
    colores = [
        "green" if v == max_v else "red" if v == min_v else "#1a5276"
        for v in vista_graf["Total"]
    ]
    fig.update_traces(marker_color=colores)
    _plotly_chart(fig)

    fig_ing = px.bar(
        vista_graf,
        x="etiqueta",
        y="Ingreso_Total",
        title=f"Ingreso por MEGA — {etiqueta_periodo}",
        labels={"etiqueta": "MEGA", "Ingreso_Total": "MXN"},
    )
    _plotly_chart(fig_ing)

    if not un_dia and not por_dia.empty:
        st.subheader("Resumen por día")
        vista_dia = _vista_energia_ingreso(por_dia)
        vista_dia["fecha"] = vista_dia["fecha"].astype(str)
        st.dataframe(
            _tabla_energia_ingreso(por_dia),
            use_container_width=True,
            hide_index=True,
        )

        fig_dia = px.bar(
            vista_dia,
            x="fecha",
            y=["Base", "Intermedio", "Punta"],
            title="Energía diaria por periodo DIST",
            labels={"value": "kWh", "fecha": "Día", "variable": "Periodo"},
            barmode="stack",
        )
        _plotly_chart(fig_dia)

        fig_ing_dia = px.line(
            vista_dia,
            x="fecha",
            y="Ingreso_Total",
            title="Ingreso diario",
            labels={"fecha": "Día", "Ingreso_Total": "MXN"},
            markers=True,
        )
        _plotly_chart(fig_ing_dia)

    if un_dia:
        pot = perfil_potencia_dia(desde)
        if not pot.empty:
            st.subheader("Perfil de potencia estimado (MW)")
            pot_mw = pot.copy()
            pot_mw["mw"] = pot_mw["kw"] / 1000.0
            fig_p = px.line(
                pot_mw,
                x="fecha",
                y="mw",
                color="etiqueta",
                title="Por MEGA",
                labels={"fecha": "Hora", "mw": "MW", "etiqueta": "MEGA"},
            )
            _plotly_chart(fig_p)

            pot_total = (
                pot.groupby("fecha", as_index=False)["kw"]
                .sum()
                .sort_values("fecha")
            )
            pot_total["mw"] = pot_total["kw"] / 1000.0
            fig_t = px.line(
                pot_total,
                x="fecha",
                y="mw",
                title="Total granja (suma 21 MEGAs)",
                labels={"fecha": "Hora", "mw": "MW"},
            )
            fig_t.update_traces(line_color="#1a5276", line_width=2)
            fig_t.update_yaxes(range=[0, CAPACIDAD_MW * 1.05])
            _plotly_chart(fig_t)

    st.subheader("Energía e ingreso por MEGA")
    st.dataframe(
        _tabla_energia_ingreso(detalle),
        use_container_width=True,
        hide_index=True,
    )


def _sidebar_sync() -> None:
    """Controles de sync API Farm en la barra lateral."""
    st.markdown("##### Sincronizar perfiles")
    st.caption(
        f"API Farm · {len(NOMBRES_MEGA)} MEGAs · desde {FECHA_INICIO_SYNC}\n\n"
        "En servidor: cron Linux cada 15 min (`deploy/install-cron-granja.sh`). "
        "La app solo recarga la vista; no bloquea con sync automática."
    )


    auto_info = st.session_state.get("granja_auto_sync_info")
    if auto_info:
        st.caption(auto_info)

    con_desde = st.checkbox(
        "Forzar fecha de inicio",
        value=False,
        key="granja_sync_forzar_desde",
        help="Si no se marca, cada MEGA continúa desde su último dato en la base.",
    )
    desde = None
    if con_desde:
        desde_val = st.date_input(
            "Desde",
            value=date.fromisoformat(FECHA_INICIO_SYNC),
            format="DD/MM/YYYY",
            key="granja_sync_desde",
        )
        desde = desde_val.isoformat() if isinstance(desde_val, date) else FECHA_INICIO_SYNC

    usar_hasta = st.checkbox(
        "Limitar fecha final",
        value=False,
        key="granja_sync_usar_hasta",
        help="Si no se marca, descarga hasta hoy.",
    )
    hasta = None
    if usar_hasta:
        hasta_val = st.date_input(
            "Hasta",
            value=date.today(),
            format="DD/MM/YYYY",
            key="granja_sync_hasta",
        )
        hasta = hasta_val.isoformat() if isinstance(hasta_val, date) else None

    if st.button("Sincronizar 21 MEGAs", type="primary", key="granja_sync_btn", use_container_width=True):
        barra = st.progress(0.0, text="Preparando…")
        estado = st.empty()

        def _on_progress(step: int, total: int, label: str) -> None:
            pct = min(step / total, 1.0) if total else 1.0
            texto = f"{step}/{total} · {label}"
            try:
                barra.progress(pct, text=texto)
            except TypeError:
                barra.progress(pct)
            estado.caption(texto)

        try:
            resumen = sincronizar_megas_con_lock(
                timeout=30,
                desde=desde,
                hasta=hasta,
                quiet=True,
                on_progress=_on_progress,
            )
        except Exception as exc:
            try:
                barra.progress(1.0, text="Error")
            except TypeError:
                barra.progress(1.0)
            st.error(f"No se pudo sincronizar: {exc}")
            return

        if resumen is None:
            st.warning("Otra sincronización sigue en curso.")
            return

        try:
            barra.progress(1.0, text="Completado")
        except TypeError:
            barra.progress(1.0)
        ok = [r for r in resumen if "error" not in r]
        err = [r for r in resumen if "error" in r]
        st.session_state["granja_sync_resumen"] = resumen
        st.success(f"{len(ok)} OK · {len(err)} error(es)")
        _rango_fechas_cached.clear()
        _resumen_rango_cached.clear()
        st.rerun()

    if st.session_state.get("granja_sync_resumen") is not None:
        with st.expander("Resultado de la última sincronización", expanded=False):
            resumen = st.session_state["granja_sync_resumen"]
            ok = [r for r in resumen if "error" not in r]
            err = [r for r in resumen if "error" in r]
            st.caption(f"{len(ok)} OK · {len(err)} con error")
            st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)


def _auto_sync_si_corresponde(tick: int) -> None:
    """En cada tick del autorefresh (cada 15 min), sync incremental silenciosa."""
    prev = st.session_state.get("_granja_auto_sync_tick", -1)
    if tick <= prev:
        return
    st.session_state["_granja_auto_sync_tick"] = tick
    if tick <= 0:
        return

    ahora = datetime.now(ZoneInfo("America/Mexico_City"))
    try:
        resumen = sincronizar_megas_con_lock(timeout=0, quiet=True)
    except Exception as exc:
        st.session_state["granja_auto_sync_info"] = (
            f"Auto-sync falló · {ahora:%H:%M} · {exc}"
        )
        return

    if resumen is None:
        st.session_state["granja_auto_sync_info"] = (
            f"Auto-sync omitido (otra sync en curso) · {ahora:%H:%M}"
        )
        return

    ok = sum(1 for r in resumen if "error" not in r)
    err = sum(1 for r in resumen if "error" in r)
    st.session_state["granja_sync_resumen"] = resumen
    st.session_state["granja_auto_sync_info"] = (
        f"Última auto-sync · {ahora:%d/%m %H:%M} · {ok} OK · {err} error(es)"
    )



def _hacer_callback_progreso(barra, estado):
    """Actualiza st.progress + caption con (step, total, label)."""
    def _on_progress(step: int, total: int, label: str) -> None:
        pct = min(step / total, 1.0) if total else 1.0
        texto = f"{step}/{total} · {label}"
        try:
            barra.progress(pct, text=texto)
        except TypeError:
            barra.progress(pct)
        estado.caption(texto)

    return _on_progress


def _tab_pdf_diario() -> None:
    st.subheader("Reporte Diario")
    st.caption("Energía e ingresos DIST del día (PDF).")
    dia = _selector_fecha(key="granja_fecha_pdf", dias_antes_del_ultimo=1)
    if dia is None:
        return
    if st.button("Generar PDF diario", type="primary", key="granja_pdf_diario_btn"):
        barra = st.progress(0.0, text="Preparando…")
        estado = st.empty()
        try:
            ruta = generar_pdf_diario(
                dia,
                on_progress=_hacer_callback_progreso(barra, estado),
            )
            try:
                barra.progress(1.0, text="Completado")
            except TypeError:
                barra.progress(1.0)
            estado.caption("Listo")
            st.success(f"Guardado: `{ruta}`")
            st.download_button(
                "Descargar PDF",
                data=ruta.read_bytes(),
                file_name=ruta.name,
                mime="application/pdf",
                key="granja_dl_pdf_diario",
            )
        except Exception as exc:
            st.error(f"No se pudo generar el PDF: {exc}")


def _selector_anios_mensual(key: str) -> list[int] | None:
    disponibles = anios_con_datos()
    if not disponibles:
        st.info(
            "No hay perfiles de MEGAs en la base local. "
            "Ve a la pestaña Sincronización y descarga desde la API."
        )
        return None
    default = disponibles[-4:] if len(disponibles) > 4 else disponibles
    anios = st.multiselect(
        "Años a comparar",
        options=disponibles,
        default=default,
        key=key,
        help="Se generan barras y tabla por mes para cada año seleccionado.",
    )
    if not anios:
        st.warning("Selecciona al menos un año.")
        return None
    return sorted(anios)


def _tab_pdf_mensual_ingresos() -> None:
    st.subheader("Reporte Mensual — Ingresos")
    st.caption("Comparativo de ingresos DIST por mes y año (Importe Acumulado).")
    anios = _selector_anios_mensual("granja_anios_mensual_ingresos")
    if anios is None:
        return
    if st.button(
        "Generar PDF de ingresos",
        type="primary",
        key="granja_pdf_mensual_ingresos_btn",
    ):
        barra = st.progress(0.0, text="Preparando…")
        estado = st.empty()
        try:
            ruta = generar_pdf_mensual_ingresos(
                anios,
                on_progress=_hacer_callback_progreso(barra, estado),
            )
            try:
                barra.progress(1.0, text="Completado")
            except TypeError:
                barra.progress(1.0)
            estado.caption("Listo")
            st.success(f"Guardado: `{ruta}`")
            st.download_button(
                "Descargar PDF",
                data=ruta.read_bytes(),
                file_name=ruta.name,
                mime="application/pdf",
                key="granja_dl_pdf_mensual_ingresos",
            )
        except Exception as exc:
            st.error(f"No se pudo generar el PDF: {exc}")


def _tab_pdf_mensual_energia() -> None:
    st.subheader("Reporte Mensual — Energía")
    st.caption("Comparativo de energía generada (kWh) por mes y año.")
    anios = _selector_anios_mensual("granja_anios_mensual_energia")
    if anios is None:
        return
    if st.button(
        "Generar PDF de energía",
        type="primary",
        key="granja_pdf_mensual_energia_btn",
    ):
        barra = st.progress(0.0, text="Preparando…")
        estado = st.empty()
        try:
            ruta = generar_pdf_mensual_energia(
                anios,
                on_progress=_hacer_callback_progreso(barra, estado),
            )
            try:
                barra.progress(1.0, text="Completado")
            except TypeError:
                barra.progress(1.0)
            estado.caption("Listo")
            st.success(f"Guardado: `{ruta}`")
            st.download_button(
                "Descargar PDF",
                data=ruta.read_bytes(),
                file_name=ruta.name,
                mime="application/pdf",
                key="granja_dl_pdf_mensual_energia",
            )
        except Exception as exc:
            st.error(f"No se pudo generar el PDF: {exc}")


def _tab_reportes() -> None:
    opciones = (
        "Reporte Diario",
        "Mensual Ingresos",
        "Mensual Energía",
    )
    if st.session_state.get("granja_reporte_tipo") == "Reporte Mensual":
        st.session_state["granja_reporte_tipo"] = "Mensual Ingresos"
    if st.session_state.get("granja_reporte_tipo") not in opciones:
        st.session_state["granja_reporte_tipo"] = "Reporte Diario"

    tipo = st.radio(
        "Tipo de reporte",
        list(opciones),
        horizontal=True,
        key="granja_reporte_tipo",
    )
    if tipo == "Reporte Diario":
        _tab_pdf_diario()
    elif tipo == "Mensual Ingresos":
        _tab_pdf_mensual_ingresos()
    else:
        _tab_pdf_mensual_energia()


def run_pages(*, desde_suite: bool = False) -> None:
    init_session()
    asegurar_megas_en_catalogo()

    if st.session_state.pop("_logout_pendiente", False):
        from bess.ui.auth import logout

        logout()
        st.rerun()

    if not desde_suite and not st.session_state.get("autenticado"):
        preparar_ui_login()
        aplicar_estilos_login()
        _login_granja()
        if not st.session_state.get("autenticado"):
            return
        st.rerun()
    elif desde_suite and not st.session_state.get("autenticado"):
        return

    es_superadmin = rol_es_superadmin(st.session_state.get("rol"))
    restaurar_ui_app(restaurar_sidebar=es_superadmin)
    aplicar_estilos()
    if not es_superadmin:
        st.markdown(
            '<div class="bess-rol-user" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
    _ajustar_sidebar_por_rol(es_superadmin)

    from streamlit_autorefresh import st_autorefresh

    # Solo recarga la vista; la sync pesada corre en cron (no bloquear la UI).
    tick = st_autorefresh(interval=15 * 60 * 1000, key="granja_autorefresh_datos")
    prev_tick = st.session_state.get("_granja_refresh_tick", -1)
    if int(tick or 0) > prev_tick:
        st.session_state["_granja_refresh_tick"] = int(tick or 0)
        if int(tick or 0) > 0:
            _rango_fechas_cached.clear()
            _resumen_rango_cached.clear()

    _render_header(desde_suite=desde_suite)

    # Migrar clave antigua de sesión
    if st.session_state.get("granja_seccion") == "Reporte PDF":
        st.session_state["granja_seccion"] = "Reportes"

    if st.session_state.get("granja_seccion") not in ("Dashboard", "Reportes"):
        st.session_state["granja_seccion"] = "Dashboard"

    seccion = st.radio(
        "Sección",
        ["Dashboard", "Reportes"],
        horizontal=True,
        key="granja_seccion",
        label_visibility="collapsed",
    )

    if es_superadmin:
        with st.sidebar:
            _sidebar_branding()
            st.divider()
            _sidebar_sync()

    if seccion == "Dashboard":
        _tab_dashboard()
    else:
        _tab_reportes()


def _login_granja() -> None:
    """Login con branding Granja (mismo logo IUSASOL que BESS)."""
    st.markdown('<div class="login-page-marker"></div>', unsafe_allow_html=True)
    try:
        usuarios = get_usuarios()
    except (RuntimeError, ValueError) as exc:
        _, col, _ = st.columns([3, 4, 3])
        with col:
            st.error(str(exc))
        return

    _, col, _ = st.columns([3, 4, 3])
    with col:
        logo_html = obtener_logo_html(288)
        logo_block = (
            f'<div class="login-logo-wrap">'
            f'<div style="background:white;border-radius:10px;padding:8px 14px;'
            f'box-shadow:0 1px 4px rgba(0,0,0,0.04);">{logo_html}</div></div>'
            if logo_html
            else ""
        )
        st.markdown(
            f"""
            <div class="login-brand">
                {logo_block}
                <h1 class="login-title">{NOMBRE_APP}</h1>
                <p class="login-subtitle">Energía e ingresos DIST · 21 MEGAs</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            with st.form("login_granja"):
                usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
                password = st.text_input(
                    "Contraseña", type="password", placeholder="Ingresa tu contraseña"
                )
                submit = st.form_submit_button(
                    "Iniciar Sesión", use_container_width=True, type="primary"
                )
                if submit and usuario and password:
                    registro = usuarios.get(usuario)
                    if registro and verificar_password(password, registro["password"]):
                        st.session_state.autenticado = True
                        st.session_state.usuario = usuario
                        st.session_state.rol = registro["rol"]
                        st.session_state.pop("sidebar_inicial_aplicada", None)
                        st.cache_data.clear()
                    else:
                        st.error("Usuario o contraseña incorrectos")


def _render_header(*, desde_suite: bool = False) -> None:
    """Encabezado con logo IUSASOL; acciones de sesión en barra (no sidebar)."""
    from bess.ui.components import (
        boton_cerrar_sesion,
        boton_volver_suite,
        en_suite,
        marcar_barra_sesion,
    )

    logo_html = obtener_logo_html(288)
    usuario = st.session_state.get("usuario", "")
    try:
        nombre = get_usuarios().get(usuario, {}).get("nombre", usuario)
    except Exception:
        nombre = usuario
    rol = st.session_state.get("rol")
    rol_tipo = ETIQUETA_ROL.get(rol or "user", "Usuario")
    logo_block = (
        f'<div style="flex-shrink:0;background:white;border-radius:8px;'
        f'padding:4px 8px;">{logo_html}</div>'
        if logo_html
        else ""
    )
    if en_suite():
        c1, c2, c3 = st.columns([5, 1.5, 1.3])
    else:
        c1, c3 = st.columns([6, 1.3])
        c2 = None
    with c1:
        marcar_barra_sesion()
        st.markdown(
            f"""
            <div class="app-header">
                {logo_block}
                <div>
                    <h1 class="app-header-title">{NOMBRE_APP}</h1>
                    <p class="app-header-sub">{rol_tipo}: {nombre} ·
                       21 MEGAs · DIST · {CAPACIDAD_MW:.0f} MW · v{VERSION}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"Perfil 5 min · Sync desde {FECHA_INICIO_SYNC}"
        )
    if c2 is not None:
        with c2:
            st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
            boton_volver_suite(key="granja_hdr_volver_suite")
    with c3:
        st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
        boton_cerrar_sesion(key="granja_hdr_logout")


def _sidebar_branding() -> None:
    """Bloque de marca en sidebar (mismo estilo degradado que BESS)."""
    logo_html = obtener_logo_html(220)
    logo_block = (
        f'<div style="background:white;border-radius:8px;padding:6px 10px;'
        f'display:inline-block;margin-bottom:8px;">{logo_html}</div>'
        if logo_html
        else f'<h2 style="color:white;margin:0;font-size:18px;">{NOMBRE_APP}</h2>'
    )
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#1a5276,#2e86c1);
                    padding:16px;border-radius:12px;text-align:center;margin-bottom:8px;">
            {logo_block}
            <p style="color:rgba(255,255,255,0.9);margin:4px 0 0;font-size:12px;font-weight:500;">
                Granja Solar · Panel local · v{VERSION}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"**{st.session_state.get('usuario', '')}**")
    st.caption(f"Rol: {st.session_state.get('rol', '')}")
