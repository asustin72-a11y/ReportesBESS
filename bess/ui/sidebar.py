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
from bess.tariffs.loader import cargar_tarifas
from bess.ui.components import html_tarifas_sidebar, obtener_logo_html
from bess.ui.catalog_check import medidores_pendientes_validacion, puede_generar_reportes
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


def html_flujo_trabajo_sidebar() -> str:
    """Cuadro de pasos del pipeline (sync → reportes → reporteador)."""
    return """
        <div class="sidebar-flujo">
            <p class="sidebar-flujo-titulo">Flujo de trabajo</p>
            <div class="sidebar-paso"><span>1</span> Sincronizar perfiles (ION Modbus + BESS API)</div>
            <div class="sidebar-paso"><span>2</span> Verificar y filtrar datos</div>
            <div class="sidebar-paso"><span>3</span> Generar reportes CSV</div>
            <div class="sidebar-paso"><span>4</span> Consultar en el reporteador</div>
        </div>
    """


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
        st.caption("SQLite: importar, exportar y purgar perfiles.")
        etiqueta = "Volver al reporteador" if en_bd else "Abrir herramientas BD"
        if st.button(etiqueta, use_container_width=True, key="toggle_mantenimiento_db"):
            if en_bd:
                st.session_state["modo_vista"] = "reporteador"
            else:
                st.session_state["modo_vista"] = "mantenimiento_db"
            st.session_state.pop("catalog_admin_cargado", None)
            st.rerun()


