"""Barra lateral (admin / usuario)."""

from __future__ import annotations

import os
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from bess.config.constants import VERSION
from bess.config import rutas as rutas_mod
from bess.config.subestaciones import SUBESTACIONES, archivos_fuente_requeridos
from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.config.esquema_tarifa import ESQUEMA_DIST, ESQUEMA_GDMTH
from bess.tariffs.loader import cargar_tarifas
from bess.ui.components import html_tarifas_sidebar, obtener_logo_html
from bess.ui.catalog_check import medidores_pendientes_validacion, puede_generar_reportes
from bess.ui.pipeline_status import (
    establecer_banner_pipeline,
    html_flujo_trabajo_sidebar,
    render_banner_pipeline,
)
from bess.ui.navigation import html_guia_usuario_sidebar
from bess.data.sync_preflight import advertencias_sidebar

def _inyectar_script_sidebar(expandida: bool):
    """Ajusta la sidebar tras el login (Streamlit fija el estado inicial solo al cargar la app)."""
    expandida_js = "true" if expandida else "false"
    js = f"""
    (function () {{
        const DEBE_EXPANDIR = {expandida_js};

        function doc() {{
            return window.parent && window.parent.document ? window.parent.document : document;
        }}

        function sidebarExpandida(sidebar) {{
            return sidebar && sidebar.getAttribute('aria-expanded') === 'true';
        }}

        function botonColapsar(d) {{
            return (
                d.querySelector('[data-testid="stSidebarCollapseButton"]') ||
                d.querySelector('[data-testid="stHeader"] [data-testid="stBaseButton-headerNoPadding"]') ||
                d.querySelector('[data-testid="stHeader"] button[aria-label*="sidebar" i]') ||
                d.querySelector('[data-testid="stHeader"] button[aria-label*="Close" i]') ||
                d.querySelector('[data-testid="stHeader"] button')
            );
        }}

        function botonExpandir(d) {{
            return (
                d.querySelector('[data-testid="stSidebarCollapsedControl"] button') ||
                d.querySelector('[data-testid="stSidebarCollapsedControl"]') ||
                d.querySelector('[data-testid="collapsedControl"]') ||
                d.querySelector('[data-testid="stExpandSidebarButton"]')
            );
        }}

        function ajustar() {{
            const d = doc();
            const sidebar = d.querySelector('section[data-testid="stSidebar"]');
            if (!sidebar) return;
            const abierta = sidebarExpandida(sidebar);
            if (abierta === DEBE_EXPANDIR) return;
            const btn = DEBE_EXPANDIR ? botonExpandir(d) : botonColapsar(d);
            if (btn) btn.click();
        }}

        [0, 80, 200, 500, 1000, 1800].forEach(function (ms) {{
            setTimeout(ajustar, ms);
        }});
    }})();
    """
    _emitir_script_sidebar(f"<script>{js}</script>")


def _inyectar_ocultar_sidebar_visualizador():
    """Oculta por completo la barra lateral para el rol user (visualizador)."""
    js = r"""
    (function () {
        function doc() {
            return window.parent && window.parent.document ? window.parent.document : document;
        }

        function ocultar() {
            const d = doc();
            d.body.classList.add('bess-rol-user-mode');

            const sidebar = d.querySelector('section[data-testid="stSidebar"]');
            if (sidebar) {
                sidebar.style.setProperty('display', 'none', 'important');
                sidebar.style.setProperty('visibility', 'hidden', 'important');
                sidebar.style.setProperty('width', '0', 'important');
                sidebar.style.setProperty('min-width', '0', 'important');
                sidebar.style.setProperty('max-width', '0', 'important');
                sidebar.style.setProperty('overflow', 'hidden', 'important');
                sidebar.setAttribute('aria-hidden', 'true');
            }

            d.querySelectorAll(
                '[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],'
                + '[data-testid="stExpandSidebarButton"]'
            ).forEach(function (el) {
                el.style.setProperty('display', 'none', 'important');
                el.style.setProperty('visibility', 'hidden', 'important');
                el.style.setProperty('pointer-events', 'none', 'important');
            });

            const main = d.querySelector('[data-testid="stAppViewContainer"] > .main');
            if (main) {
                main.style.setProperty('margin-left', '0', 'important');
                main.style.setProperty('padding-left', '0', 'important');
            }
        }

        ocultar();
        [0, 40, 120, 300, 700, 1500].forEach(function (ms) {
            setTimeout(ocultar, ms);
        });

        const d = doc();
        if (d.__bessUserSidebarObs) return;
        const app = d.querySelector('[data-testid="stApp"]') || d.body;
        d.__bessUserSidebarObs = new MutationObserver(function () {
            if (d.body.classList.contains('bess-rol-user-mode')) ocultar();
        });
        d.__bessUserSidebarObs.observe(app, { childList: true, subtree: true });
    })();
    """
    _emitir_script_sidebar(f"<script>{js}</script>")


