"""Estado del pipeline de datos (sync → verificar → filtrar → reportes)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import streamlit as st

from bess.config import rutas as rutas_mod
from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.config.subestaciones import (
    SUBESTACIONES,
    archivos_fuente_subestacion,
    ruta_combinado_por_prefijo,
)
from bess.config import subestaciones as subestaciones_mod
from bess.ui.catalog_check import medidores_pendientes_validacion

EstadoPaso = Literal["ok", "pendiente", "parcial"]

# Umbral a partir del cual el desfase entre "última sincronización" y
# "última fecha en el reporte" se considera notable y se avisa en la app.
# Se puso por encima del rezago normal de un flujo manual paso a paso
# (sincronizar y luego, minutos/horas después, procesar) para no generar
# ruido, pero lo bastante bajo para atrapar el caso real que lo motivó:
# reportes regenerados con datos de un respaldo viejo mientras el sync
# ya había avanzado más de un día.
UMBRAL_DESFASE_REPORTE = timedelta(hours=3)


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


@dataclass(frozen=True)
class DesfaseReporte:
    sub_id: str
    etiqueta: str
    ultima_sync: datetime | None
    ultima_reporte: datetime | None

    @property
    def desfase(self) -> timedelta | None:
        if self.ultima_sync is None or self.ultima_reporte is None:
            return None
        return self.ultima_sync - self.ultima_reporte


def _parse_fecha_sync(texto: str | None) -> datetime | None:
    if not texto:
        return None
    txt = texto.strip()
    if not txt:
        return None
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    return dt.replace(tzinfo=None)


def _evaluar_reporte(
    sub_id: str,
    etiqueta: str,
    medidor_id: str,
    ruta_reporte,
    resumen: dict,
    ultima_fecha_hora_escrita,
) -> "DesfaseReporte":
    info = resumen.get(medidor_id)
    ultima_sync = _parse_fecha_sync(info.ultima_sync) if info else None

    ultima_reporte: datetime | None = None
    try:
        ts = ultima_fecha_hora_escrita(ruta_reporte)
    except Exception:
        ts = None
    if ts is not None:
        ultima_reporte = ts.to_pydatetime()

    return DesfaseReporte(sub_id, etiqueta, ultima_sync, ultima_reporte)


def evaluar_desfase_reportes() -> list[DesfaseReporte]:
    """Compara, por subestación, la última fecha ya sincronizada (sync_state
    en SQLite) contra la última fecha escrita en su reporte combinado --
    tanto el de consumo (medidor de facturación) como el de generación
    (granja o cogeneración/individual), si la subestación tiene uno.

    Detecta el caso "el sync (o Filtrar) sigue avanzando pero Reportes se
    quedó congelado en un corte viejo" -- p. ej. un reporte regenerado justo
    después de restaurar un respaldo, antes de que el sync se pusiera al día,
    y nunca vuelto a regenerar tras los sync/filtrados posteriores. Caso real
    que motivó cubrir también generación: GENERACION_ARAGON con Filtrado al
    corriente (11:25) y su combinado congelado varias horas atrás (08:20),
    sin que el aviso original (solo consumo) lo detectara.
    """
    from bess.ui.db_tools.service import resumen_medidores
    from bess.data.aggregates.combined import ultima_fecha_hora_escrita

    try:
        resumen = {r.medidor_id: r for r in resumen_medidores()}
    except Exception:
        return []

    resultado: list[DesfaseReporte] = []
    for sub in SUBESTACIONES:
        med = sub.medidor_facturacion
        if med:
            resultado.append(_evaluar_reporte(
                sub.id, sub.nombre, med.nombre, med.ruta_combinado(),
                resumen, ultima_fecha_hora_escrita,
            ))

        recurso = subestaciones_mod.recurso_generacion_subestacion(sub.id)
        if recurso:
            ruta_gen = rutas_mod.ruta_reporte(
                sub.id, f"COMBINADO_POR_MINUTO_{recurso.prefijo_reporte}.csv"
            )
            resultado.append(_evaluar_reporte(
                sub.id, f"{sub.nombre} · Generación", recurso.prefijo_reporte,
                ruta_gen, resumen, ultima_fecha_hora_escrita,
            ))
    return resultado


def render_aviso_reporte_desactualizado():
    """Aviso persistente (a diferencia de render_banner_pipeline, no se
    borra al mostrarse) si algún reporte quedó notablemente atrás respecto
    a su última sincronización. Se evalúa en cada render de página."""
    desfases = evaluar_desfase_reportes()
    atrasados = [
        d for d in desfases
        if d.desfase is not None and d.desfase > UMBRAL_DESFASE_REPORTE
    ]
    if not atrasados:
        return

    lineas = []
    for d in atrasados:
        horas = d.desfase.total_seconds() / 3600
        lineas.append(
            f"- **{d.etiqueta}**: reporte hasta "
            f"{d.ultima_reporte:%d/%m/%Y %H:%M}, sincronizado hasta "
            f"{d.ultima_sync:%d/%m/%Y %H:%M} (≈{horas:.0f} h de diferencia)"
        )
    st.warning(
        "⚠️ **El reporte mostrado no incluye los datos ya sincronizados "
        "más recientes:**\n\n"
        + "\n".join(lineas)
        + "\n\nPara actualizarlo: en la barra lateral use "
        "**Verificar → Filtrar → Generar reportes**. "
        "Si la API está caída, primero exporte la BD a CSV en consola:\n"
        "`python scripts/sincronizar_perfiles.py --quiet --solo-export`"
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
