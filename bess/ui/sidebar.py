"""Barra lateral (admin / usuario)."""

from __future__ import annotations

import os
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from bess.config.constants import VERSION
from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, DIRECTORIO_REPORTES
from bess.tariffs.loader import cargar_tarifas
from bess.ui.components import html_tarifas_sidebar, obtener_logo_html

def _inyectar_script_sidebar(expandida):
    """Ajusta la sidebar tras el login (Streamlit fija el estado inicial solo al cargar la app)."""
    objetivo = 'true' if expandida else 'false'
    js = f"""
    (function () {{
        function doc() {{
            return window.parent && window.parent.document ? window.parent.document : document;
        }}
        function ajustar() {{
            const d = doc();
            const sidebar = d.querySelector('section[data-testid="stSidebar"]');
            if (!sidebar) return;
            const abierta = sidebar.getAttribute('aria-expanded') === 'true';
            const debeEstarAbierta = {objetivo};
            if (abierta === debeEstarAbierta) return;
            const btn = d.querySelector('[data-testid="stHeader"] button');
            if (btn) btn.click();
        }}
        [80, 250, 600, 1200, 2000].forEach(function (ms) {{
            setTimeout(ajustar, ms);
        }});
    }})();
    """
    markup = f"<script>{js}</script>"
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


def sidebar_admin():
    with st.sidebar:
        sidebar_branding(es_admin=True)

        with st.expander("Cargar archivos", expanded=False):
            archivos = st.file_uploader(
                "Archivos CSV (ION, BESS, Banco1)",
                type=['csv'],
                accept_multiple_files=True,
                key="upload",
            )
            if archivos:
                for archivo in archivos:
                    if st.button(f"📤 {archivo.name}", key=f"subir_{archivo.name}"):
                        try:
                            ruta = os.path.join(DIRECTORIO_FUENTE, archivo.name)
                            with open(ruta, 'wb') as f:
                                f.write(archivo.getbuffer())
                            st.success(f"✅ {archivo.name} subido")
                            st.session_state['archivos_subidos'] = True
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

            st.divider()
            if st.button("Ver archivos fuente", use_container_width=True):
                archivos_fuente = os.listdir(DIRECTORIO_FUENTE) if os.path.exists(DIRECTORIO_FUENTE) else []
                if archivos_fuente:
                    for a in archivos_fuente:
                        st.write(f"📄 {a}")
                else:
                    st.info("No hay archivos fuente")

        with st.expander("Sincronizar perfiles", expanded=False):
            if st.button("Sincronizar ahora", use_container_width=True, key="sync_perfiles"):
                with st.spinner("Sincronizando..."):
                    try:
                        import subprocess
                        import sys
                        from pathlib import Path

                        from bess.data.sync_resumen import html_resumen_sidebar

                        root = Path(__file__).resolve().parents[2]
                        script = root / "scripts" / "sincronizar_perfiles.py"
                        proc = subprocess.run(
                            [sys.executable, str(script), "--quiet"],
                            cwd=str(root),
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=600,
                        )
                        salida = (proc.stdout or "").strip()
                        ion_off = "Medidor ION no disponible." in salida or "ION: no disponible" in salida
                        if proc.returncode == 0:
                            if ion_off:
                                st.warning("Medidor ION no disponible. BESS/BANCO y export OK.")
                            else:
                                st.success("Sync completada. Siguiente: **Procesar todo**.")
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
                            err = (proc.stderr or "").strip()
                            if err:
                                st.caption(err[:500])
                    except subprocess.TimeoutExpired:
                        st.error("Tiempo agotado (>10 min). Ejecute el script en consola.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        with st.expander("Procesar datos", expanded=False):
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
                filtrados = ['BESS_Filtrado.csv', 'ION_Filtrado.csv', 'Banco1_Filtrado.csv']
                faltan = [
                    f for f in filtrados
                    if not os.path.exists(os.path.join(DIRECTORIO_PROCESADOS, f))
                ]
                if faltan:
                    st.error(
                        f"Faltan archivos filtrados: {', '.join(faltan)}. "
                        "Ejecute **Filtrar** antes de generar reportes."
                    )
                else:
                    with st.spinner("Generando reportes..."):
                        try:
                            from bess_core import reporte_bess
                            exito, msg_ion, msg_banco = reporte_bess()
                            if exito:
                                st.success("✅ Reportes generados exitosamente")
                                st.success(f"   ION: {msg_ion}")
                                st.success(f"   BANCO1: {msg_banco}")
                                st.session_state['reportes_generados'] = True
                            else:
                                st.warning("⚠️ Procesamiento parcial")
                                st.warning(f"   ION: {msg_ion}")
                                st.warning(f"   BANCO1: {msg_banco}")
                        except OSError as e:
                            st.error(
                                f"❌ Error al escribir archivos de reporte: {e}. "
                                "Cierre Excel u otros programas con CSV abiertos en ArchivosReporte."
                            )
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

            if st.button("Procesar todo", use_container_width=True):
                with st.spinner("Verificando, filtrando y generando reportes..."):
                    try:
                        from bess_core import verificar_datos_fuente, filtrar_datos, reporte_bess
                        exito_v, msg_v = verificar_datos_fuente()
                        if not exito_v:
                            st.error(msg_v)
                        else:
                            exito_f, msg_f = filtrar_datos()
                            if not exito_f:
                                st.error(msg_f)
                            else:
                                exito_r, msg_ion, msg_banco = reporte_bess()
                                if exito_r:
                                    st.success("Proceso completo: ION y BANCO actualizados")
                                else:
                                    st.warning(f"Parcial — ION: {msg_ion} · BANCO: {msg_banco}")
                    except Exception as e:
                        st.error(f"Error: {e}")

        with st.expander("Tarifas", expanded=False):
            tarifas = cargar_tarifas()
            mes = datetime.now().month
            nombres_mes = (
                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
            )
            st.markdown(f"**Mes actual:** {nombres_mes[mes - 1]} {datetime.now().year}")
            st.markdown(html_tarifas_sidebar(tarifas, mes), unsafe_allow_html=True)
            st.divider()
            from bess.ui.pages import render_editor_tarifas_sidebar
            render_editor_tarifas_sidebar()

        st.divider()
        _pie_sidebar()


def _ajustar_sidebar_por_rol(es_admin):
    _inyectar_script_sidebar(expandida=es_admin)


def sidebar_user():
    with st.sidebar:
        sidebar_branding(es_admin=False)
        st.info("Modo visualización")
        _pie_sidebar()
