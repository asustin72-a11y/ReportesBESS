"""Pipeline ETL: verificación, filtrado y agregados CSV.

Los submódulos (`orchestrator`, `aggregates`, `pipeline`, etc.) se importan
directamente desde su ruta. No reexportar aquí: evita cargar reportes al
sincronizar perfiles (`from bess.data.sync_resumen import ...`).
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "identificar_y_renombrar_archivos": (
        "bess.data.ingest.identify",
        "identificar_y_renombrar_archivos",
    ),
    "leer_archivo_perfil": ("bess.data.ingest.readers", "leer_archivo_perfil"),
    "leer_sin_agrupar": ("bess.data.ingest.readers", "leer_sin_agrupar"),
    "leer_y_agrupar_por_hora": (
        "bess.data.ingest.readers",
        "leer_y_agrupar_por_hora",
    ),
    "procesar_archivo_verificacion": (
        "bess.data.pipeline.verify",
        "procesar_archivo_verificacion",
    ),
    "verificar_datos_fuente": ("bess.data.pipeline.verify", "verificar_datos_fuente"),
    "generar_archivo_limpio": ("bess.data.pipeline.clean", "generar_archivo_limpio"),
    "filtrar_datos": ("bess.data.pipeline.filter", "filtrar_datos"),
    "limpiar_archivos_fuente": (
        "bess.data.pipeline.filter",
        "limpiar_archivos_fuente",
    ),
    "generar_combinado_por_minuto": (
        "bess.data.aggregates.combined",
        "generar_combinado_por_minuto",
    ),
    "generar_diarios_con_demandas": (
        "bess.data.aggregates.daily",
        "generar_diarios_con_demandas",
    ),
    "generar_reportes_granja": (
        "bess.data.aggregates.granja",
        "generar_reportes_granja",
    ),
    "generar_acumulados": ("bess.data.aggregates.accumulated", "generar_acumulados"),
    "generar_bess_diario": ("bess.data.aggregates.bess_daily", "generar_bess_diario"),
    "procesar_grupo": ("bess.data.orchestrator", "procesar_grupo"),
    "reporte_bess": ("bess.data.orchestrator", "reporte_bess"),
    "_validar_archivos_filtrados": (
        "bess.data.orchestrator",
        "_validar_archivos_filtrados",
    ),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    return getattr(importlib.import_module(module_name), attr_name)
