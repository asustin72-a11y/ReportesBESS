"""Páginas: Clientes / Granja / Porteo → CSV."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

from bess.data.ingest.iusasol.client import IusasolError
from bess.ui.components import obtener_logo_html
from bess.ui.styles import aplicar_estilos

from descargas import NOMBRE_APP
from descargas.config import AVISO_GRANJA_REQUESTS, SECCIONES, ZONA
from descargas.service import (
    MedidorInfo,
    crear_clientes,
    descargar_clientes_csv,
    descargar_granja_csv,
    descargar_porteo_csv,
    estimar_requests_granja,
    listar_medidores_clientes,
    listar_medidores_granja,
    listar_medidores_porteo,
)

# Login desactivado en entry standalone; en la suite BESS usa auth propia.


def render_panel_descargas(*, mostrar_titulo: bool = True) -> None:
    """Panel embebible (suite BESS) o contenido principal del entry standalone."""
    if mostrar_titulo:
        st.markdown(
            f"""
            <div style="margin-bottom:12px;">
                <div style="font-size:1.25rem;font-weight:700;">{NOMBRE_APP}</div>
                <div style="opacity:0.75;font-size:0.9rem;">
                    Clientes · Granja · Porteo → CSV (API IUSASOL)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    claves = [k for k, _ in SECCIONES]
    etiquetas = {k: e for k, e in SECCIONES}
    if st.session_state.get("descargas_seccion") not in claves:
        st.session_state["descargas_seccion"] = claves[0]

    seccion = st.radio(
        "Sección",
        claves,
        format_func=lambda k: etiquetas[k],
        horizontal=True,
        key="descargas_seccion",
        label_visibility="collapsed",
    )
    _tab_descarga(seccion)


def run_pages() -> None:
    """Entry standalone (`streamlit_descargas.py`): sin login por ahora."""
    aplicar_estilos()
    _render_header()
    with st.sidebar:
        _sidebar()
    render_panel_descargas(mostrar_titulo=False)


def _hoy() -> date:
    return datetime.now(ZONA).date()


def _render_header() -> None:
    logo_html = obtener_logo_html(288)
    logo_block = (
        f'<div style="flex-shrink:0;background:white;border-radius:8px;'
        f'padding:4px 8px;">{logo_html}</div>'
        if logo_html
        else ""
    )
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:8px;">
            {logo_block}
            <div>
                <div style="font-size:1.35rem;font-weight:700;">{NOMBRE_APP}</div>
                <div style="opacity:0.75;font-size:0.9rem;">Clientes · Granja · Porteo → CSV</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _sidebar() -> None:
    st.markdown("### Descarga API")
    st.caption(
        "Clientes = ISOL · Granja = Farm · Porteo = Reports/Porteo. "
        "No escribe en SQLite ni al pipeline BESS."
    )


@st.cache_data(ttl=300, show_spinner="Listando medidores…")
def _cached_listar(seccion: str) -> list[dict]:
    isol, farm, porteo = crear_clientes()
    if seccion == "clientes":
        items = listar_medidores_clientes(isol)
    elif seccion == "granja":
        items = listar_medidores_granja(farm)
    elif seccion == "porteo":
        items = listar_medidores_porteo(porteo)
    else:
        items = []
    return [
        {"idcode": m.idcode, "etiqueta": m.etiqueta, "serial": m.serial}
        for m in items
    ]