def sidebar_admin(*, mostrar_superadmin: bool = False):
    with st.sidebar:
        sidebar_branding(es_admin=True)

        for aviso in advertencias_sidebar():
            st.warning(aviso)

        if mostrar_superadmin:
            st.divider()
            _sidebar_admin_catalogo()
            _sidebar_mantenimiento_db()

        pendientes = medidores_pendientes_validacion()
        if pendientes:
            st.warning(
                f"{len(pendientes)} medidor(es) sin validar. "
                "Sincronice antes de **Generar reportes**."
            )

        with st.expander("Ayuda", expanded=False):
            st.markdown(html_flujo_trabajo_sidebar(), unsafe_allow_html=True)

        with st.expander("📂 Cargar archivos", expanded=False):
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

        progreso_sync = st.empty()
        with st.expander("🔄 Sincronizar perfiles", expanded=False):
            if st.button("Sincronizar ahora", use_container_width=True, key="sync_perfiles"):
                try:
                    import subprocess
                    import sys
                    from pathlib import Path

                    from bess.data.sync_resumen import html_resumen_sidebar
                    from bess.config.catalog import invalidar_cache_catalogo
                    from bess.ui.pipeline_progress import ejecutar_subprocess_con_progreso

                    root = Path(__file__).resolve().parents[2]
                    script = root / "scripts" / "sincronizar_perfiles.py"
                    with progreso_sync.container():
                        rc, stdout, stderr = ejecutar_subprocess_con_progreso(
                            [sys.executable, "-u", str(script), "--quiet", "--ui-progress"],
                            cwd=str(root),
                            timeout=600,
                            titulo="Sincronizando perfiles…",
                        )
                    progreso_sync.empty()
                    salida = (stdout or "").strip()
                    ion_off = "Medidor ION no disponible." in salida or "ION: no disponible" in salida
                    if rc == 0:
                        invalidar_cache_catalogo()
                        pendientes = medidores_pendientes_validacion()
                        if ion_off:
                            st.warning(
                                "Medidor ION (IUSA 1) no disponible. "
                                "Sync API/export completados; ION sigue sin validar."
                            )
                        elif pendientes:
                            st.warning(
                                f"Sync completada. Pendientes de validar: "
                                f"{', '.join(pendientes[:6])}"
                                f"{'…' if len(pendientes) > 6 else ''}"
                            )
                        else:
                            st.success(
                                "Sync completada y medidores validados. "
                                "Siguiente: **Procesar todo**."
                            )
                        st.session_state["verificado"] = False
                        lineas = [ln.strip() for ln in salida.splitlines() if ln.strip()]
                        if lineas:
                            st.markdown(html_resumen_sidebar(lineas), unsafe_allow_html=True)
                    else:
                        st.error("La sincronizacion fallo.")
                        if salida:
                            st.markdown(
                                html_resumen_sidebar(salida.splitlines()[:6]),
                                unsafe_allow_html=True,
                            )
                        err = (stderr or "").strip()
                        if err:
                            st.caption(err[:500])
                except subprocess.TimeoutExpired:
                    st.error("Tiempo agotado (>10 min). Ejecute el script en consola.")
                except Exception as e:
                    st.error(f"Error: {e}")

        progreso_reportes = st.empty()
        with st.expander("⚙️ Procesar datos", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Verificar", use_container_width=True):
                    with st.spinner("Verificando archivos..."):
                        try:
                            from bess_core import verificar_datos_fuente
                            exito, mensaje = verificar_datos_fuente()
                            if exito:
                                st.success(f"✅ {mensaje}")
                                st.session_state['verificado'] = True
                            else:
                                st.error(f"❌ {mensaje}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

            with col2:
                if st.button("Filtrar", use_container_width=True):
                    with st.spinner("Filtrando datos..."):
                        try:
                            from bess_core import filtrar_datos
                            exito, mensaje = filtrar_datos()
                            if exito:
                                st.success(f"✅ {mensaje}")
                                st.session_state['filtrado'] = True
                            else:
                                st.error(f"❌ {mensaje}")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

            if st.button("Generar reportes", use_container_width=True, type="primary"):
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
                                st.session_state['reportes_generados'] = True
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

            if st.button("Procesar todo", use_container_width=True):
                ok_val, msg_val = puede_generar_reportes()
                if not ok_val:
                    st.error(msg_val)
                else:
                    with st.spinner("Verificando, filtrando y generando reportes..."):
                        try:
                            from bess_core import verificar_datos_fuente, filtrar_datos, ejecutar_reporte_bess
                            exito_v, msg_v = verificar_datos_fuente()
                            if not exito_v:
                                st.error(msg_v)
                            else:
                                exito_f, msg_f = filtrar_datos()
                                if not exito_f:
                                    st.error(msg_f)
                                else:
                                    exito_r, mensajes = ejecutar_reporte_bess()
                                    if "_error" in mensajes:
                                        st.error(f"❌ {mensajes['_error']}")
                                        if mensajes.get("_traceback"):
                                            with st.expander("Detalle del error"):
                                                st.code(mensajes["_traceback"])
                                    elif exito_r:
                                        partes = []
                                        for sub in SUBESTACIONES:
                                            for med in sub.medidores_consumo:
                                                msg = mensajes.get(med.prefijo, "")
                                                if msg:
                                                    partes.append(f"{med.etiqueta}: {msg}")
                                        st.success(
                                            "Proceso completo — " + "; ".join(partes)
                                            if partes
                                            else "Proceso completo"
                                        )
                                    else:
                                        partes = [
                                            f"{med.etiqueta}: {mensajes.get(med.prefijo, '')}"
                                            for sub in SUBESTACIONES
                                            for med in sub.medidores_consumo
                                            if mensajes.get(med.prefijo)
                                        ]
                                        st.warning("Parcial — " + " · ".join(partes))
                        except Exception as e:
                            st.error(f"Error: {e}")

        with st.expander("💲 Tarifas", expanded=False):
            tarifas = cargar_tarifas()
            mes = datetime.now().month
            nombres_mes = (
                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
            )
            st.markdown(f"**Mes actual:** {nombres_mes[mes - 1]} {datetime.now().year}")
            st.markdown(html_tarifas_sidebar(tarifas, mes), unsafe_allow_html=True)

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
