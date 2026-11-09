"""Componentes reutilizables de la UI Streamlit."""

from __future__ import annotations

import base64
import os
from datetime import date, datetime, timedelta

import streamlit as st

from bess.config.paths import DIRECTORIO_BASE

CREDITO_COPYRIGHT = "Copyright © 2025-2026. Industrias Unidas, S.A. de C.V."
CREDITO_AUTOR = "Diseñado y Desarrollado por: SanTo."


def html_creditos_plataforma(*, variante: str = "login") -> str:
    """Pie de créditos (login / sidebar)."""
    cls = "bess-creditos"
    if variante == "sidebar":
        cls += " bess-creditos-sidebar"
    return (
        f'<div class="{cls}">'
        f"<p>{CREDITO_COPYRIGHT}</p>"
        f"<p>{CREDITO_AUTOR}</p>"
        f"</div>"
    )


def section_header(titulo, descripcion="", compact=False):
    cls = "section-title-sm" if compact else "section-title"
    html = f'<p class="{cls}">{titulo}</p>'
    if descripcion:
        html += f'<p class="section-desc">{descripcion}</p>'
    st.markdown(html, unsafe_allow_html=True)


def _seleccionar_subnav(state_key: str, key: str) -> None:
    st.session_state[state_key] = key


def subnav_en_panel(
    etiqueta: str,
    opciones: list[tuple[str, str]],
    state_key: str,
) -> str:
    """Botones de sub-sección dentro de un contenedor con borde. Devuelve la clave activa."""
    if state_key not in st.session_state:
        st.session_state[state_key] = opciones[0][0]
    activa = st.session_state[state_key]
    if activa not in {k for k, _ in opciones}:
        activa = opciones[0][0]
        st.session_state[state_key] = activa

    with st.container(border=True):
        st.markdown(
            '<span class="bess-subnav-panel-marker" aria-hidden="true"></span>'
            f'<p class="bess-subnav-panel-label">{etiqueta}</p>',
            unsafe_allow_html=True,
        )
        cols = st.columns(len(opciones), gap="small")
        for col, (key, label) in zip(cols, opciones):
            with col:
                es_activa = activa == key
                marcador = (
                    '<span class="bess-subnav-col-marker bess-subnav-active" aria-hidden="true"></span>'
                    if es_activa
                    else '<span class="bess-subnav-col-marker" aria-hidden="true"></span>'
                )
                st.markdown(marcador, unsafe_allow_html=True)
                st.button(
                    label,
                    key=f"subnav_{state_key}_{key}",
                    on_click=_seleccionar_subnav,
                    kwargs={"state_key": state_key, "key": key},
                    type="primary" if es_activa else "secondary",
                    use_container_width=False,
                )
    return st.session_state[state_key]


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


