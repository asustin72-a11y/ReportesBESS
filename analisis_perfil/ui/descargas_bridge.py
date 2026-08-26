"""Descargas API embebidas en el flujo de Análisis de Perfil."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bess.config.paths import PROJECT_ROOT

ZONA = ZoneInfo("America/Mexico_City")


@dataclass
class MemFile:
    """Sustituto de UploadedFile para perfiles bajados de la API."""

    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


def ensure_reporteador_path() -> Path:
    """Compat: el módulo ya vive dentro de ReporteadorIUSASOL."""
    return PROJECT_ROOT


def _hoy() -> date:
    return datetime.now(ZONA).date()


def _blob_a_archivos(blob: bytes, nombre: str) -> list[MemFile]:
    """CSV único o ZIP → lista de MemFile (solo CSV de perfil)."""
    if nombre.lower().endswith(".csv"):
        return [MemFile(name=Path(nombre).name, data=blob)]
    out: list[MemFile] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            base = Path(info.filename).name
            low = base.lower()
            if not low.endswith(".csv") or base.startswith("."):
                continue
            if "__macosx" in info.filename.lower():
                continue
            out.append(MemFile(name=base, data=zf.read(info)))
    if not out:
        raise ValueError("El ZIP de la API no contenía CSV utilizables.")
    return out


def _import_descargas():
    from descargas.config import AVISO_GRANJA_REQUESTS, SECCIONES
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
    from bess.data.ingest.iusasol.client import IusasolError

    return {
        "AVISO_GRANJA_REQUESTS": AVISO_GRANJA_REQUESTS,
        "SECCIONES": SECCIONES,
        "MedidorInfo": MedidorInfo,
        "crear_clientes": crear_clientes,
        "descargar_clientes_csv": descargar_clientes_csv,
        "descargar_granja_csv": descargar_granja_csv,
        "descargar_porteo_csv": descargar_porteo_csv,
        "estimar_requests_granja": estimar_requests_granja,
        "listar_medidores_clientes": listar_medidores_clientes,
        "listar_medidores_granja": listar_medidores_granja,
        "listar_medidores_porteo": listar_medidores_porteo,
        "IusasolError": IusasolError,
    }


def _opciones_medidores(raw: list[dict]) -> dict[str, str]:
    opciones = {f"{r['etiqueta']}": r["idcode"] for r in raw}
    if len(opciones) < len(raw):
        opciones = {
            f"{r['etiqueta']} [{r['idcode'][:8]}…]": r["idcode"] for r in raw
        }
    return opciones


def _medidores_desde_elegidos(deps: dict, opciones: dict[str, str], elegidos: list[str]):
    MedidorInfo = deps["MedidorInfo"]
    return [
        MedidorInfo(idcode=opciones[e], etiqueta=e.split(" [")[0])
        for e in elegidos
    ]


def _descargar_lado(
    deps: dict,
    seccion: str,
    medidores: list,
    desde: date,
    hasta: date,
    progress,
) -> tuple[list[MemFile], str, int]:
    isol, farm, porteo = deps["crear_clientes"]()
    if seccion == "clientes":
        blob, nombre = deps["descargar_clientes_csv"](
            isol, medidores, desde, hasta, progress=progress
        )
    elif seccion == "granja":
        blob, nombre = deps["descargar_granja_csv"](
            farm, medidores, desde, hasta, progress=progress
        )
    else:
        blob, nombre = deps["descargar_porteo_csv"](
            porteo, medidores, desde, hasta, progress=progress
        )
    return _blob_a_archivos(blob, nombre), nombre, len(blob)


def _chip_perfiles(etiqueta: str, archivos: list[MemFile]) -> None:
    import streamlit as st

    if not archivos:
        return
    nombres = ", ".join(a.name for a in archivos)
    st.markdown(
        f'<div class="metric-chip">'
        f"{etiqueta} · <strong>{len(archivos)}</strong> perfil(es): {nombres}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if len(archivos) >= 2:
        st.caption("Al generar, se sumarán por FECHA.")


def render_descarga_en_flujo(
    *,
    session_key: str,
    reset: int,
    titulo: str = "Descargar de la API",
) -> list[MemFile]:
    """UI compacta de descarga; deja los perfiles listos en session_state[session_key]."""
    import streamlit as st

    actuales: list[MemFile] = list(st.session_state.get(session_key) or [])

    try:
        deps = _import_descargas()
    except Exception as exc:
        st.error(f"No se pudo cargar Descargas API: {exc}")
        st.caption(
            f"Credenciales en `{PROJECT_ROOT / '.streamlit' / 'secrets.toml'}` "
            "o variables IUSASOL_*."
        )
        return actuales

    st.markdown(f"**{titulo}**")
    claves = [k for k, _ in deps["SECCIONES"]]
    etiquetas = {k: e for k, e in deps["SECCIONES"]}
    seccion = st.radio(
        "Fuente API",
        claves,
        format_func=lambda k: etiquetas[k],
        horizontal=True,
        key=f"api_sec_{session_key}_{reset}",
        label_visibility="collapsed",
    )

    hoy = _hoy()
    c1, c2 = st.columns(2)
    with c1:
        desde = st.date_input(
            "Desde (API)",
            value=hoy - timedelta(days=1),
            key=f"api_desde_{session_key}_{reset}",
            format="DD/MM/YYYY",
        )
    with c2:
        hasta = st.date_input(
            "Hasta (API)",
            value=hoy,
            key=f"api_hasta_{session_key}_{reset}",
            format="DD/MM/YYYY",
        )
    if hasta < desde:
        st.error("La fecha fin API debe ser ≥ inicio.")
        return actuales

    @st.cache_data(ttl=300, show_spinner="Listando medidores…")
    def _listar(sec: str) -> list[dict]:
        isol, farm, porteo = deps["crear_clientes"]()
        if sec == "clientes":
            items = deps["listar_medidores_clientes"](isol)
        elif sec == "granja":
            items = deps["listar_medidores_granja"](farm)
        else:
            items = deps["listar_medidores_porteo"](porteo)
        return [
            {"idcode": m.idcode, "etiqueta": m.etiqueta, "serial": m.serial}
            for m in items
        ]

    try:
        raw = _listar(seccion)
    except Exception as exc:
        st.error(f"No se pudieron listar medidores: {exc}")
        if st.button("Reintentar listado", key=f"api_retry_{session_key}_{reset}"):
            _listar.clear()
            st.rerun()
        return actuales

    if not raw:
        st.warning("La API no devolvió medidores.")
        return actuales

    opciones = _opciones_medidores(raw)
    elegidos = st.multiselect(
        "Medidores",
        options=list(opciones.keys()),
        default=[],
        key=f"api_meds_{session_key}_{reset}",
    )

    if seccion == "granja" and elegidos:
        n_req = deps["estimar_requests_granja"](len(elegidos), desde, hasta)
        st.caption(f"Granja ≈ {n_req} requests (1/día/medidor).")
        if n_req > deps["AVISO_GRANJA_REQUESTS"]:
            st.warning(
                f"Más de {deps['AVISO_GRANJA_REQUESTS']} requests; puede tardar."
            )

    _, col_mid, _ = st.columns([1.5, 1.2, 1.5])
    with col_mid:
        generar = st.button(
            "Obtener perfiles",
            type="primary",
            disabled=not elegidos,
            use_container_width=True,
            key=f"api_gen_{session_key}_{reset}",
        )
        if actuales and st.button(
            "Quitar perfiles API",
            use_container_width=True,
            key=f"api_clear_{session_key}_{reset}",
        ):
            st.session_state.pop(session_key, None)
            st.rerun()

    if generar and elegidos:
        medidores = _medidores_desde_elegidos(deps, opciones, elegidos)
        barra = st.progress(0.0, text="Conectando…")

        def _prog(frac: float, msg: str) -> None:
            barra.progress(min(max(frac, 0.0), 1.0), text=msg)

        try:
            archivos, nombre, nbytes = _descargar_lado(
                deps, seccion, medidores, desde, hasta, _prog
            )
            st.session_state[session_key] = archivos
            actuales = archivos
            barra.empty()
            st.success(
                f"Listos para análisis: {len(archivos)} perfil(es) "
                f"({nombre}, {nbytes:,} bytes)."
            )
        except (deps["IusasolError"], ValueError) as exc:
            barra.empty()
            st.error(str(exc))
        except Exception as exc:
            barra.empty()
            st.error(f"Error inesperado: {exc}")

    actuales = list(st.session_state.get(session_key) or [])
    _chip_perfiles("API", actuales)
    return actuales


def render_descarga_bidireccional(
    *,
    reset: int,
    incluir_consumo: bool,
    incluir_generacion: bool,
    session_key_consumo: str = "api_perfiles_consumo",
    session_key_generacion: str = "api_perfiles_generacion",
) -> tuple[list[MemFile], list[MemFile]]:
    """Un rango de fechas y un botón para bajar consumo y/o generación."""
    import streamlit as st

    vacio: list[MemFile] = []
    actuales_c: list[MemFile] = (
        list(st.session_state.get(session_key_consumo) or [])
        if incluir_consumo
        else vacio
    )
    actuales_g: list[MemFile] = (
        list(st.session_state.get(session_key_generacion) or [])
        if incluir_generacion
        else vacio
    )

    if not incluir_consumo and not incluir_generacion:
        return vacio, vacio

    try:
        deps = _import_descargas()
    except Exception as exc:
        st.error(f"No se pudo cargar Descargas API: {exc}")
        st.caption(
            f"Credenciales en `{PROJECT_ROOT / '.streamlit' / 'secrets.toml'}` "
            "o variables IUSASOL_*."
        )
        return actuales_c, actuales_g

    st.markdown("**API · bidireccional**")
    st.caption(
        "Un solo rango de fechas y un botón para ambos lados. "
        "Elija medidores de consumo y/o generación."
    )

    claves = [k for k, _ in deps["SECCIONES"]]
    etiquetas = {k: e for k, e in deps["SECCIONES"]}
    seccion = st.radio(
        "Fuente API",
        claves,
        format_func=lambda k: etiquetas[k],
        horizontal=True,
        key=f"api_bidi_sec_{reset}",
        label_visibility="collapsed",
    )

    hoy = _hoy()
    c1, c2 = st.columns(2)
    with c1:
        desde = st.date_input(
            "Desde (API)",
            value=hoy - timedelta(days=1),
            key=f"api_bidi_desde_{reset}",
            format="DD/MM/YYYY",
        )
    with c2:
        hasta = st.date_input(
            "Hasta (API)",
            value=hoy,
            key=f"api_bidi_hasta_{reset}",
            format="DD/MM/YYYY",
        )
    if hasta < desde:
        st.error("La fecha fin API debe ser ≥ inicio.")
        return actuales_c, actuales_g

    @st.cache_data(ttl=300, show_spinner="Listando medidores…")
    def _listar(sec: str) -> list[dict]:
        isol, farm, porteo = deps["crear_clientes"]()
        if sec == "clientes":
            items = deps["listar_medidores_clientes"](isol)
        elif sec == "granja":
            items = deps["listar_medidores_granja"](farm)
        else:
            items = deps["listar_medidores_porteo"](porteo)
        return [
            {"idcode": m.idcode, "etiqueta": m.etiqueta, "serial": m.serial}
            for m in items
        ]

    try:
        raw = _listar(seccion)
    except Exception as exc:
        st.error(f"No se pudieron listar medidores: {exc}")
        if st.button("Reintentar listado", key=f"api_bidi_retry_{reset}"):
            _listar.clear()
            st.rerun()
        return actuales_c, actuales_g

    if not raw:
        st.warning("La API no devolvió medidores.")
        return actuales_c, actuales_g

    opciones = _opciones_medidores(raw)
    labels = list(opciones.keys())

    elegidos_c: list[str] = []
    elegidos_g: list[str] = []
    cols = st.columns(2 if (incluir_consumo and incluir_generacion) else 1)
    idx = 0
    if incluir_consumo:
        with cols[idx]:
            elegidos_c = st.multiselect(
                "Medidores de consumo",
                options=labels,
                default=[],
                key=f"api_bidi_meds_c_{reset}",
            )
        idx += 1
    if incluir_generacion:
        with cols[idx]:
            elegidos_g = st.multiselect(
                "Medidores de generación",
                options=labels,
                default=[],
                key=f"api_bidi_meds_g_{reset}",
            )

    n_meds = len(elegidos_c) + len(elegidos_g)
    if seccion == "granja" and n_meds:
        n_req = deps["estimar_requests_granja"](n_meds, desde, hasta)
        st.caption(f"Granja ≈ {n_req} requests (1/día/medidor).")
        if n_req > deps["AVISO_GRANJA_REQUESTS"]:
            st.warning(
                f"Más de {deps['AVISO_GRANJA_REQUESTS']} requests; puede tardar."
            )

    listo_para_bajar = True
    if incluir_consumo and not elegidos_c:
        listo_para_bajar = False
    if incluir_generacion and not elegidos_g:
        listo_para_bajar = False

    _, col_mid, _ = st.columns([1.5, 1.2, 1.5])
    with col_mid:
        generar = st.button(
            "Obtener perfiles",
            type="primary",
            disabled=not listo_para_bajar,
            use_container_width=True,
            key=f"api_bidi_gen_{reset}",
        )
        hay_algo = bool(actuales_c or actuales_g)
        if hay_algo and st.button(
            "Quitar perfiles API",
            use_container_width=True,
            key=f"api_bidi_clear_{reset}",
        ):
            if incluir_consumo:
                st.session_state.pop(session_key_consumo, None)
            if incluir_generacion:
                st.session_state.pop(session_key_generacion, None)
            st.rerun()

    if generar and listo_para_bajar:
        barra = st.progress(0.0, text="Conectando…")
        n_lados = (1 if incluir_consumo else 0) + (1 if incluir_generacion else 0)
        hechos = 0

        def _prog_lado(base: float, span: float):
            def _inner(frac: float, msg: str) -> None:
                barra.progress(
                    min(max(base + span * frac, 0.0), 1.0),
                    text=msg,
                )

            return _inner

        try:
            msgs: list[str] = []
            if incluir_consumo:
                meds_c = _medidores_desde_elegidos(deps, opciones, elegidos_c)
                archivos_c, nombre_c, nbytes_c = _descargar_lado(
                    deps,
                    seccion,
                    meds_c,
                    desde,
                    hasta,
                    _prog_lado(hechos / n_lados, 1 / n_lados),
                )
                st.session_state[session_key_consumo] = archivos_c
                actuales_c = archivos_c
                msgs.append(
                    f"consumo {len(archivos_c)} ({nombre_c}, {nbytes_c:,} B)"
                )
                hechos += 1
            if incluir_generacion:
                meds_g = _medidores_desde_elegidos(deps, opciones, elegidos_g)
                archivos_g, nombre_g, nbytes_g = _descargar_lado(
                    deps,
                    seccion,
                    meds_g,
                    desde,
                    hasta,
                    _prog_lado(hechos / n_lados, 1 / n_lados),
                )
                st.session_state[session_key_generacion] = archivos_g
                actuales_g = archivos_g
                msgs.append(
                    f"generación {len(archivos_g)} ({nombre_g}, {nbytes_g:,} B)"
                )
            barra.empty()
            st.success("Listos para análisis: " + " · ".join(msgs) + ".")
        except (deps["IusasolError"], ValueError) as exc:
            barra.empty()
            st.error(str(exc))
        except Exception as exc:
            barra.empty()
            st.error(f"Error inesperado: {exc}")

    if incluir_consumo:
        actuales_c = list(st.session_state.get(session_key_consumo) or [])
        _chip_perfiles("API consumo", actuales_c)
    if incluir_generacion:
        actuales_g = list(st.session_state.get(session_key_generacion) or [])
        _chip_perfiles("API generación", actuales_g)

    return (
        actuales_c if incluir_consumo else vacio,
        actuales_g if incluir_generacion else vacio,
    )
