"""Barra lateral (admin / usuario)."""

from __future__ import annotations

import os
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from bess.config.constants import VERSION
from bess.config.subestaciones import SUBESTACIONES, archivos_fuente_requeridos
from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, DIRECTORIO_REPORTES
from bess.tariffs.loader import cargar_tarifas
from bess.ui.components import html_tarifas_sidebar, obtener_logo_html
from bess.ui.navigation import html_guia_usuario_sidebar

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


def sidebar_admin():
    with st.sidebar:
        sidebar_branding(es_admin=True)

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

        with st.expander("🔄 Sincronizar perfiles", expanded=False):
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
                                st.warning(
                                    "Medidor ION (IUSA 1) no disponible. "
                                    "Sync API BESS y exportación completados."
                                )
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
                filtrados = []
                for sub in SUBESTACIONES:
                    for med in sub.medidores_consumo:
                        filtrados.append(med.consumo_filtrado)
                    filtrados.append(sub.bess_filtrado)
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
                            from bess_core import ejecutar_reporte_bess
                            exito, mensajes = ejecutar_reporte_bess()
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
                                            st.success(f"   {sub.nombre} · {med.etiqueta}: {msg}")
                                st.session_state['reportes_generados'] = True
                            else:
                                st.warning("⚠️ Procesamiento parcial")
                                for sub in SUBESTACIONES:
                                    for med in sub.medidores_consumo:
                                        msg = mensajes.get(med.prefijo, "")
                                        if msg:
                                            st.warning(f"   {sub.nombre} · {med.etiqueta}: {msg}")
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


def _ajustar_sidebar_por_rol(es_admin):
    _inyectar_script_sidebar(expandida=es_admin)


def sidebar_user():
    with st.sidebar:
        sidebar_branding(es_admin=False)
        st.markdown(html_guia_usuario_sidebar(), unsafe_allow_html=True)
        _pie_sidebar()