def como_fecha(valor) -> date | None:
    """Normaliza date o datetime de un date_input."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def rango_desplazado(
    inicio: date,
    fin: date,
    dias: int,
    fecha_min: date,
    fecha_max: date,
) -> tuple[date, date] | None:
    """Mueve el periodo `dias` días si el resultado cabe en los datos.

    Un día suelto (inicio == fin) avanza o retrocede un día. Un rango
    conserva su longitud y se desliza un día.
    """
    if inicio > fin or dias == 0:
        return None
    nuevo_ini = inicio + timedelta(days=dias)
    nuevo_fin = fin + timedelta(days=dias)
    if nuevo_ini < fecha_min or nuevo_fin > fecha_max:
        return None
    return nuevo_ini, nuevo_fin


def _asegurar_fecha_sesion(key: str, defecto: date, fecha_min: date, fecha_max: date) -> date:
    """Deja en sesión una fecha dentro del rango antes de crear el date_input."""
    actual = como_fecha(st.session_state.get(key))
    if actual is None:
        actual = defecto
    if actual < fecha_min:
        actual = fecha_min
    elif actual > fecha_max:
        actual = fecha_max
    st.session_state[key] = actual
    return actual


def _boton_recorrer_dia(
    *,
    etiqueta: str,
    ayuda: str,
    key: str,
    habilitado: bool,
    aplicar,
) -> None:
    if st.button(
        etiqueta,
        help=ayuda,
        key=key,
        use_container_width=True,
        disabled=not habilitado,
    ):
        if aplicar():
            st.rerun()


def _aplicar_desplazamiento(
    key_inicio: str,
    key_fin: str,
    dias: int,
    fecha_min: date,
    fecha_max: date,
) -> bool:
    inicio = como_fecha(st.session_state.get(key_inicio))
    fin = como_fecha(st.session_state.get(key_fin))
    if inicio is None or fin is None:
        return False
    nuevo = rango_desplazado(inicio, fin, dias, fecha_min, fecha_max)
    if nuevo is None:
        return False
    st.session_state[key_inicio], st.session_state[key_fin] = nuevo
    return True


def render_controles_rango(
    *,
    key_inicio: str,
    key_fin: str,
    key_atras: str,
    key_adelante: str,
    fecha_def: date,
    fecha_min: date,
    fecha_max: date,
) -> tuple[date, date]:
    """Desde / Hasta con botones para deslizar el periodo un día."""
    fecha_def = como_fecha(fecha_def) or fecha_min
    fecha_min = como_fecha(fecha_min) or fecha_def
    fecha_max = como_fecha(fecha_max) or fecha_def
    inicio_act = _asegurar_fecha_sesion(key_inicio, fecha_def, fecha_min, fecha_max)
    fin_act = _asegurar_fecha_sesion(key_fin, fecha_def, fecha_min, fecha_max)
    puede_atras = inicio_act > fecha_min and inicio_act <= fin_act
    puede_adelante = fin_act < fecha_max and inicio_act <= fin_act

    c_prev, c_desde, c_hasta, c_dias, c_next = st.columns(
        [0.85, 2, 2, 0.75, 0.85],
        gap="small",
        vertical_alignment="bottom",
    )
    with c_prev:
        _boton_recorrer_dia(
            etiqueta="◀ Ant.",
            ayuda="Recorre el periodo un día hacia atrás",
            key=key_atras,
            habilitado=puede_atras,
            aplicar=lambda: _aplicar_desplazamiento(
                key_inicio, key_fin, -1, fecha_min, fecha_max
            ),
        )
    with c_desde:
        fecha_inicio = st.date_input(
            "Desde",
            min_value=fecha_min,
            max_value=fecha_max,
            key=key_inicio,
            format="DD/MM/YYYY",
        )
    with c_hasta:
        fecha_fin = st.date_input(
            "Hasta",
            min_value=fecha_min,
            max_value=fecha_max,
            key=key_fin,
            format="DD/MM/YYYY",
        )
    with c_dias:
        dias = (fecha_fin - fecha_inicio).days + 1
        st.metric("Días", dias)
    with c_next:
        _boton_recorrer_dia(
            etiqueta="Sig. ▶",
            ayuda="Recorre el periodo un día hacia adelante",
            key=key_adelante,
            habilitado=puede_adelante,
            aplicar=lambda: _aplicar_desplazamiento(
                key_inicio, key_fin, 1, fecha_min, fecha_max
            ),
        )
    return fecha_inicio, fecha_fin


def render_selector_fecha_unica(
    titulo, descripcion, label, fecha_def, fecha_min, fecha_max, key,
    metric_label=None, metric_fn=None,
):
    """Panel compacto con un date_input y avance de un día."""
    fecha_def = como_fecha(fecha_def) or fecha_min
    fecha_min = como_fecha(fecha_min) or fecha_def
    fecha_max = como_fecha(fecha_max) or fecha_def
    fecha_act = _asegurar_fecha_sesion(key, fecha_def, fecha_min, fecha_max)
    with st.container(border=True):
        st.markdown(
            '<span class="panel-fecha-unica-anchor" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        section_header(titulo, descripcion, compact=True)
        if metric_label and metric_fn:
            c_prev, col_fecha, col_info, c_next = st.columns(
                [0.85, 3, 1, 0.85],
                gap="small",
                vertical_alignment="bottom",
            )
        else:
            c_prev, col_fecha, c_next = st.columns(
                [0.85, 3, 0.85],
                gap="small",
                vertical_alignment="bottom",
            )
            col_info = None
        with c_prev:
            _boton_recorrer_dia(
                etiqueta="◀ Ant.",
                ayuda="Día anterior",
                key=f"{key}_dia_ant",
                habilitado=fecha_act > fecha_min,
                aplicar=lambda: _aplicar_desplazamiento(
                    key, key, -1, fecha_min, fecha_max
                ),
            )
        with col_fecha:
            fecha = st.date_input(
                label,
                min_value=fecha_min,
                max_value=fecha_max,
                key=key,
                format="DD/MM/YYYY",
            )
        if col_info is not None:
            with col_info:
                metric_compact(metric_label, metric_fn(fecha))
        with c_next:
            _boton_recorrer_dia(
                etiqueta="Sig. ▶",
                ayuda="Día siguiente",
                key=f"{key}_dia_sig",
                habilitado=fecha_act < fecha_max,
                aplicar=lambda: _aplicar_desplazamiento(
                    key, key, 1, fecha_min, fecha_max
                ),
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


def en_suite() -> bool:
    """True si la sesión entró desde el selector de la Suite."""
    return bool(st.session_state.get("suite_modulo"))


def boton_volver_suite(*, key: str) -> None:
    """Botón «Volver a la Suite» para barra superior (no sidebar)."""
    if not en_suite():
        return
    if st.button("Volver a la Suite", use_container_width=True, key=key):
        st.session_state.pop("suite_modulo", None)
        st.session_state.pop("sidebar_inicial_aplicada", None)
        st.rerun()


def boton_cerrar_sesion(*, key: str) -> None:
    """Botón «Cerrar sesión» para barra superior (no sidebar)."""
    if st.button("Cerrar sesión", use_container_width=True, key=key):
        st.session_state["_logout_pendiente"] = True
        st.rerun()


def marcar_barra_sesion() -> None:
    """Ancla CSS para apilar título + acciones en pantallas angostas."""
    st.markdown(
        '<div class="suite-session-bar-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )


def marcar_fila_controles() -> None:
    """Ancla CSS para envolver filas densas de controles (atajos, fechas)."""
    st.markdown(
        '<div class="suite-controls-row-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )