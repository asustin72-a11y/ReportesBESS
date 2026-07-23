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
        section_header("Últimas sincronizaciones", "Entradas recientes del log de sync (ION, API y Granja).")
        logs = service.ultimos_sync_log()
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
        else:
            st.caption("Sin entradas en sync_log.")

    with st.container(border=True):
        section_header(
            "Cursores sync_state ↔ Ultima_Sincronizacion",
            "Si el CSV de petición está atrás de sync_state, el próximo sync API "
            "puede forzar redescarga y solapar el día completo.",
        )
        if st.button("🔍 Evaluar cursores", key="cur_btn_eval"):
            st.session_state["cur_divergencias"] = service.divergencias_cursores_sync()

        divergencias = st.session_state.get("cur_divergencias")
        if divergencias is None:
            st.caption("Pulse Evaluar para comparar.")
        elif not divergencias:
            st.success("✅ Cursores alineados (o sin datos).")
        else:
            st.warning(f"⚠️ {len(divergencias)} medidor(es) con cursores divergentes.")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Medidor": d["medidor_id"],
                            "sync_state": d["sync_state"] or "—",
                            "Ultima_Sincronizacion": d["ultima_sincronizacion_csv"] or "—",
                            "MAX perfil_carga": d["max_perfil_carga"] or "—",
                            "Motivo": d["motivo"],
                        }
                        for d in divergencias
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
            ids = [d["medidor_id"] for d in divergencias]
            confirmar = st.checkbox(
                "Confirmo alinear Ultima_Sincronizacion a MAX(fecha) en BD",
                key="cur_confirmar",
            )
            if st.button(
                "🔗 Alinear a BD",
                type="primary",
                disabled=not confirmar,
                key="cur_btn_alinear",
            ):
                hechos = service.alinear_cursores_a_bd(ids)
                st.success(f"✅ Alineados {len(hechos)} medidor(es).")
                st.session_state["cur_divergencias"] = service.divergencias_cursores_sync()
                st.rerun()


def _tab_importar():
    medidores = service.lista_medidores_catalogo()

    with st.container(border=True):
        section_header(
            "Importar CSV a SQLite",
            "Suba un archivo con columnas Fecha, KWH_REC, KWH_ENT, KVARH_Q1…Q4.",
        )
        st.info(
            "Tras importar: se alinea el cursor de sync (`Ultima_Sincronizacion`) "
            "y las filas quedan con `fuente=csv`. El sync API trae días completos, "
            "pero **no pisa** filas `csv` con energía real (`respetar_fuente=csv` + "
            "`no_degradar_a_ceros`). Filas `csv` en cero sí pueden corregirse por la API."
        )

        medidor = st.selectbox("Medidor destino", medidores, key="imp_medidor")

        solo_faltantes = st.checkbox(
            "Solo timestamps faltantes",
            value=False,
            key="imp_solo_faltantes",
            help="No actualiza registros existentes, solo inserta nuevos.",
        )

        rebuild_despues = st.checkbox(
            "Después del import: Rebuild CSV (reexportar + verificar/filtrar/reportes)",
            value=False,
            key="imp_rebuild",
            help="Útil si la gráfica lee COMBINADO y no solo SQLite.",
        )
        hoy = date.today()
        rebuild_desde = st.date_input(
            "Rebuild desde",
            value=hoy - timedelta(days=45),
            max_value=hoy,
            disabled=not rebuild_despues,
            key="imp_rebuild_desde",
        )

        archivo = st.file_uploader("Archivo CSV", type=["csv"], key="imp_archivo")
        if st.button("⬆️ Importar a SQLite", type="primary", disabled=archivo is None, key="imp_btn"):
            with st.spinner("Importando..."):
                codigo, log = service.importar_desde_bytes(
                    archivo.getvalue(),
                    archivo.name,
                    medidor,
                    solo_faltantes=solo_faltantes,
                )
            if codigo == 0:
                st.success(
                    "✅ Importación completada. Cursor de sync alineado; "
                    "filas con energía quedan protegidas frente al sync API."
                )
                if rebuild_despues:
                    with st.spinner("Rebuild CSV en curso…"):
                        rb = _ejecutar_rebuild_csv_ui(
                            medidor, rebuild_desde, procesar=True
                        )
                    if rb.get("ok"):
                        st.success(
                            f"✅ Rebuild OK desde {rb.get('desde')} "
                            f"({len(rb.get('borrados') or [])} CSV regenerados)."
                        )
                    else:
                        st.error("❌ Import OK, pero el Rebuild falló.")
                    with st.expander("Log Rebuild", expanded=not rb.get("ok")):
                        st.code(rb.get("log") or "(sin log)")
            else:
                st.error("❌ La importación terminó con errores.")
            with st.expander("Ver log importación", expanded=codigo != 0):
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


def _tab_reconciliar():
    from bess.data.ingest.medidor_ids import destinos_export_bd

    with st.container(border=True):
        section_header(
            "Reconciliar SQLite ↔ Fuente",
            "Compara SUM(kWh) y filas por día entre perfil_carga y ArchivosFuente. "
            "Detecta cursores CSV congelados (BD bien, Fuente desfasada).",
        )
        st.caption(
            "No escribe nada. Si hay divergencias, use **Rebuild CSV** para "
            "reexportar desde la BD y regenerar la cadena."
        )

        hoy = date.today()
        c1, c2, c3 = st.columns(3)
        dias = c1.number_input(
            "Ventana (días)",
            min_value=7,
            max_value=120,
            value=45,
            step=1,
            key="rec_dias",
        )
        hasta = c2.date_input("Hasta", value=hoy, max_value=hoy, key="rec_hasta")
        medidores = [m for m, _ in destinos_export_bd(RUTA_BD_PERFILES)]
        solo = c3.multiselect(
            "Solo medidores (vacío = todos)",
            medidores,
            default=[],
            key="rec_medidores",
        )

        if st.button("🔍 Evaluar divergencias", type="primary", key="rec_btn"):
            with st.spinner("Comparando BD vs Fuente…"):
                resultado = service.reconciliar_sqlite_vs_fuente(
                    hasta=hasta,
                    dias=int(dias),
                    solo_medidores=solo or None,
                )
            st.session_state["rec_ultimo_resultado"] = resultado

        resultado = st.session_state.get("rec_ultimo_resultado")
        if not resultado:
            return

        total = resultado.get("total_divergencias", 0)
        n_med = resultado.get("medidores_afectados", 0)
        if total == 0:
            st.success("✅ Sin divergencias en la ventana evaluada.")
            return

        st.warning(
            f"⚠️ **{total} día(s)** divergente(s) en **{n_med} medidor(es)**. "
            "La BD y ArchivosFuente no coinciden — típico de export incremental "
            "congelado. Remedio: Rebuild CSV del medidor desde la fecha afectada."
        )

        resumen = resultado.get("resumen") or []
        if resumen:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Medidor": r["medidor_id"],
                            "Días": r["dias_divergentes"],
                            "Desde": r["primer_dia"],
                            "Hasta": r["ultimo_dia"],
                            "Δ REC": r["delta_rec_total"],
                            "Δ ENT": r["delta_ent_total"],
                            "Motivo": r["motivos"],
                        }
                        for r in resumen
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

        detalle = resultado.get("detalle") or []
        if detalle:
            with st.expander(f"Detalle día a día ({len(detalle)})", expanded=False):
                st.dataframe(pd.DataFrame(detalle), use_container_width=True, hide_index=True)

        st.markdown("#### Ir a Rebuild CSV")
        opciones = [r["medidor_id"] for r in resumen]
        if opciones:
            elegido = st.selectbox(
                "Medidor a reparar",
                opciones,
                key="rec_rebuild_medidor",
            )
            fila = next(r for r in resumen if r["medidor_id"] == elegido)
            if st.button(
                f"🔄 Abrir Rebuild para `{elegido}`",
                key="rec_goto_rebuild",
                type="primary",
            ):
                st.session_state["db_tools_vista"] = "rebuild"
                st.session_state["rb_medidor"] = elegido
                try:
                    st.session_state["rb_desde"] = date.fromisoformat(fila["primer_dia"])
                except ValueError:
                    pass
                st.rerun()