def _emitir_script_sidebar(markup: str):
    if hasattr(st, "html"):
        try:
            st.html(markup, height=0)
        except TypeError:
            st.html(markup)
    else:
        components.html(markup, height=0)


def _pie_sidebar():
    st.caption(f'Sistema BESS v{VERSION}')


def sidebar_branding(es_admin):
    logo_html = obtener_logo_html(288)
    subtitulo = 'Panel de Control' if es_admin else 'Visualizador'
    logo_block = (
        f'<div style="background:white;border-radius:8px;padding:6px 10px;display:inline-block;margin-bottom:8px;">{logo_html}</div>'
        if logo_html else '<h2 style="color:white;margin:0;font-size:20px;">⚡ BESS</h2>'
    )
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a5276,#2e86c1);padding:16px;border-radius:12px;text-align:center;margin-bottom:16px;">
        {logo_block}
        <p style="color:rgba(255,255,255,0.9);margin:4px 0 0;font-size:12px;font-weight:500;">{subtitulo}</p>
    </div>
    """, unsafe_allow_html=True)


def _sidebar_ayuda():
    """Flujo de trabajo — primera sección del panel admin."""
    with st.expander("Ayuda", expanded=False):
        st.markdown(html_flujo_trabajo_sidebar(), unsafe_allow_html=True)


def _sidebar_admin_catalogo():
    en_cat = st.session_state.get("modo_vista") == "admin_catalogo"
    with st.expander("🏭 Catálogo", expanded=en_cat):
        st.caption("Subestaciones, medidores, tarifas y usuarios.")
        etiqueta = "Volver al reporteador" if en_cat else "Administrar catálogo"
        if st.button(etiqueta, use_container_width=True, key="toggle_admin_catalogo"):
            if en_cat:
                st.session_state["modo_vista"] = "reporteador"
            else:
                st.session_state["modo_vista"] = "admin_catalogo"
            st.session_state.pop("catalog_admin_cargado", None)
            st.rerun()


def _sidebar_mantenimiento_db():
    en_bd = st.session_state.get("modo_vista") == "mantenimiento_db"
    with st.expander("🗄️ Mantenimiento DB", expanded=en_bd):
        st.caption("SQLite: importar, exportar, reconciliar, rebuild CSV y purgar.")
        etiqueta = "Volver al reporteador" if en_bd else "Abrir herramientas BD"
        if st.button(etiqueta, use_container_width=True, key="toggle_mantenimiento_db"):
            if en_bd:
                st.session_state["modo_vista"] = "reporteador"
            else:
                st.session_state["modo_vista"] = "mantenimiento_db"
            st.session_state.pop("catalog_admin_cargado", None)
            st.rerun()


def _ui_cargar_archivos_sidebar():
    lista_fuente = ", ".join(archivos_fuente_requeridos())
    archivos = st.file_uploader(
        f"Archivos CSV ({lista_fuente})",
        type=['csv'],
        accept_multiple_files=True,
        key="upload",
    )
    if archivos:
        for archivo in archivos:
            if st.button(f"📤 {archivo.name}", key=f"subir_{archivo.name}"):
                try:
                    destino = rutas_mod.ruta_fuente_por_nombre_archivo(archivo.name)
                    if destino is None:
                        st.error(
                            f"❌ No se reconoce {archivo.name}. "
                            "Use el nombre del medidor en el catálogo (ej. ION_Testigo_IUSA1.csv)."
                        )
                        continue
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    with open(destino, "wb") as f:
                        f.write(archivo.getbuffer())
                    st.success(f"✅ {destino.relative_to(DIRECTORIO_FUENTE.parent)} subido")
                    st.session_state["archivos_subidos"] = True
                    establecer_banner_pipeline(
                        "Archivo subido. Siguiente: **Verificar** (paso a paso) o **Procesar todo**.",
                        tipo="info",
                    )
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    st.divider()
    if st.button("Ver archivos fuente", use_container_width=True):
        encontrados = False
        for sub in SUBESTACIONES:
            carpeta = DIRECTORIO_FUENTE / sub.id
            if not carpeta.exists():
                continue
            for a in sorted(carpeta.glob("*.csv")):
                st.write(f"📄 {sub.id}/{a.name}")
                encontrados = True
        if not encontrados:
            st.info("No hay archivos fuente")


def _correr_sincronizar_perfiles(
    *,
    procesar: bool,
    progreso_placeholder,
) -> tuple[int, str, str]:
    """Ejecuta scripts/sincronizar_perfiles.py. Con procesar=True incluye verificar/filtrar/reportes."""
    import subprocess
    import sys
    from pathlib import Path

    from bess.ui.pipeline_progress import ejecutar_subprocess_con_progreso

    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "sincronizar_perfiles.py"
    cmd = [sys.executable, "-u", str(script), "--quiet", "--ui-progress"]
    if procesar:
        cmd.append("--procesar")
    titulo = (
        "Sincronizando y procesando…"
        if procesar
        else "Sincronizando perfiles…"
    )
    timeout = 1200 if procesar else 600
    with progreso_placeholder.container():
        return ejecutar_subprocess_con_progreso(
            cmd,
            cwd=str(root),
            timeout=timeout,
            titulo=titulo,
        )


def _mostrar_resultado_sync(
    rc: int,
    stdout: str,
    stderr: str,
    *,
    proceso_completo: bool = False,
) -> None:
    from bess.config.catalog import invalidar_cache_catalogo
    from bess.data.sync_resumen import html_resumen_sidebar

    salida = (stdout or "").strip()
    ion_off = "Medidor ION no disponible." in salida or "ION: no disponible" in salida
    if rc == 0:
        invalidar_cache_catalogo()
        st.session_state["verificado"] = False
        lineas = [ln.strip() for ln in salida.splitlines() if ln.strip()]
        if lineas:
            st.markdown(html_resumen_sidebar(lineas), unsafe_allow_html=True)
        if proceso_completo:
            st.session_state["verificado"] = True
            st.session_state["filtrado"] = True
            st.session_state["reportes_generados"] = True
            st.success("Proceso completo — sync, verificación, filtrado y reportes.")
            establecer_banner_pipeline(
                "Reportes listos. Consulte el **reporteador** en el área principal."
            )
            return
        pendientes = medidores_pendientes_validacion()
        if ion_off:
            st.warning(
                "Medidor ION (IUSA 1) no disponible. "
                "Sync API/export completados; ION sigue sin validar."
            )
            establecer_banner_pipeline(
                "Sync parcial. Revise medidores sin validar antes de procesar.",
                tipo="warning",
            )
        elif pendientes:
            st.warning(
                f"Sync completada. Pendientes de validar: "
                f"{', '.join(pendientes[:6])}"
                f"{'…' if len(pendientes) > 6 else ''}"
            )
            establecer_banner_pipeline(
                "Sync completada con pendientes. Valide medidores antes de **Procesar todo**.",
                tipo="warning",
            )
        else:
            st.success("Sync completada y medidores validados.")
            establecer_banner_pipeline(
                "Sync completada. Use **Procesar todo** para el flujo completo o continúe paso a paso."
            )
        return

    st.error("La sincronización falló." if not proceso_completo else "El proceso falló.")
    if salida:
        st.markdown(
            html_resumen_sidebar(salida.splitlines()[:12]),
            unsafe_allow_html=True,
        )
    err = (stderr or "").strip()
    if err:
        with st.expander("Detalle del error"):
            st.code(err[:2000])


def _ejecutar_procesar_todo_sidebar(progreso_placeholder):
    import subprocess

    try:
        rc, stdout, stderr = _correr_sincronizar_perfiles(
            procesar=True,
            progreso_placeholder=progreso_placeholder,
        )
        progreso_placeholder.empty()
        _mostrar_resultado_sync(rc, stdout, stderr, proceso_completo=True)
    except subprocess.TimeoutExpired:
        st.error("Tiempo agotado (>20 min). Ejecute el script en consola.")
    except Exception as e:
        st.error(f"Error: {e}")


def _ejecutar_sync_sidebar(progreso_sync):
    import subprocess

    try:
        rc, stdout, stderr = _correr_sincronizar_perfiles(
            procesar=False,
            progreso_placeholder=progreso_sync,
        )
        progreso_sync.empty()
        _mostrar_resultado_sync(rc, stdout, stderr, proceso_completo=False)
    except subprocess.TimeoutExpired:
        st.error("Tiempo agotado (>10 min). Ejecute el script en consola.")
    except Exception as e:
        st.error(f"Error: {e}")


def sidebar_admin(*, mostrar_superadmin: bool = False):
    with st.sidebar:
        sidebar_branding(es_admin=True)

        for aviso in advertencias_sidebar():
            st.warning(aviso)

        _sidebar_ayuda()

        progreso_pipeline = st.empty()

        with st.container(border=True):
            st.markdown(
                '<span class="bess-cta-procesar-marker" aria-hidden="true"></span>',
                unsafe_allow_html=True,
            )
            if st.button(
                "⚡ Procesar todo",
                type="primary",
                use_container_width=True,
                key="pipeline_procesar_todo",
            ):
                _ejecutar_procesar_todo_sidebar(progreso_pipeline)

        progreso_sync = progreso_pipeline
        progreso_reportes = st.empty()

        with st.expander("🔧 Paso a paso", expanded=False):
            st.caption("Sync, verificar, filtrar y generar reportes por separado.")
            if st.button("Sincronizar ahora", use_container_width=True, key="sync_perfiles"):
                _ejecutar_sync_sidebar(progreso_sync)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Verificar", use_container_width=True, key="paso_verificar"):
                    with st.spinner("Verificando archivos..."):
                        try:
                            from bess_core import verificar_datos_fuente

                            exito, mensaje = verificar_datos_fuente()
                            if exito:
                                st.success(f"✅ {mensaje}")
                                st.session_state["verificado"] = True
                                establecer_banner_pipeline(
                                    "Verificación OK. Siguiente: **Filtrar** o **Procesar todo**.",
                                    tipo="info",
                                )
                            else:
                                st.error(f"❌ {mensaje}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

            with col2:
                if st.button("Filtrar", use_container_width=True, key="paso_filtrar"):
                    with st.spinner("Filtrando datos..."):
                        try:
                            from bess_core import filtrar_datos

                            exito, mensaje = filtrar_datos()
                            if exito:
                                st.success(f"✅ {mensaje}")
                                st.session_state["filtrado"] = True
                                establecer_banner_pipeline(
                                    "Filtrado OK. Siguiente: **Generar reportes** o **Procesar todo**.",
                                    tipo="info",
                                )
                            else:
                                st.error(f"❌ {mensaje}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

            if st.button("Generar reportes", use_container_width=True, key="paso_reportes"):
                ok_val, msg_val = puede_generar_reportes()
                if not ok_val:
                    st.error(msg_val)
                else:
                    faltan: list[str] = []
                    for sub in SUBESTACIONES:
                        for med in sub.medidores_consumo:
                            ruta = med.ruta_consumo_lectura(filtrado=True)
                            if not ruta.exists():
                                faltan.append(f"{sub.id}/{med.consumo_filtrado}")
                        ruta_bess = sub.ruta_bess_lectura(filtrado=True)
                        if not ruta_bess.exists():
                            faltan.append(f"{sub.id}/{sub.bess_filtrado}")
                    if faltan:
                        st.error(
                            f"Faltan archivos filtrados: {', '.join(faltan)}. "
                            "Ejecute **Filtrar** antes de generar reportes."
                        )
                    else:
                        try:
                            import os
                            import subprocess
                            import sys
                            from pathlib import Path

                            from bess.ui.pipeline_progress import (
                                ejecutar_subprocess_con_progreso,
                                parse_reporte_subprocess,
                            )

                            root = Path(__file__).resolve().parents[2]
                            script = root / "scripts" / "run_reporte_bess.py"
                            env = os.environ.copy()
                            env["BESS_UI_PROGRESS"] = "1"
                            with progreso_reportes.container():
                                rc, stdout, stderr = ejecutar_subprocess_con_progreso(
                                    [sys.executable, "-u", str(script)],
                                    cwd=str(root),
                                    timeout=900,
                                    titulo="Generando reportes CSV…",
                                    env=env,
                                )
                            progreso_reportes.empty()
                            exito, mensajes = parse_reporte_subprocess(stdout, stderr, rc)
                            if "_error" in mensajes:
                                st.error(f"❌ {mensajes['_error']}")
                                if mensajes.get("_traceback"):
                                    with st.expander("Detalle del error"):
                                        st.code(mensajes["_traceback"])
                            elif exito:
                                st.success("✅ Reportes generados exitosamente")
                                for sub in SUBESTACIONES:
                                    for med in sub.medidores_consumo:
                                        msg = mensajes.get(med.prefijo, "")
                                        if msg:
                                            st.success(
                                                f"   {sub.nombre} · {med.etiqueta}: {msg}"
                                            )
                                st.session_state["reportes_generados"] = True
                                establecer_banner_pipeline(
                                    "Reportes listos. Consulte el **reporteador**."
                                )
                            else:
                                st.warning("⚠️ Procesamiento parcial")
                                for sub in SUBESTACIONES:
                                    for med in sub.medidores_consumo:
                                        msg = mensajes.get(med.prefijo, "")
                                        if msg:
                                            st.warning(
                                                f"   {sub.nombre} · {med.etiqueta}: {msg}"
                                            )
                        except subprocess.TimeoutExpired:
                            st.error("Tiempo agotado (>15 min). Ejecute el proceso en consola.")
                        except OSError as e:
                            st.error(
                                f"❌ Error al escribir archivos de reporte: {e}. "
                                "Cierre Excel u otros programas con CSV abiertos en ArchivosReporte."
                            )
                        except Exception as e:
                            import traceback

                            st.error(f"❌ Error: {e}")
                            with st.expander("Detalle del error"):
                                st.code(traceback.format_exc())

        with st.expander("📂 Cargar archivos", expanded=False):
            _ui_cargar_archivos_sidebar()

        with st.expander("💲 Consulta — Tarifas", expanded=False):
            esquema = st.selectbox(
                "Esquema tarifario",
                [ESQUEMA_DIST, ESQUEMA_GDMTH],
                key="sidebar_tarifas_esquema",
            )
            tarifas = cargar_tarifas(esquema)
            mes = datetime.now().month
            nombres_mes = (
                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
            )
            st.markdown(f"**Mes actual:** {nombres_mes[mes - 1]} {datetime.now().year}")
            st.markdown(html_tarifas_sidebar(tarifas, mes), unsafe_allow_html=True)

        if mostrar_superadmin:
            st.divider()
            _sidebar_admin_catalogo()
            _sidebar_mantenimiento_db()

        render_banner_pipeline()

        st.divider()
        _pie_sidebar()


def _ajustar_sidebar_por_rol(es_operador: bool):
    """Admin/superadmin: expande al entrar. Visualizador (user): barra oculta."""
    if es_operador:
        if st.session_state.get("sidebar_inicial_aplicada"):
            return
        _inyectar_script_sidebar(expandida=True)
        st.session_state["sidebar_inicial_aplicada"] = True
    else:
        _inyectar_ocultar_sidebar_visualizador()


def sidebar_user():
    with st.sidebar:
        sidebar_branding(es_admin=False)
        st.markdown(html_guia_usuario_sidebar(), unsafe_allow_html=True)
        _pie_sidebar()
