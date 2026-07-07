"""Navegación principal y ayuda contextual del reporteador."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

SECCIONES = [
    {
        "key": "operacion",
        "pill": "Operación",
        "titulo": "Operación BESS",
        "icono": "⚡",
        "resumen": "Resumen diario o por rango: carga, descarga, eficiencia y arbitraje.",
        "capacidades": [
            "Perfil de carga",
            "Arbitraje por periodo",
            "Descarga PNG",
        ],
    },
    {
        "key": "analisis",
        "pill": "Análisis",
        "titulo": "Análisis",
        "icono": "📊",
        "resumen": "Demanda, costos de energía y capacidad CFE con y sin BESS.",
        "capacidades": [
            "Demanda 15 min",
            "Costo por periodo",
            "Capacidad CFE",
        ],
    },
    {
        "key": "participacion",
        "pill": "Participación",
        "titulo": "Participación Capacidad",
        "icono": "⚖️",
        "resumen": "Atribución Shapley de la reducción de capacidad CFE (generación vs BESS).",
        "capacidades": [
            "Escenarios D0–Dcb",
            "Shapley kW y MXN",
            "Criterio CFE",
        ],
    },
    {
        "key": "tendencia",
        "pill": "Tendencia",
        "titulo": "Tendencia",
        "icono": "📈",
        "resumen": "Evolución histórica de consumo y operación de la batería.",
        "capacidades": [
            "Consumo por periodo",
            "Con vs sin BESS",
            "Carga y descarga",
        ],
    },
    {
        "key": "generacion",
        "pill": "Generación",
        "titulo": "Generación",
        "icono": "☀️",
        "resumen": "Energía generada por el recurso de generación de cada subestación.",
        "capacidades": [
            "Generación por periodo",
            "Acumulado mensual",
            "Gráfica diaria",
        ],
    },
    {
        "key": "reportes",
        "pill": "Reportes",
        "titulo": "Reportes",
        "icono": "📄",
        "resumen": "Reporte diario y reporte acumulado de ahorros BESS (PDF descargable).",
        "capacidades": [
            "Reporte diario",
            "Reporte acumulado",
            "PDF descargable",
        ],
    },
    {
        "key": "recibo",
        "pill": "Recibo",
        "titulo": "Recibo CFE",
        "icono": "🧾",
        "resumen": "Recibo estimado mensual con y sin BESS según tarifas vigentes.",
        "capacidades": [
            "Escenario con BESS",
            "Escenario sin BESS",
            "PDF del recibo",
        ],
    },
]


def secciones_para_subestacion(sub_id: str | None) -> list[dict]:
    """Filtra Participación y Generación si no aplican a la subestación."""
    from bess.config.subestaciones import (
        recurso_generacion_subestacion,
        soporta_participacion_capacidad,
    )

    visibles: list[dict] = []
    for seccion in SECCIONES:
        key = seccion["key"]
        if key == "participacion" and sub_id and not soporta_participacion_capacidad(sub_id):
            continue
        if key == "generacion" and sub_id and not recurso_generacion_subestacion(sub_id):
            continue
        visibles.append(seccion)
    return visibles


def _etiqueta_pill(s: dict) -> str:
    return f'{s["icono"]} {s["pill"]}'


def _seleccionar_seccion(key: str):
    st.session_state["seccion_activa"] = key


def _inyectar_script_ayuda_nav(secciones: list[dict], delay_ms: int = 2000):
    """Tooltips al hover (2 s) sobre los botones de navegación."""
    sections_json = json.dumps(
        [
            {
                "key": s["key"],
                "icono": s["icono"],
                "titulo": s["titulo"],
                "resumen": s["resumen"],
                "capacidades": s["capacidades"],
            }
            for s in secciones
        ],
        ensure_ascii=False,
    )
    js = f"""
    (function () {{
        const DELAY = {delay_ms};
        const SECTIONS = {sections_json};

        function rootDoc() {{
            return window.parent && window.parent.document
                ? window.parent.document
                : document;
        }}

        function viewWin() {{
            return window.parent && window.parent !== window
                ? window.parent
                : window;
        }}

        let hoverTimer = null;

        function hideAllTips() {{
            if (hoverTimer) {{
                clearTimeout(hoverTimer);
                hoverTimer = null;
            }}
            rootDoc().querySelectorAll(".bess-floating-tip").forEach(function (tip) {{
                tip.classList.remove("visible");
                tip.style.top = "-9999px";
                tip.style.left = "-9999px";
            }});
        }}

        function isUsableButton(btn) {{
            if (!btn || !btn.isConnected) return false;
            const rect = btn.getBoundingClientRect();
            if (rect.width < 4 || rect.height < 4) return false;
            const vh = viewWin().innerHeight;
            if (rect.bottom < 0 || rect.top > vh) return false;
            const style = viewWin().getComputedStyle(btn);
            if (style.visibility === "hidden" || style.display === "none") return false;
            return true;
        }}

        function buildTipCard(s) {{
            const tip = document.createElement("div");
            tip.id = "bess-tip-" + s.key;
            tip.className = "bess-floating-tip";
            tip.setAttribute("role", "tooltip");

            const icon = document.createElement("div");
            icon.className = "nav-hub-icon";
            icon.textContent = s.icono;

            const title = document.createElement("div");
            title.className = "nav-hub-title";
            title.textContent = s.titulo;

            const resumen = document.createElement("p");
            resumen.className = "nav-hub-resumen";
            resumen.textContent = s.resumen;

            const caps = document.createElement("ul");
            caps.className = "nav-hub-caps";
            (s.capacidades || []).forEach(function (c) {{
                const li = document.createElement("li");
                li.textContent = c;
                caps.appendChild(li);
            }});

            tip.append(icon, title, resumen, caps);
            return tip;
        }}

        function ensureTooltipRoot() {{
            const d = rootDoc();
            d.querySelectorAll(".bess-floating-tip").forEach(function (tip) {{
                tip.classList.remove("visible");
            }});

            const roots = Array.from(d.querySelectorAll("#bess-nav-tooltip-root"));
            let root = roots[0];
            if (!root) {{
                root = d.createElement("div");
                root.id = "bess-nav-tooltip-root";
                root.style.cssText =
                    "position:fixed;top:0;left:0;width:0;height:0;overflow:visible;"
                    + "z-index:999990;pointer-events:none;";
                d.body.appendChild(root);
            }} else if (root.parentElement !== d.body) {{
                d.body.appendChild(root);
            }}
            for (let i = 1; i < roots.length; i++) roots[i].remove();

            d.querySelectorAll(".bess-floating-tip").forEach(function (tip) {{
                if (!root.contains(tip)) tip.remove();
            }});

            SECTIONS.forEach(function (s) {{
                let tip = d.getElementById("bess-tip-" + s.key);
                if (!tip) tip = buildTipCard(s);
                if (!root.contains(tip)) root.appendChild(tip);
            }});
        }}

        function showTip(key, btn) {{
            if (!isUsableButton(btn)) return;
            const d = rootDoc();
            const tip = d.getElementById("bess-tip-" + key);
            if (!tip) return;

            const rect = btn.getBoundingClientRect();
            hideAllTips();

            const vw = viewWin().innerWidth;
            const tipWidth = tip.offsetWidth || 268;
            let left = rect.left;
            const maxLeft = vw - tipWidth - 8;
            if (left > maxLeft) left = Math.max(8, maxLeft);

            tip.style.top = (rect.bottom + 8) + "px";
            tip.style.left = left + "px";
            tip.classList.add("visible");
        }}

        function findNavButton(key) {{
            const d = rootDoc();
            const widgets = d.querySelectorAll(".st-key-nav_btn_" + key);
            for (let i = widgets.length - 1; i >= 0; i--) {{
                const btn = widgets[i].querySelector("button");
                if (isUsableButton(btn)) return btn;
            }}
            return null;
        }}

        function bindButtons() {{
            SECTIONS.forEach(function (s) {{
                const key = s.key;
                const btn = findNavButton(key);
                if (!btn || btn.dataset.bessTipBound) return;
                btn.dataset.bessTipBound = "1";
                btn.addEventListener("mouseenter", function () {{
                    hideAllTips();
                    hoverTimer = setTimeout(function () {{
                        showTip(key, btn);
                    }}, DELAY);
                }});
                btn.addEventListener("mouseleave", hideAllTips);
                btn.addEventListener("click", hideAllTips);
            }});
        }}

        function init() {{
            const d = rootDoc();
            ensureTooltipRoot();
            hideAllTips();
            bindButtons();
            if (d.__bessNavTipReady) return;
            d.__bessNavTipReady = true;
            const app = d.querySelector('[data-testid="stApp"]') || d.body;
            const obs = new MutationObserver(function () {{
                bindButtons();
            }});
            obs.observe(app, {{ childList: true, subtree: true }});
            d.__bessNavTipObserver = obs;
            viewWin().addEventListener("scroll", hideAllTips, true);
            d.addEventListener("click", hideAllTips, true);
        }}

        init();
        [120, 400, 900].forEach(function (ms) {{
            setTimeout(init, ms);
        }});
    }})();
    """
    components.html(f"<script>{js}</script>", height=0)


def _inicializar_seccion():
    if "seccion_activa" not in st.session_state:
        st.session_state["seccion_activa"] = SECCIONES[0]["key"]
    elif st.session_state["seccion_activa"] == "reporte":
        st.session_state["seccion_activa"] = "reportes"


def _ajustar_seccion_activa(sub_id: str | None):
    visibles = secciones_para_subestacion(sub_id)
    keys = {s["key"] for s in visibles}
    actual = st.session_state.get("seccion_activa", SECCIONES[0]["key"])
    if actual == "reporte":
        actual = "reportes"
    if actual not in keys and visibles:
        st.session_state["seccion_activa"] = visibles[0]["key"]


def render_navegacion_principal(sub_id: str | None = None) -> str:
    """Botones en columnas + ayuda flotante (hover 2 s)."""
    _inicializar_seccion()
    if sub_id is None:
        sub_id = st.session_state.get("subestacion_principal")
    _ajustar_seccion_activa(sub_id)
    activa = st.session_state["seccion_activa"]
    visibles = secciones_para_subestacion(sub_id)

    with st.container(border=True):
        st.markdown(
            '<span class="bess-nav-panel-marker" aria-hidden="true"></span>'
            '<p class="nav-pills-label">Secciones del reporteador</p>',
            unsafe_allow_html=True,
        )

        cols = st.columns(len(visibles), gap="small")
        for col, seccion in zip(cols, visibles):
            with col:
                es_activa = activa == seccion["key"]
                marcador = (
                    '<span class="bess-nav-col-marker bess-nav-active" aria-hidden="true"></span>'
                    if es_activa
                    else '<span class="bess-nav-col-marker" aria-hidden="true"></span>'
                )
                st.markdown(marcador, unsafe_allow_html=True)
                st.button(
                    _etiqueta_pill(seccion),
                    key=f"nav_btn_{seccion['key']}",
                    on_click=_seleccionar_seccion,
                    kwargs={"key": seccion["key"]},
                    type="primary" if es_activa else "secondary",
                    use_container_width=True,
                )

    _inyectar_script_ayuda_nav(visibles)
    return st.session_state["seccion_activa"]


def html_guia_usuario_sidebar() -> str:
    """Lista compacta de módulos para el sidebar de visualizador."""
    items = "".join(
        f'<div class="sidebar-modulo">'
        f'<span class="sidebar-modulo-icon">{s["icono"]}</span>'
        f'<div><strong>{s["titulo"]}</strong>'
        f'<p>{s["resumen"]}</p></div></div>'
        for s in SECCIONES
    )
    return (
        '<div class="sidebar-guia">'
        '<p class="sidebar-guia-titulo">Módulos disponibles</p>'
        f"{items}</div>"
    )