def _tab_descarga(seccion: str) -> None:
    st.subheader(
        {"clientes": "Clientes (ISOL)", "granja": "Granja (Farm)", "porteo": "Porteo"}.get(
            seccion, seccion
        )
    )

    col_a, col_b = st.columns(2)
    hoy = _hoy()
    with col_a:
        desde = st.date_input("Desde", value=hoy - timedelta(days=1), key=f"desde_{seccion}")
    with col_b:
        hasta = st.date_input("Hasta", value=hoy, key=f"hasta_{seccion}")

    if hasta < desde:
        st.error("La fecha fin debe ser mayor o igual a la fecha inicio.")
        return

    try:
        raw = _cached_listar(seccion)
    except Exception as exc:
        st.error(f"No se pudieron listar medidores: {exc}")
        if st.button("Reintentar listado", key=f"retry_{seccion}"):
            _cached_listar.clear()
            st.rerun()
        return

    if not raw:
        st.warning("La API no devolvió medidores en esta sección.")
        return

    opciones = {f"{r['etiqueta']}": r["idcode"] for r in raw}
    # etiquetas pueden repetirse; usar id en label si hay choque
    if len(opciones) < len(raw):
        opciones = {
            f"{r['etiqueta']} [{r['idcode'][:8]}…]": r["idcode"] for r in raw
        }

    elegidos = st.multiselect(
        "Medidores",
        options=list(opciones.keys()),
        default=[],
        key=f"meds_{seccion}",
    )

    if seccion == "granja" and elegidos:
        n_req = estimar_requests_granja(len(elegidos), desde, hasta)
        st.info(
            f"Granja usa 1 petición por día y medidor → **{n_req}** requests. "
            "Rangos largos pueden tardar."
        )
        if n_req > AVISO_GRANJA_REQUESTS:
            st.warning(
                f"Más de {AVISO_GRANJA_REQUESTS} requests. "
                "Considera un rango más corto o menos medidores."
            )

    if seccion == "clientes":
        st.caption("CSV: Fecha, KWH_REC, KWH_ENT, KVARH_Q1…Q4")
    elif seccion == "granja":
        st.caption("CSV: Fecha, kwh_rec (canal 0)")
    else:
        st.caption("CSV: mismo layout que Clientes (6 canales)")

    generar = st.button(
        "Generar descarga",
        type="primary",
        disabled=not elegidos,
        key=f"gen_{seccion}",
    )

    if not generar:
        if "descargas_blob" in st.session_state and st.session_state.get(
            "descargas_blob_seccion"
        ) == seccion:
            _mostrar_download()
        return

    medidores = [
        MedidorInfo(idcode=opciones[e], etiqueta=e.split(" [")[0])
        for e in elegidos
    ]

    barra = st.progress(0.0, text="Conectando…")

    def _prog(frac: float, msg: str) -> None:
        barra.progress(min(max(frac, 0.0), 1.0), text=msg)

    try:
        isol, farm, porteo = crear_clientes()
        if seccion == "clientes":
            blob, nombre = descargar_clientes_csv(
                isol, medidores, desde, hasta, progress=_prog
            )
        elif seccion == "granja":
            blob, nombre = descargar_granja_csv(
                farm, medidores, desde, hasta, progress=_prog
            )
        else:
            blob, nombre = descargar_porteo_csv(
                porteo, medidores, desde, hasta, progress=_prog
            )
    except (IusasolError, ValueError) as exc:
        barra.empty()
        st.error(str(exc))
        return
    except Exception as exc:
        barra.empty()
        st.error(f"Error inesperado: {exc}")
        return

    barra.empty()
    st.session_state["descargas_blob"] = blob
    st.session_state["descargas_nombre"] = nombre
    st.session_state["descargas_blob_seccion"] = seccion
    st.success(f"Listo: {nombre} ({len(blob):,} bytes)")
    _mostrar_download()


def _mostrar_download() -> None:
    blob = st.session_state.get("descargas_blob")
    nombre = st.session_state.get("descargas_nombre") or "perfil.csv"
    if not blob:
        return
    mime = (
        "application/zip"
        if str(nombre).lower().endswith(".zip")
        else "text/csv"
    )
    st.download_button(
        label=f"Descargar {nombre}",
        data=blob,
        file_name=nombre,
        mime=mime,
        type="primary",
        key=f"dl_{nombre}_{len(blob)}",
    )
