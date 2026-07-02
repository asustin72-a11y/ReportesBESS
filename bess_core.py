# bess_core.py
"""
BESS - Fachada de compatibilidad.
Re-exporta el pipeline de datos, CFE, tarifas y reportes PDF desde bess.*.

Los módulos de reportes (orchestrator, combined, daily, …) se cargan bajo demanda
para que Verificar / Filtrar / Sincronizar no arrastren todo el pipeline.
"""

from __future__ import annotations

import importlib
import warnings
from typing import Any

warnings.filterwarnings("ignore")

# ========== CONFIGURACIÓN GLOBAL (bess.config + bess.core) ==========
from bess.config.constants import ARCHIVO_TARIFAS, TIPOS_TARIFA
from bess.config.paths import (
    DIRECTORIO_BASE,
    DIRECTORIO_FUENTE,
    DIRECTORIO_PROCESADOS,
    DIRECTORIO_REPORTES,
    DIRECTORIO_REPORTES_DIARIOS,
    DIRECTORIO_TARIFAS,
)
from bess.core.kvarh import (
    COLUMNAS_KVARH as _COLUMNAS_KVARH,
    columnas_kvarh as _columnas_kvarh,
    columnas_kvarh_prefijo as _columnas_kvarh_prefijo,
    kvarh_total as _kvarh_total,
    normalizar_columnas_kvarh as _normalizar_columnas_kvarh,
)
from bess.core.numbers import (
    a_num as _a_num,
    fmt_kwh,
    kwh_para_calculo,
    redondear_arriba_kw,
    redondear_arriba_mxn,
    redondear_kwh,
    redondear_mxn_energia,
    sumar_energia,
)

# ========== CONSOLA Y UTILIDADES (bess.core) ==========
from bess.core.console import crear_barra, imprimir_progreso as _imprimir_progreso, log as print
from bess.core.dates import normalizar_fecha, validar_y_convertir_fecha

# ========== PERIODOS CFE (bess.cfe) ==========
from bess.cfe.periods import (
    agregar_periodo,
    es_festivo,
    obtener_periodo_por_fecha_hora,
    obtener_periodo_por_hora,
    obtener_temporada,
)

# ========== PIPELINE DE DATOS (ligero) ==========
from bess.data.ingest.identify import identificar_y_renombrar_archivos
from bess.data.ingest.readers import leer_archivo_perfil, leer_sin_agrupar, leer_y_agrupar_por_hora
from bess.data.pipeline.clean import generar_archivo_limpio
from bess.data.pipeline.filter import filtrar_datos, limpiar_archivos_fuente
from bess.data.pipeline.verify import procesar_archivo_verificacion, verificar_datos_fuente

# ========== TARIFAS, COSTOS CFE Y PDF ==========
from bess.tariffs.loader import cargar_tarifas
from bess.cfe.arbitrage import calcular_arbitraje_dia
from bess.cfe.daily_data import (
    energia_diaria_tiene_sin_bess,
    fila_por_fecha_csv as _fila_por_fecha_csv,
    obtener_bess_energia_dia,
)
from bess.cfe.energy import calcular_costo_energia_dia
from bess.reports.assets import buscar_logo, formatear_fecha_espanol
from bess.reports.daily_pdf import generar_reporte_pdf
from bess.reports.accumulated_pdf import generar_reporte_acumulado_pdf

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "generar_acumulados": ("bess.data.aggregates.accumulated", "generar_acumulados"),
    "generar_bess_diario": ("bess.data.aggregates.bess_daily", "generar_bess_diario"),
    "generar_combinado_por_minuto": (
        "bess.data.aggregates.combined",
        "generar_combinado_por_minuto",
    ),
    "generar_diarios_con_demandas": (
        "bess.data.aggregates.daily",
        "generar_diarios_con_demandas",
    ),
    "procesar_grupo": ("bess.data.orchestrator", "procesar_grupo"),
    "reporte_bess": ("bess.data.orchestrator", "reporte_bess"),
    "_validar_archivos_filtrados": (
        "bess.data.orchestrator",
        "_validar_archivos_filtrados",
    ),
}

_PIPELINE_REPORTES = (
    "bess.core.consumo",
    "bess.data.ingest.readers",
    "bess.data.aggregates.combined",
    "bess.data.aggregates.daily",
    "bess.data.aggregates.accumulated",
    "bess.data.aggregates.bess_daily",
    "bess.data.aggregates.granja",
    "bess.data.orchestrator",
)


def _recargar_pipeline_reportes() -> None:
    """Recarga módulos del pipeline (solo uso en consola; Streamlit usa subproceso)."""
    import sys

    importlib.invalidate_caches()
    for nombre in _PIPELINE_REPORTES:
        sys.modules.pop(nombre, None)
    for nombre in _PIPELINE_REPORTES:
        importlib.import_module(nombre)


def ejecutar_reporte_bess():
    """
    Genera reportes CSV en un subproceso Python limpio.

    Streamlit mantiene módulos viejos en memoria; un proceso nuevo siempre
    lee el código actual del disco.
    """
    import json
    import os
    import subprocess
    import sys

    root = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(root, "scripts", "run_reporte_bess.py")
    proc = subprocess.run(
        [sys.executable, script],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    stdout = proc.stdout or ""
    marker = "__BESS_REPORTE_JSON__"
    if marker not in stdout:
        err = (proc.stderr or "").strip() or stdout.strip()
        if not err:
            err = f"El proceso terminó con código {proc.returncode}"
        return False, {"_error": err}

    payload = json.loads(stdout.split(marker, 1)[1].strip())
    mensajes = dict(payload.get("mensajes") or {})
    if payload.get("traceback"):
        mensajes["_traceback"] = payload["traceback"]
    if not payload.get("ok") and "_error" not in mensajes:
        mensajes["_error"] = "Error al generar reportes"
    return bool(payload.get("ok")), mensajes


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    return getattr(importlib.import_module(module_name), attr_name)