def _plan_rebuild_csv_ui(medidor_id: str, desde: date) -> dict:
    """Vista previa: importa el módulo fresco (evita AttributeError por caché Streamlit)."""
    import importlib

    from bess.data import csv_rebuild
    from bess.ui.db_tools import service as service_mod

    importlib.reload(csv_rebuild)
    importlib.reload(service_mod)
    if hasattr(service_mod, "plan_rebuild_csv"):
        return service_mod.plan_rebuild_csv(medidor_id, desde)
    plan = csv_rebuild.plan_rebuild_csv(medidor_id, desde)
    return {
        "medidor": plan.medidor_id,
        "subestacion": plan.subestacion_id,
        "tipo_medidor": plan.tipo_medidor,
        "desde": plan.desde,
        "ruta_fuente": str(plan.ruta_fuente),
        "archivos_a_borrar_existentes": plan.resumen_borrado(),
        "archivos_candidato": [str(p) for p in plan.archivos_a_borrar],
        "avisos": plan.avisos,
    }


def _ejecutar_rebuild_csv_ui(medidor_id: str, desde: date, *, procesar: bool = True) -> dict:
    import importlib

    from bess.data import csv_rebuild
    from bess.ui.db_tools import service as service_mod

    importlib.reload(csv_rebuild)
    importlib.reload(service_mod)
    if hasattr(service_mod, "ejecutar_rebuild_csv"):
        return service_mod.ejecutar_rebuild_csv(medidor_id, desde, procesar=procesar)
    return csv_rebuild.ejecutar_rebuild_csv(medidor_id, desde, procesar=procesar)


def _tab_rebuild_csv():
    from bess.data.ingest.medidor_ids import destinos_export_bd

    with st.container(border=True):
        section_header(
            "Rebuild forzado de CSV",
            "Reexporta desde SQLite y borra CSV derivados para saltar la ventana "
            "incremental de 1 día. No modifica la base de datos (solo lectura).",
        )
        st.info(
            "Úselo cuando SQLite tiene datos correctos pero Fuente/Filtrado/COMBINADO "
            "tienen ceros o huecos congelados (p. ej. BESS Aragón 8–12 jul)."
        )

        medidores = [m for m, _ in destinos_export_bd(RUTA_BD_PERFILES)]
        if not medidores:
            st.warning("No hay medidores exportables en el catálogo.")
            return
        if st.session_state.get("rb_medidor") not in medidores:
            st.session_state["rb_medidor"] = medidores[0]
        medidor = st.selectbox("Medidor", medidores, key="rb_medidor")

        hoy = date.today()
        if "rb_desde" not in st.session_state:
            st.session_state["rb_desde"] = (
                date(hoy.year, 5, 1) if hoy.month >= 5 else date(hoy.year - 1, 5, 1)
            )
        desde = st.date_input(
            "Reexportar desde",
            max_value=hoy,
            key="rb_desde",
            help="La Fuente del medidor se reescribe completa desde esta fecha.",
        )
        procesar = st.checkbox(
            "Después del export: Verificar → Filtrar → Reportes",
            value=True,
            key="rb_procesar",
        )

        col_prev, col_exec = st.columns(2)
        with col_prev:
            if st.button(
                "👁️ Vista previa",
                type="secondary",
                key="rb_btn_preview",
                use_container_width=True,
            ):
                plan = _plan_rebuild_csv_ui(medidor, desde)
                st.json(plan)
                for aviso in plan.get("avisos", []):
                    st.caption(f"• {aviso}")

        with col_exec:
            confirmar = st.checkbox(
                "Confirmo rebuild CSV (no toca SQLite)",
                key="rb_confirmar",
            )
            if st.button(
                "🔄 Ejecutar rebuild",
                type="primary",
                disabled=not confirmar,
                key="rb_btn_ejecutar",
                use_container_width=True,
            ):
                with st.spinner(
                    "Reexportando y regenerando CSV… esto puede tardar varios minutos."
                ):
                    resultado = _ejecutar_rebuild_csv_ui(
                        medidor, desde, procesar=procesar
                    )
                if resultado.get("ok"):
                    st.success(
                        f"✅ Rebuild OK: `{resultado['medidor']}` desde {resultado['desde']}."
                    )
                else:
                    st.error("❌ Rebuild incompleto o con errores.")
                st.caption(
                    f"Export rc={resultado.get('export_rc')} · "
                    f"CSV borrados={len(resultado.get('borrados') or [])}"
                )
                with st.expander("Ver log completo", expanded=not resultado.get("ok")):
                    st.code(resultado.get("log") or "(sin log)")


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


