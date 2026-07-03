"""Rutas del proyecto y carpetas de datos."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIRECTORIO_BASE = PROJECT_ROOT / "data"
DIRECTORIO_FUENTE = DIRECTORIO_BASE / "ArchivosFuente"
DIRECTORIO_PROCESADOS = DIRECTORIO_BASE / "ArchivosProcesados"
DIRECTORIO_REPORTES = DIRECTORIO_BASE / "ArchivosReporte"
DIRECTORIO_REPORTES_DIARIOS = DIRECTORIO_BASE / "ReportesDiarios"
DIRECTORIO_TARIFAS = DIRECTORIO_BASE / "Tarifas"
RUTA_ULTIMA_SINCRONIZACION = DIRECTORIO_TARIFAS / "Ultima_Sincronizacion.csv"

# SQLite central de perfiles (ION Modbus + BESS/BANCO API).
RUTA_BD_PERFILES = DIRECTORIO_BASE / "bess_perfiles.db"

_DATA_DIRS = (
    DIRECTORIO_BASE,
    DIRECTORIO_FUENTE,
    DIRECTORIO_PROCESADOS,
    DIRECTORIO_REPORTES,
    DIRECTORIO_REPORTES_DIARIOS,
    DIRECTORIO_TARIFAS,
)


def ensure_data_dirs() -> None:
    for path in _DATA_DIRS:
        os.makedirs(path, exist_ok=True)
    try:
        from bess.config.rutas import asegurar_carpetas_desde_catalogo

        asegurar_carpetas_desde_catalogo()
    except Exception:
        pass


def nombre_energia_bess_por_dia(prefijo: str) -> str:
    """Nombre de archivo BESS diario por subestación (compat. prefijo legado)."""
    from bess.config.rutas import nombre_energia_bess_por_dia as _nombre_sub
    from bess.config.subestaciones import subestacion_por_prefijo

    sub = subestacion_por_prefijo(prefijo)
    if sub:
        return _nombre_sub(sub.id)
    return f"ENERGIA_BESS_POR_DIA_{prefijo}.csv"


def ruta_energia_bess_por_dia(prefijo: str) -> Path:
    from bess.config.rutas import ruta_energia_bess_por_dia as _ruta_sub
    from bess.config.subestaciones import subestacion_por_prefijo

    sub = subestacion_por_prefijo(prefijo)
    if sub:
        nueva = _ruta_sub(sub.id)
        legacy = DIRECTORIO_REPORTES / f"ENERGIA_BESS_POR_DIA_{prefijo}.csv"
        if nueva.exists():
            return nueva
        if legacy.exists():
            return legacy
        return nueva
    return DIRECTORIO_REPORTES / nombre_energia_bess_por_dia(prefijo)


ensure_data_dirs()
