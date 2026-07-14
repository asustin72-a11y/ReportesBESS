"""Estado del pipeline de datos (sync → verificar → filtrar → reportes)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import streamlit as st

from bess.config import rutas as rutas_mod
from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.config.subestaciones import (
    SUBESTACIONES,
    archivos_fuente_subestacion,
    ruta_combinado_por_prefijo,
)
from bess.ui.catalog_check import medidores_pendientes_validacion

EstadoPaso = Literal["ok", "pendiente", "parcial"]


@dataclass(frozen=True)
class PasoPipeline:
    numero: int
    clave: str
    titulo: str
    estado: EstadoPaso
    detalle: str


@dataclass(frozen=True)
class EstadoPipeline:
    pasos: tuple[PasoPipeline, ...]
    siguiente_clave: str | None
    puede_procesar_todo: bool
    mensaje_bloqueo: str


def _paso_sync() -> PasoPipeline:
    pendientes = medidores_pendientes_validacion()
    if not pendientes:
        return PasoPipeline(1, "sync", "Sincronizar", "ok", "Medidores validados")
    n = len(pendientes)
    return PasoPipeline(
        1, "sync", "Sincronizar", "pendiente", f"{n} medidor(es) sin validar"
    )


def _paso_verificar() -> PasoPipeline:
    total_fuente = 0
    total_ok = 0
    for sub in SUBESTACIONES:
        fuente_dir = DIRECTORIO_FUENTE / sub.id
        proc_dir = DIRECTORIO_PROCESADOS / sub.id
        for archivo in archivos_fuente_subestacion(sub):
            if not (fuente_dir / archivo).exists():
                continue
            total_fuente += 1
            if rutas_mod.resolver_ruta_procesado(proc_dir / archivo).exists():
                total_ok += 1
    if total_fuente == 0:
        return PasoPipeline(2, "verificar", "Verificar", "pendiente", "Sin archivos en fuente")
    if total_ok == total_fuente:
        return PasoPipeline(2, "verificar", "Verificar", "ok", f"{total_ok} archivo(s)")
    if total_ok > 0:
        return PasoPipeline(
            2, "verificar", "Verificar", "parcial", f"{total_ok}/{total_fuente} verificados"
        )
    return PasoPipeline(2, "verificar", "Verificar", "pendiente", "Pendiente de verificar")


def _paso_filtrar() -> PasoPipeline:
    requeridos = 0
    listos = 0
    for sub in SUBESTACIONES:
        proc_dir = DIRECTORIO_PROCESADOS / sub.id
        for med in sub.medidores_consumo:
            requeridos += 1
            if rutas_mod.resolver_ruta_procesado(
                proc_dir / med.consumo_filtrado
            ).exists():
                listos += 1
        requeridos += 1
        if rutas_mod.resolver_ruta_procesado(
            proc_dir / sub.bess_filtrado
        ).exists():
            listos += 1
        if sub.granja_filtrado:
            requeridos += 1
            if rutas_mod.resolver_ruta_procesado(proc_dir / sub.granja_filtrado).exists():
                listos += 1
        if sub.cogeneracion_filtrado:
            requeridos += 1
            if rutas_mod.resolver_ruta_procesado(
                proc_dir / sub.cogeneracion_filtrado
            ).exists():
                listos += 1
    if listos == 0:
        return PasoPipeline(3, "filtrar", "Filtrar", "pendiente", "Sin datos filtrados")
    if listos >= requeridos:
        return PasoPipeline(3, "filtrar", "Filtrar", "ok", "Filtrado completo")
    return PasoPipeline(3, "filtrar", "Filtrar", "parcial", f"{listos}/{requeridos} listos")


def _paso_reportes() -> PasoPipeline:
    requeridos = 0
    listos = 0
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            requeridos += 1
            ruta = ruta_combinado_por_prefijo(med.prefijo)
            if ruta and ruta.exists():
                listos += 1
    if listos == 0:
        return PasoPipeline(4, "reportes", "Reportes", "pendiente", "Sin reportes CSV")
    if listos >= requeridos:
        return PasoPipeline(4, "reportes", "Reportes", "ok", "Reportes generados")
    return PasoPipeline(
        4, "reportes", "Reportes", "parcial", f"{listos}/{requeridos} medidores"
    )


def evaluar_pipeline() -> EstadoPipeline:
    pasos = (_paso_sync(), _paso_verificar(), _paso_filtrar(), _paso_reportes())
    siguiente: str | None = None
    for paso in pasos:
        if paso.estado != "ok":
            siguiente = paso.clave
            break

    pendientes = medidores_pendientes_validacion()
    bloqueo = ""
    if pendientes:
        bloqueo = (
            f"{len(pendientes)} medidor(es) sin validar. "
            "**Procesar todo** sincroniza y valida antes de generar reportes."
        )

    return EstadoPipeline(
        pasos=pasos,
        siguiente_clave=siguiente,
        puede_procesar_todo=True,
        mensaje_bloqueo=bloqueo,
    )


def html_flujo_trabajo_sidebar() -> str:
    """Cuadro de pasos del pipeline (sync → reportes → reporteador)."""
    return """
        <div class="sidebar-flujo">
            <p class="sidebar-flujo-titulo">Flujo de trabajo</p>
            <div class="sidebar-paso"><span>1</span> Sincronizar perfiles (ION + API → ArchivosFuente)</div>
            <div class="sidebar-paso"><span>2</span> Verificar y filtrar datos</div>
            <div class="sidebar-paso"><span>3</span> Generar reportes CSV</div>
            <div class="sidebar-paso"><span>4</span> Consultar en el reporteador</div>
            <p class="sidebar-flujo-nota">⚡ <b>Procesar todo</b> ejecuta los pasos 1–3 en un solo clic.</p>
        </div>
    """


def render_banner_pipeline():
    """Muestra banner persistente tras sync/proceso (session_state)."""
    banner = st.session_state.pop("pipeline_banner", None)
    if not banner:
        return
    tipo = banner.get("tipo", "info")
    texto = banner.get("texto", "")
    if tipo == "success":
        st.success(texto)
    elif tipo == "warning":
        st.warning(texto)
    else:
        st.info(texto)


def establecer_banner_pipeline(texto: str, *, tipo: str = "success"):
    st.session_state["pipeline_banner"] = {"texto": texto, "tipo": tipo}


def render_estado_vacio_reporteador(estado: EstadoPipeline | None = None):
    """CTA cuando el reporteador no tiene datos procesados."""
    estado = estado or evaluar_pipeline()
    st.markdown("### Reporteador sin datos")
    st.markdown(
        "Aún no hay reportes CSV para consultar. Revise **Ayuda** en la barra lateral "
        "y use **Procesar todo** o los pasos en **Paso a paso**."
    )
    with st.container(border=True):
        st.markdown(html_flujo_trabajo_sidebar(), unsafe_allow_html=True)
    if estado.mensaje_bloqueo:
        st.info(estado.mensaje_bloqueo)