def _tab_pcarga():
    medidores_fb = service.lista_medidores_fallback_iusa12()
    with st.container(border=True):
        section_header(
            "Fallback API → pcarga (IUSA 1/2)",
            "Cuando api.iusasol.mx está caída: descarga Ethernet, importa a SQLite "
            "y reconstruye CSV. No incluye granja ni Aragón.",
        )
        st.info(
            "Cubiertos: **"
            + "**, **".join(medidores_fb)
            + "**. Granja Mega y Consumo Aragón siguen dependiendo de la API."
        )
        rebuild_fb = st.checkbox(
            "Rebuild CSV tras importar (recomendado)",
            value=True,
            key="pcarga_fb_rebuild",
        )
        procesar_fb = st.checkbox(
            "Tras Rebuild: Verificar → Filtrar → Reportes",
            value=False,
            key="pcarga_fb_procesar",
            help="Más lento; actívelo si necesita reportes al momento.",
        )
        if st.button(
            "⚡ Ejecutar fallback pcarga IUSA 1/2",
            type="primary",
            key="pcarga_fb_btn",
        ):
            with st.spinner(
                "Fallback en curso (Wine/MLE por medidor; puede tardar varios minutos)…"
            ):
                lote = service.ejecutar_fallback_pcarga_iusa12(
                    rebuild=rebuild_fb,
                    procesar=procesar_fb,
                )
            st.session_state["pcarga_fallback_lote"] = lote

        lote = st.session_state.get("pcarga_fallback_lote")
        if lote is not None:
            if lote.ok:
                st.success(
                    f"✅ Fallback OK: {lote.exitosos}/{len(lote.medidores)} medidores."
                )
            else:
                st.warning(
                    f"Fallback parcial: {lote.exitosos} OK, {lote.fallidos} con error."
                )
            st.code(lote.log or "(sin resumen)")
            with st.expander("Detalle por medidor", expanded=not lote.ok):
                for r in lote.medidores:
                    icon = "✅" if r.ok else "❌"
                    st.markdown(
                        f"{icon} **{r.medidor_id}** · {r.registros:,} reg · "
                        f"`{r.desde}` → `{r.hasta}`"
                        + (f" · falló en {r.etapa}" if not r.ok else "")
                    )
                    if r.log and not r.ok:
                        st.code(r.log[:3000])
            if not rebuild_fb:
                st.caption(
                    "Sin Rebuild: SQLite actualizado; use la pestaña Rebuild CSV "
                    "antes de confiar en el reporteador."
                )

    medidores = service.lista_medidores_pcarga()
    with st.container(border=True):
        section_header(
            "Descargar pcarga (Ethernet)",
            "Lee el perfil del medidor por red (Wine/MLE en Linux). "
            "Solo descarga CSV listo para Importar; no escribe en SQLite.",
        )
        st.info(
            "Flujo: descargar aquí → revisar el CSV → si hace falta, "
            "usar la pestaña **Importar**. "
            "Ke externo se aplica solo si MULT internos = 1; "
            "Cogeneración y BESS Aragón ya vienen escalados."
        )
        if not medidores:
            st.warning("No hay medidores con endpoint pcarga configurado.")
            return

        medidor = st.selectbox("Medidor", medidores, key="pcarga_medidor")
        st.caption(service.info_endpoint_pcarga(medidor))

        hoy = date.today()
        ahora = datetime.now().replace(second=0, microsecond=0)
        # Alinear a intervalo de 5 min del perfil
        minuto_alig = (ahora.minute // 5) * 5
        hora_fin_default = ahora.replace(minute=minuto_alig)
        hora_ini_default = (hora_fin_default - timedelta(hours=3)).time()

        c1, c2 = st.columns(2)
        fecha_desde = c1.date_input(
            "Desde (fecha)",
            value=hoy - timedelta(days=1),
            max_value=hoy,
            key="pcarga_fecha_desde",
        )
        hora_desde = c1.time_input(
            "Desde (hora)",
            value=hora_ini_default,
            step=300,
            key="pcarga_hora_desde",
            help="Intervalos de 5 minutos (el medidor alinea si no coincide).",
        )
        fecha_hasta = c2.date_input(
            "Hasta (fecha)",
            value=hoy,
            max_value=hoy,
            key="pcarga_fecha_hasta",
        )
        hora_hasta = c2.time_input(
            "Hasta (hora)",
            value=hora_fin_default.time(),
            step=300,
            key="pcarga_hora_hasta",
            help="Intervalos de 5 minutos.",
        )

        desde = datetime.combine(fecha_desde, hora_desde).replace(second=0, microsecond=0)
        hasta = datetime.combine(fecha_hasta, hora_hasta).replace(second=0, microsecond=0)
        st.caption(
            f"Rango efectivo: `{desde.strftime('%Y-%m-%d %H:%M')}` → "
            f"`{hasta.strftime('%Y-%m-%d %H:%M')}`"
        )
        if desde > hasta:
            st.error("Desde no puede ser posterior a Hasta.")
            return

        if st.button("⬇️ Descargar pcarga", type="primary", key="pcarga_btn"):
            with st.spinner(f"Leyendo {medidor} por red… (puede tardar varios minutos)"):
                res = service.descargar_pcarga_rango(medidor, desde, hasta)
            st.session_state["pcarga_resultado"] = res

        res = st.session_state.get("pcarga_resultado")
        if res is None:
            return

        if not res.ok:
            st.error("No se pudo descargar pcarga.")
            with st.expander("Ver log", expanded=True):
                st.code(res.log or "(sin log)")
            return

        ke_txt = (
            "ya escalado (×1)"
            if res.ya_escalado
            else f"Ke×{res.ke_aplicado:g}"
        )
        st.success(
            f"✅ {res.registros:,} registros · {ke_txt} · "
            f"serie {res.serie_leida or '—'} · "
            f"omitidos inválidos: {res.omitidos_invalidos}"
        )
        st.download_button(
            "💾 Guardar CSV (formato Importar)",
            data=res.csv_bytes,
            file_name=res.nombre_archivo,
            mime="text/csv",
            key="pcarga_dl",
        )
        with st.expander("Ver log descarga"):
            st.code(res.log or "(sin log)")


def main():
    _requiere_superadmin()
    aplicar_estilos()
    _cabecera()

    vista = subnav_en_panel(
        "Herramientas de base de datos",
        [
            ("resumen", "📋 Resumen"),
            ("pcarga", "📡 PCarga"),
            ("importar", "📥 Importar"),
            ("exportar", "📤 Exportar"),
            ("reconciliar", "🔬 Reconciliar"),
            ("rebuild", "🔄 Rebuild CSV"),
            ("purgar", "🗑️ Purgar"),
            ("avanzado", "⚙️ Avanzado"),
        ],
        "db_tools_vista",
    )

    if vista == "resumen":
        _tab_resumen()
    elif vista == "pcarga":
        _tab_pcarga()
    elif vista == "importar":
        _tab_importar()
    elif vista == "exportar":
        _tab_exportar()
    elif vista == "reconciliar":
        _tab_reconciliar()
    elif vista == "rebuild":
        _tab_rebuild_csv()
    elif vista == "purgar":
        _tab_purgar()
    elif vista == "avanzado":
        _tab_avanzado()
