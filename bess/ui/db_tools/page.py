"""Página Streamlit: Herramientas Base de Datos (admin, app aislada)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from bess.config.paths import RUTA_BD_PERFILES
from bess.ui.db_tools import service
from bess.ui.styles import aplicar_estilos


def _requiere_superadmin():
    from bess.config.users import rol_es_superadmin

    if not rol_es_superadmin(st.session_state.get("rol")):
        st.error("Solo superadministradores pueden usar Mantenimiento DB.")
        st.stop()


def _cabecera():
    st.markdown(
        """
        <div class="section-container">
            <p class="section-title">Herramientas Base de Datos</p>
            <p class="section-desc">
                Mantenimiento de <code>bess_perfiles.db</code> (perfiles minuto a minuto).
                Importar, exportar, purgar y migrar sin ejecutar verificar, filtrar ni reportes.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    ruta = service.ruta_bd()
    existe = ruta.is_file()
    c1, c2, c3 = st.columns(3)
    c1.metric("Base de datos", ruta.name)
    c2.metric("Estado", "Disponible" if existe else "No existe")
    if existe:
        c3.metric("Tamaño", f"{ruta.stat().st_size / (1024 * 1024):.2f} MB")
    else:
        c3.metric("Tamaño", "—")


def _tab_resumen():
    st.markdown('<p class="section-title-sm">Resumen por medidor</p>', unsafe_allow_html=True)
    if not RUTA_BD_PERFILES.is_file():
        st.warning(f"No existe {RUTA_BD_PERFILES.name}. Use **Avanzado → Inicializar BD**.")
        return

    filas = service.resumen_medidores()
    if not filas:
        st.info("Catálogo de medidores vacío. Inicialice la BD.")
        return

    df = pd.DataFrame(
        [
            {
                "Medidor": r.medidor_id,
                "Registros": r.registros,
                "Desde": r.fecha_min or "—",
                "Hasta": r.fecha_max or "—",
                "Última sync": r.ultima_sync or "—",
                "Sync OK": r.ultima_sync_ok or "—",
            }
            for r in filas
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown('<p class="section-title-sm">Últimas sincronizaciones (sync_log)</p>', unsafe_allow_html=True)
    logs = service.ultimos_sync_log()
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
    else:
        st.caption("Sin entradas en sync_log.")


def _tab_importar():
    from bess.data.ingest.ion.import_csv import MEDIDORES_IMPORTABLES

    st.markdown(
        '<p class="section-desc">Suba un CSV con columnas Fecha, KWH_REC, KWH_ENT, KVARH_Q1…Q4.</p>',
        unsafe_allow_html=True,
    )
    medidor = st.selectbox("Medidor destino", list(MEDIDORES_IMPORTABLES), key="imp_medidor")

    c1, c2 = st.columns(2)
    solo_faltantes = c1.checkbox(
        "Solo timestamps faltantes (no actualizar existentes)",
        value=False,
        key="imp_solo_faltantes",
    )
    sin_filtro_dia = c2.checkbox(
        "Sin filtro 00:05 del primer registro del día",
        value=False,
        key="imp_sin_filtro_dia",
    )

    archivo = st.file_uploader("Archivo CSV", type=["csv"], key="imp_archivo")
    if st.button("Importar a SQLite", type="primary", disabled=archivo is None, key="imp_btn"):
        codigo, log = service.importar_desde_bytes(
            archivo.getvalue(),
            archivo.name,
            medidor,
            solo_faltantes=solo_faltantes,
            sin_filtro_dia=sin_filtro_dia,
        )
        if codigo == 0:
            st.success("Importación completada.")
        else:
            st.error("La importación terminó con errores.")
        st.code(log)


def _tab_exportar():
    from bess.data.ingest.medidor_ids import destinos_export_bd

    medidores = [m for m, _ in destinos_export_bd(RUTA_BD_PERFILES)]
    medidor = st.selectbox("Medidor", medidores, key="exp_medidor")
    hoy = date.today()
    c1, c2 = st.columns(2)
    usar_desde = c1.checkbox("Filtrar desde", value=False, key="exp_desde_on")
    usar_hasta = c2.checkbox("Filtrar hasta", value=False, key="exp_hasta_on")
    desde = c1.date_input(
        "Desde",
        value=hoy - timedelta(days=30),
        max_value=hoy,
        disabled=not usar_desde,
        key="exp_desde",
    )
    hasta = c2.date_input(
        "Hasta",
        value=hoy,
        max_value=hoy,
        disabled=not usar_hasta,
        key="exp_hasta",
    )

    desde_d = desde if usar_desde else None
    hasta_d = hasta if usar_hasta else None

    if st.button("Descargar CSV desde BD", type="primary", key="exp_btn_descarga"):
        ok, data, log = service.exportar_medidor_a_bytes(medidor, desde=desde_d, hasta=hasta_d)
        if ok and data:
            st.download_button(
                "Guardar archivo",
                data=data,
                file_name=f"{medidor}_export.csv",
                mime="text/csv",
                key="exp_btn_guardar",
            )
            if log.strip():
                st.code(log)
        else:
            st.warning(log or "Sin datos.")

    st.divider()
    st.markdown("**Exportar todos los medidores** a `ArchivosFuente/` (misma lógica que `export_perfiles.py`).")
    if st.button("Exportar todos a ArchivosFuente", key="exp_btn_todos"):
        codigo, log = service.exportar_todos_a_fuente()
        if codigo == 0:
            st.success("Exportación masiva completada.")
        else:
            st.warning("Algunos medidores no tenían registros.")
        st.code(log)


def _tab_purgar():
    medidores = service.lista_medidores_catalogo()
    seleccion = st.multiselect(
        "Medidores",
        medidores,
        default=medidores[:1] if medidores else [],
        key="pur_medidores",
    )

    modo = st.radio(
        "Modo de borrado",
        ["Rango de fechas (desde / hasta)", "Desde una fecha hasta el final (sync incremental)"],
        horizontal=False,
        key="pur_modo",
    )

    hoy = datetime.now().date()
    c1, c2 = st.columns(2)
    fecha_desde = c1.date_input(
        "Desde",
        value=hoy - timedelta(days=7),
        max_value=hoy,
        key="pur_desde",
    )
    fecha_hasta = c2.date_input(
        "Hasta",
        value=hoy,
        max_value=hoy,
        disabled=modo.startswith("Desde"),
        key="pur_hasta",
    )

    ejecutar = st.checkbox(
        "Confirmo que deseo borrar los registros mostrados en la vista previa",
        key="pur_confirmar",
    )

    if st.button("Vista previa", type="secondary", key="pur_btn_preview"):
        if not seleccion:
            st.warning("Seleccione al menos un medidor.")
            return
        for med in seleccion:
            if modo.startswith("Rango"):
                info = service.preview_borrar_rango(med, fecha_desde, fecha_hasta)
            else:
                corte = f"{fecha_desde.isoformat()} 00:00:00"
                info = service.purgar_desde_fecha(med, corte, ejecutar=False)
            st.json(info)

    if st.button("Ejecutar borrado", type="primary", disabled=not ejecutar, key="pur_btn_ejecutar"):
        if not seleccion:
            st.warning("Seleccione al menos un medidor.")
            return
        for med in seleccion:
            if modo.startswith("Rango"):
                info = service.ejecutar_borrar_rango(med, fecha_desde, fecha_hasta)
            else:
                corte = f"{fecha_desde.isoformat()} 00:00:00"
                info = service.purgar_desde_fecha(med, corte, ejecutar=True)
            st.success(f"{med}: eliminados {info.get('eliminar', 0)} registros.")
            if info.get("registros_restantes") is not None:
                st.caption(f"Registros restantes en BD: {info['registros_restantes']}")


def _tab_avanzado():
    st.warning("Operaciones destructivas o de una sola vez. Use vista previa cuando exista.")

    with st.expander("Inicializar esquema y catálogo de medidores", expanded=False):
        st.caption("Crea tablas si no existen y actualiza el catálogo desde Medidores.csv.")
        if st.button("Inicializar BD", key="adv_btn_init"):
            service.inicializar_bd()
            st.success("BD inicializada.")

    with st.expander("Migrar IDs legacy → nombres del catálogo", expanded=False):
        dry = st.checkbox("Solo vista previa (dry-run)", value=True, key="migrar_dry")
        if st.button("Ejecutar migración de IDs", key="adv_btn_migrar"):
            codigo, log = service.migrar_ids_legacy(dry_run=dry)
            if codigo == 0:
                st.success("Migración completada." if not dry else "Vista previa lista.")
            else:
                st.error("La migración reportó errores.")
            st.code(log)

    with st.expander("Vaciar todos los perfiles", expanded=False):
        st.caption("Borra perfil_carga y sync_state. Conserva el catálogo de medidores.")
        confirm = st.text_input('Escriba VACIAR para confirmar', key="vaciar_confirm")
        if st.button("Vaciar perfiles", type="primary", disabled=confirm != "VACIAR", key="adv_btn_vaciar"):
            n = service.vaciar_perfiles_bd()
            st.success(f"Eliminados {n:,} registros de perfil_carga.")


def main():
    _requiere_superadmin()
    aplicar_estilos()
    _cabecera()

    tab_resumen, tab_import, tab_export, tab_purge, tab_adv = st.tabs(
        ["Resumen", "Importar CSV", "Exportar", "Purgar rango", "Avanzado"]
    )
    with tab_resumen:
        _tab_resumen()
    with tab_import:
        _tab_importar()
    with tab_export:
        _tab_exportar()
    with tab_purge:
        _tab_purgar()
    with tab_adv:
        _tab_avanzado()
