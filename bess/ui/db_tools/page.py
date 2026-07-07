"""Página Streamlit: Herramientas Base de Datos (admin, app aislada)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from bess.config.paths import RUTA_BD_PERFILES
from bess.ui.components import section_header, subnav_en_panel
from bess.ui.db_tools import service
from bess.ui.styles import aplicar_estilos


def _requiere_superadmin():
    from bess.config.users import rol_es_superadmin

    if not rol_es_superadmin(st.session_state.get("rol")):
        st.error("Solo superadministradores pueden usar Mantenimiento DB.")
        st.stop()


def _cabecera():
    ruta = service.ruta_bd()
    existe = ruta.is_file()
    tamanio = f"{ruta.stat().st_size / (1024 * 1024):.2f} MB" if existe else "—"
    estado_color = "#27ae60" if existe else "#e74c3c"
    estado_texto = "Disponible" if existe else "No existe"

    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#1a5276 0%,#2e86c1 100%);
                    border-radius:12px;padding:20px 24px;margin-bottom:16px;color:#fff;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                <span style="font-size:1.8rem;">🗄️</span>
                <div>
                    <h2 style="margin:0;font-size:1.4rem;font-weight:700;color:#fff;">
                        Mantenimiento Base de Datos
                    </h2>
                    <p style="margin:2px 0 0;font-size:0.85rem;opacity:0.85;">
                        Gestión de <code style="background:rgba(255,255,255,0.15);padding:1px 5px;
                        border-radius:3px;font-size:1.1rem;color:#000;font-weight:700;">{ruta.name}</code>
                        — perfiles minuto a minuto
                    </p>
                </div>
            </div>
            <div style="display:flex;gap:24px;flex-wrap:wrap;">
                <div style="background:rgba(255,255,255,0.1);border-radius:8px;padding:8px 16px;">
                    <span style="font-size:0.7rem;text-transform:uppercase;opacity:0.7;">Estado</span>
                    <p style="margin:2px 0 0;font-weight:600;font-size:0.95rem;">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                                     background:{estado_color};margin-right:6px;"></span>
                        {estado_texto}
                    </p>
                </div>
                <div style="background:rgba(255,255,255,0.1);border-radius:8px;padding:8px 16px;">
                    <span style="font-size:0.7rem;text-transform:uppercase;opacity:0.7;">Tamaño</span>
                    <p style="margin:2px 0 0;font-weight:600;font-size:0.95rem;">{tamanio}</p>
                </div>
                <div style="background:rgba(255,255,255,0.1);border-radius:8px;padding:8px 16px;">
                    <span style="font-size:0.7rem;text-transform:uppercase;opacity:0.7;">Archivo</span>
                    <p style="margin:2px 0 0;font-weight:600;font-size:0.95rem;">{ruta.name}</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _estado_vacio_bd():
    with st.container(border=True):
        section_header(
            "Base de datos no encontrada",
            f"No existe `{RUTA_BD_PERFILES.name}`. Inicialice el esquema en la pestaña Avanzado.",
        )
        st.info("Vaya a **Avanzado → Inicializar esquema y catálogo** para crear la base de datos.")


def _tab_resumen():
    if not RUTA_BD_PERFILES.is_file():
        _estado_vacio_bd()
        return

    with st.container(border=True):
        section_header(
            "Medidores registrados",
            "Conteo de registros, rango de fechas y estado de la última sincronización.",
        )
        filas = service.resumen_medidores()
        if not filas:
            st.info("Catálogo de medidores vacío. Inicialice la BD en Avanzado.")
            return

        df = pd.DataFrame(
            [
                {
                    "Medidor": r.medidor_id,
                    "Registros": f"{r.registros:,}",
                    "Desde": r.fecha_min or "—",
                    "Hasta": r.fecha_max or "—",
                    "Última sync": r.ultima_sync or "—",
                    "Sync OK": r.ultima_sync_ok or "—",
                }
                for r in filas
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    with st.container(border=True):
        section_header("Últimas sincronizaciones", "Entradas recientes del log de sync API/Modbus.")
        logs = service.ultimos_sync_log()
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
        else:
            st.caption("Sin entradas en sync_log.")


def _tab_importar():
    medidores = service.lista_medidores_catalogo()

    with st.container(border=True):
        section_header(
            "Importar CSV a SQLite",
            "Suba un archivo con columnas Fecha, KWH_REC, KWH_ENT, KVARH_Q1…Q4.",
        )

        medidor = st.selectbox("Medidor destino", medidores, key="imp_medidor")

        c1, c2 = st.columns(2)
        solo_faltantes = c1.checkbox(
            "Solo timestamps faltantes",
            value=False,
            key="imp_solo_faltantes",
            help="No actualiza registros existentes, solo inserta nuevos.",
        )
        sin_filtro_dia = c2.checkbox(
            "Sin filtro 00:05 del primer registro",
            value=False,
            key="imp_sin_filtro_dia",
            help="Desactiva el filtro que descarta el registro de las 00:05.",
        )

        archivo = st.file_uploader("Archivo CSV", type=["csv"], key="imp_archivo")
        if st.button("⬆️ Importar a SQLite", type="primary", disabled=archivo is None, key="imp_btn"):
            with st.spinner("Importando..."):
                codigo, log = service.importar_desde_bytes(
                    archivo.getvalue(),
                    archivo.name,
                    medidor,
                    solo_faltantes=solo_faltantes,
                    sin_filtro_dia=sin_filtro_dia,
                )
            if codigo == 0:
                st.success("✅ Importación completada.")
            else:
                st.error("❌ La importación terminó con errores.")
            with st.expander("Ver log completo", expanded=codigo != 0):
                st.code(log)


def _tab_exportar():
    from bess.data.ingest.medidor_ids import destinos_export_bd

    with st.container(border=True):
        section_header("Exportar desde SQLite", "Descargue un medidor o exporte todos a ArchivosFuente.")

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

        if st.button("⬇️ Descargar CSV", type="primary", key="exp_btn_descarga"):
            with st.spinner("Exportando..."):
                ok, data, log = service.exportar_medidor_a_bytes(medidor, desde=desde_d, hasta=hasta_d)
            if ok and data:
                st.download_button(
                    "💾 Guardar archivo",
                    data=data,
                    file_name=f"{medidor}_export.csv",
                    mime="text/csv",
                    key="exp_btn_guardar",
                )
                if log.strip():
                    with st.expander("Ver log"):
                        st.code(log)
            else:
                st.warning(log or "Sin datos para el rango seleccionado.")

    with st.container(border=True):
        section_header(
            "Exportación masiva",
            "Exporta todos los medidores a `ArchivosFuente/` (misma lógica que `export_perfiles.py`).",
        )
        if st.button("Exportar todos a ArchivosFuente", key="exp_btn_todos"):
            with st.spinner("Exportando todos los medidores..."):
                codigo, log = service.exportar_todos_a_fuente()
            if codigo == 0:
                st.success("✅ Exportación masiva completada.")
            else:
                st.warning("⚠️ Algunos medidores no tenían registros.")
            with st.expander("Ver log completo"):
                st.code(log)


def _tab_purgar():
    with st.container(border=True):
        section_header(
            "Purgar registros",
            "Elimine datos por medidor y rango de fechas. Use vista previa antes de confirmar.",
        )

        medidores = service.lista_medidores_catalogo()
        seleccion = st.multiselect(
            "Medidores a purgar",
            medidores,
            default=medidores[:1] if medidores else [],
            key="pur_medidores",
        )

        modo = st.radio(
            "Modo de borrado",
            ["Rango de fechas (desde / hasta)", "Desde una fecha hasta el final (sync incremental)"],
            horizontal=True,
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

        col_prev, col_exec = st.columns(2)

        with col_prev:
            if st.button("👁️ Vista previa", type="secondary", key="pur_btn_preview", use_container_width=True):
                if not seleccion:
                    st.warning("Seleccione al menos un medidor.")
                else:
                    for med in seleccion:
                        if modo.startswith("Rango"):
                            info = service.preview_borrar_rango(med, fecha_desde, fecha_hasta)
                        else:
                            corte = f"{fecha_desde.isoformat()} 00:00:00"
                            info = service.purgar_desde_fecha(med, corte, ejecutar=False)
                        st.json(info)

        with col_exec:
            ejecutar = st.checkbox(
                "Confirmo el borrado",
                key="pur_confirmar",
            )
            if st.button(
                "🗑️ Ejecutar borrado",
                type="primary",
                disabled=not ejecutar,
                key="pur_btn_ejecutar",
                use_container_width=True,
            ):
                if not seleccion:
                    st.warning("Seleccione al menos un medidor.")
                else:
                    for med in seleccion:
                        if modo.startswith("Rango"):
                            info = service.ejecutar_borrar_rango(med, fecha_desde, fecha_hasta)
                        else:
                            corte = f"{fecha_desde.isoformat()} 00:00:00"
                            info = service.purgar_desde_fecha(med, corte, ejecutar=True)
                        st.success(f"**{med}**: eliminados {info.get('eliminar', 0):,} registros.")
                        if info.get("registros_restantes") is not None:
                            st.caption(f"Registros restantes: {info['registros_restantes']:,}")


def _tab_avanzado():
    with st.container(border=True):
        section_header(
            "Operaciones avanzadas",
            "Operaciones destructivas o de una sola vez. Use con precaución.",
        )

        with st.expander("🏗️ Inicializar esquema y catálogo", expanded=False):
            st.markdown("Crea tablas si no existen y sincroniza medidores desde el catálogo en BD.")
            if st.button("Inicializar BD", key="adv_btn_init", type="primary"):
                with st.spinner("Inicializando..."):
                    service.inicializar_bd()
                st.success("✅ BD inicializada correctamente.")

        with st.expander("🔄 Migrar IDs legacy → nombres del catálogo", expanded=False):
            st.markdown("Renombra IDs antiguos en la tabla de perfiles según el catálogo actual.")
            dry = st.checkbox("Solo vista previa (dry-run)", value=True, key="migrar_dry")
            if st.button("Ejecutar migración", key="adv_btn_migrar", type="primary"):
                with st.spinner("Migrando..."):
                    codigo, log = service.migrar_ids_legacy(dry_run=dry)
                if codigo == 0:
                    st.success("✅ " + ("Vista previa lista." if dry else "Migración completada."))
                else:
                    st.error("❌ La migración reportó errores.")
                with st.expander("Ver log", expanded=codigo != 0):
                    st.code(log)

        with st.expander("⚠️ Vaciar todos los perfiles", expanded=False):
            st.markdown(
                "Borra **todos** los registros de `perfil_carga` y `sync_state`. "
                "Conserva el catálogo de medidores."
            )
            confirm = st.text_input(
                "Escriba **VACIAR** para confirmar:",
                key="vaciar_confirm",
                placeholder="VACIAR",
            )
            if st.button(
                "🗑️ Vaciar perfiles",
                type="primary",
                disabled=confirm != "VACIAR",
                key="adv_btn_vaciar",
            ):
                with st.spinner("Vaciando..."):
                    n = service.vaciar_perfiles_bd()
                st.success(f"✅ Eliminados {n:,} registros de perfil_carga.")


def main():
    _requiere_superadmin()
    aplicar_estilos()
    _cabecera()

    vista = subnav_en_panel(
        "Herramientas de base de datos",
        [
            ("resumen", "📋 Resumen"),
            ("importar", "📥 Importar"),
            ("exportar", "📤 Exportar"),
            ("purgar", "🗑️ Purgar"),
            ("avanzado", "⚙️ Avanzado"),
        ],
        "db_tools_vista",
    )

    if vista == "resumen":
        _tab_resumen()
    elif vista == "importar":
        _tab_importar()
    elif vista == "exportar":
        _tab_exportar()
    elif vista == "purgar":
        _tab_purgar()
    elif vista == "avanzado":
        _tab_avanzado()
