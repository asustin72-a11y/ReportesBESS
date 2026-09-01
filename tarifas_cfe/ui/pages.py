"""UI Consultar Tarifa — app hermana (login BESS, mismo aspecto suite)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from bess.config.paths import DIRECTORIO_BASE
from bess.config.users import ETIQUETA_ROL, verificar_password
from bess.data.ingest.cfe.catalog import (
    CATEGORIAS,
    INICIOS_VERANO,
    tarifas_por_categoria,
)
from bess.ui.auth import (
    get_usuarios,
    init_session,
    preparar_ui_login,
    restaurar_ui_app,
)
from bess.ui.components import (
    boton_cerrar_sesion,
    boton_volver_suite,
    en_suite,
    marcar_barra_sesion,
    obtener_logo_html,
)
from bess.ui.styles import aplicar_estilos, aplicar_estilos_login

from tarifas_cfe import NOMBRE_APP, VERSION

_DIR_REPORTES = DIRECTORIO_BASE / "ReportesTarifasCFE"

_MESES_LABEL = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def run_pages(*, desde_suite: bool = False) -> None:
    init_session()

    if st.session_state.pop("_logout_pendiente", False):
        from bess.ui.auth import logout

        logout()
        st.rerun()

    if not desde_suite and not st.session_state.get("autenticado"):
        preparar_ui_login()
        aplicar_estilos_login()
        _login_consultar_tarifa()
        if not st.session_state.get("autenticado"):
            return
        st.rerun()
    elif desde_suite and not st.session_state.get("autenticado"):
        return

    restaurar_ui_app(restaurar_sidebar=False)
    aplicar_estilos()
    from bess.ui.sidebar_cleanup import limpiar_residuos_nav_bess

    limpiar_residuos_nav_bess()
    _render_header()

    with st.sidebar:
        _sidebar_branding()
        st.divider()
        _sidebar_ayuda()

    if st.session_state.get("tcfe_seccion") not in ("Consulta", "Reportes CSV"):
        st.session_state["tcfe_seccion"] = "Consulta"

    seccion = st.radio(
        "Sección",
        ["Consulta", "Reportes CSV"],
        horizontal=True,
        key="tcfe_seccion",
        label_visibility="collapsed",
    )

    if seccion == "Consulta":
        _panel_consulta()
    else:
        _panel_descargas_reporte()

def _login_consultar_tarifa() -> None:
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
                <p class="login-subtitle">Cuotas CFE · Hogar · Negocio · Industria · Agrícola</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            with st.form("login_consultar_tarifa"):
                usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
                password = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="Ingresa tu contraseña",
                )
                submit = st.form_submit_button(
                    "Iniciar Sesión",
                    use_container_width=True,
                    type="primary",
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


def _render_header() -> None:
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
                       Solo consulta · v{VERSION}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Cuotas vigentes en app.cfe.mx · Reportes CSV locales")
    if c2 is not None:
        with c2:
            st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
            boton_volver_suite(key="tcfe_hdr_volver_suite")
    with c3:
        st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
        boton_cerrar_sesion(key="tcfe_hdr_logout")


def _sidebar_branding() -> None:
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
                Consultar Tarifa · Panel local
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"**{st.session_state.get('usuario', '')}**")
    st.caption(f"Rol: {st.session_state.get('rol', '')}")


def _sidebar_ayuda() -> None:
    st.markdown("### Tarifas CFE")
    st.caption(
        "Consulta a app.cfe.mx. No escribe CSV ni SQLite. "
        "La actualización DIST/GDMTH de BESS corre por cron aparte."
    )
    with st.expander("Tarifas disponibles", expanded=False):
        for cat in CATEGORIAS:
            items = tarifas_por_categoria(cat)
            if not items:
                continue
            st.markdown(f"**{cat}**")
            for t in items:
                st.caption(f"`{t.codigo}` — {t.nombre}")


def _cfe_client():
    """Import diferido: Playwright solo al consultar CFE, no al abrir el módulo."""
    from bess.data.ingest.cfe.tarifas_client import (
        CfeTarifasError,
        consultar_tarifa_catalogo,
        explorar_opciones_geo,
    )

    return CfeTarifasError, consultar_tarifa_catalogo, explorar_opciones_geo


def _panel_descargas_reporte() -> None:
    st.markdown(
        '<div class="section-container">'
        '<div class="section-title">Reportes CSV</div>'
        '<p class="section-desc">Un archivo por tarifa: '
        "AÑO · MES · REGIÓN (división de distribución) · TARIFA · BASE · "
        "INTERMEDIO · SEMIPUNTA · PUNTA · FIJO · CAPACIDAD · HORARIA. "
        "GEO: 17 divisiones CNE. "
        "Se generan con <code>scripts/reporte_tarifas_cfe.py</code>.</p>",
        unsafe_allow_html=True,
    )
    if not _DIR_REPORTES.is_dir():
        st.info("Aún no hay reportes generados en `data/ReportesTarifasCFE`.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    periodos = sorted(
        (p for p in _DIR_REPORTES.iterdir() if p.is_dir()),
        reverse=True,
    )
    if not periodos:
        st.info("Aún no hay reportes generados.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    with st.container(border=True):
        periodo = st.selectbox(
            "Periodo",
            periodos,
            format_func=lambda p: p.name,
            key="tcfe_rep_periodo",
        )
        archivos = sorted(periodo.glob("*.csv"))
        if not archivos:
            st.caption(f"Sin CSV en {periodo.name}.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        cols = st.columns(3)
        from bess.ui.components import marcar_fila_controles

        with cols[0]:
            marcar_fila_controles()
        for i, ruta in enumerate(archivos):
            with cols[i % 3]:
                st.download_button(
                    label=ruta.name,
                    data=ruta.read_bytes(),
                    file_name=ruta.name,
                    mime="text/csv",
                    key=f"tcfe_dl_{periodo.name}_{ruta.name}",
                    use_container_width=True,
                )
    st.markdown("</div>", unsafe_allow_html=True)


def _panel_consulta() -> None:
    hoy = date.today()
    st.markdown(
        '<div class="section-container">'
        '<div class="section-title">Consultar cuota vigente</div>'
        '<p class="section-desc">Seleccione categoría, tarifa y periodo. '
        "Las tarifas con región requieren Estado / Municipio / División.</p>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.2, 1.6, 1.2])
        with c1:
            categoria = st.selectbox("Categoría", CATEGORIAS, key="tcfe_cat")
        tarifas = tarifas_por_categoria(categoria)
        with c2:
            defn = st.selectbox(
                "Tarifa",
                tarifas,
                format_func=lambda t: f"{t.codigo} — {t.nombre}",
                key=f"tcfe_tarifa_{categoria}",
            )
        with c3:
            st.caption(defn.descripcion or "—")

        c_anio, c_mes, c_ver = st.columns(3)
        with c_anio:
            anio = st.number_input(
                "Año",
                min_value=2017,
                max_value=hoy.year + 1,
                value=hoy.year,
                step=1,
                key="tcfe_anio",
            )
        with c_mes:
            mes = st.selectbox(
                "Mes",
                list(range(1, 13)),
                index=hoy.month - 1,
                format_func=lambda m: _MESES_LABEL[m],
                key="tcfe_mes",
            )
        inicio_verano = ""
        with c_ver:
            if defn.requiere_inicio_verano:
                inicio_verano = st.selectbox(
                    "Inicio temporada verano",
                    INICIOS_VERANO,
                    index=len(INICIOS_VERANO) - 1,
                    key="tcfe_verano",
                )
            else:
                st.write("")

        estado = municipio = division = region_tabla = ""
        if defn.requiere_geo:
            st.markdown("##### Región tarifaria")
            g1, g2, g3 = st.columns(3)
            geo_cache_key = f"tcfe_geo_{defn.codigo}_{anio}_{mes}"
            if st.button("Cargar estados CFE", key="tcfe_btn_estados"):
                with st.spinner("Leyendo catálogo geográfico CFE…"):
                    try:
                        _, _, explorar_opciones_geo = _cfe_client()
                        st.session_state[geo_cache_key] = explorar_opciones_geo(
                            defn.url, anio=int(anio), mes=int(mes)
                        )
                    except Exception as exc:
                        st.error(f"No se pudieron cargar estados: {exc}")

            geo = st.session_state.get(geo_cache_key) or {}
            estados = geo.get("estados") or []
            with g1:
                if estados:
                    estado = st.selectbox("Estado", estados, key="tcfe_estado")
                else:
                    estado = st.text_input(
                        "Estado",
                        value="CIUDAD DE MÉXICO",
                        key="tcfe_estado_txt",
                        help="O pulse «Cargar estados CFE».",
                    )
            if estado and st.button("Cargar municipios", key="tcfe_btn_mpo"):
                with st.spinner("Municipios…"):
                    try:
                        _, _, explorar_opciones_geo = _cfe_client()
                        data = explorar_opciones_geo(
                            defn.url, anio=int(anio), mes=int(mes), estado=estado
                        )
                        st.session_state[geo_cache_key] = {
                            **geo,
                            "municipios": data.get("municipios") or [],
                            "estado_sel": estado,
                        }
                    except Exception as exc:
                        st.error(f"No se pudieron cargar municipios: {exc}")

            geo = st.session_state.get(geo_cache_key) or {}
            municipios = geo.get("municipios") or []
            with g2:
                if municipios and geo.get("estado_sel") == estado:
                    municipio = st.selectbox("Municipio", municipios, key="tcfe_mpo")
                else:
                    municipio = st.text_input(
                        "Municipio", value="MIGUEL HIDALGO", key="tcfe_mpo_txt"
                    )
            if estado and municipio and st.button(
                "Cargar divisiones", key="tcfe_btn_div"
            ):
                with st.spinner("Divisiones…"):
                    try:
                        _, _, explorar_opciones_geo = _cfe_client()
                        data = explorar_opciones_geo(
                            defn.url,
                            anio=int(anio),
                            mes=int(mes),
                            estado=estado,
                            municipio=municipio,
                        )
                        st.session_state[geo_cache_key] = {
                            **geo,
                            "divisiones": data.get("divisiones") or [],
                            "estado_sel": estado,
                            "mpo_sel": municipio,
                        }
                    except Exception as exc:
                        st.error(f"No se pudieron cargar divisiones: {exc}")

            geo = st.session_state.get(geo_cache_key) or {}
            divisiones = geo.get("divisiones") or []
            with g3:
                if (
                    divisiones
                    and geo.get("estado_sel") == estado
                    and geo.get("mpo_sel") == municipio
                ):
                    division = st.selectbox("División", divisiones, key="tcfe_div")
                else:
                    division = st.text_input(
                        "División",
                        value="VALLE DE MÉXICO NORTE",
                        key="tcfe_div_txt",
                    )
            region_tabla = (
                st.text_input(
                    "Etiqueta de tabla (opcional)",
                    value="",
                    key="tcfe_region_tabla",
                    help=(
                        "Si CFE muestra varias regiones (p. ej. Norte y Centro), "
                        "indique cuál leer."
                    ),
                ).strip()
                or None
            )

        consultar = st.button(
            "Consultar en CFE",
            type="primary",
            use_container_width=True,
            key="tcfe_consultar",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    if not consultar:
        _mostrar_resultado_sesion()
        return

    with st.spinner(f"Consultando {defn.codigo} en CFE…"):
        try:
            CfeTarifasError, consultar_tarifa_catalogo, _ = _cfe_client()
            resultado = consultar_tarifa_catalogo(
                defn.codigo,
                anio=int(anio),
                mes=int(mes),
                estado=estado,
                municipio=municipio,
                division=division,
                region_tabla=region_tabla,
                inicio_verano=inicio_verano,
            )
        except CfeTarifasError as exc:
            st.error(f"CFE: {exc}")
            return
        except Exception as exc:
            st.error(f"Error: {exc}")
            return

    st.session_state["tcfe_ultimo"] = {
        "codigo": resultado.codigo_tarifa or defn.codigo,
        "nombre": resultado.nombre_tarifa or defn.nombre,
        "anio": resultado.anio,
        "mes": resultado.mes,
        "estado": resultado.estado,
        "municipio": resultado.municipio,
        "division": resultado.division,
        "url": resultado.url,
        "cargos": resultado.cargos,
        "filas": resultado.filas_crudas,
        "tablas": [
            {
                "titulo": t.titulo,
                "columnas": list(t.columnas),
                "filas": list(t.filas),
            }
            for t in (resultado.tablas or [])
        ],
        "publicado": resultado.publicado(),
    }
    _mostrar_resultado_sesion()


def _mostrar_resultado_sesion() -> None:
    data = st.session_state.get("tcfe_ultimo")
    if not data:
        return

    st.markdown(
        '<div class="section-container">'
        '<div class="section-title">Resultado</div>'
        '<p class="section-desc">Cuotas obtenidas de la consulta a CFE.</p>',
        unsafe_allow_html=True,
    )
    mes_lbl = _MESES_LABEL.get(int(data["mes"]), str(data["mes"]))
    with st.container(border=True):
        st.markdown(
            f"**{data['codigo']}** — {data['nombre']} · "
            f"{mes_lbl} {data['anio']}"
        )
        ubic = " / ".join(
            p
            for p in (
                data.get("estado"),
                data.get("municipio"),
                data.get("division"),
            )
            if p
        )
        if ubic:
            st.caption(ubic)
        st.caption(data.get("url") or "")

        if not data.get("publicado"):
            st.warning(
                "La consulta no devolvió cargos con valor. "
                "Es posible que el mes aún no esté publicado en CFE."
            )

        tablas = data.get("tablas") or []
        if tablas:
            for tabla in tablas:
                st.markdown(f"##### {tabla.get('titulo') or 'Cuotas'}")
                filas_t = tabla.get("filas") or []
                columnas = tabla.get("columnas") or (
                    list(filas_t[0].keys()) if filas_t else []
                )
                df_t = pd.DataFrame(filas_t)
                if columnas:
                    df_t = df_t.reindex(
                        columns=[c for c in columnas if c in df_t.columns]
                    )
                st.dataframe(df_t, use_container_width=True, hide_index=True)
        else:
            cargos = data.get("cargos") or {}
            if cargos:
                df = pd.DataFrame(
                    [{"Concepto": k, "Valor": v} for k, v in cargos.items()]
                )
                st.dataframe(df, use_container_width=True, hide_index=True)

        filas = data.get("filas") or []
        if filas:
            with st.expander("Tabla cruda CFE", expanded=False):
                max_cols = max(len(r) for r in filas)
                normalizadas = [r + [""] * (max_cols - len(r)) for r in filas]
                st.dataframe(
                    pd.DataFrame(normalizadas),
                    use_container_width=True,
                    hide_index=True,
                )
    st.markdown("</div>", unsafe_allow_html=True)
