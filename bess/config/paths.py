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


def nombre_energia_bess_por_dia(prefijo: str) -> str:
    """IUSA 1 (ION/BANCO) usa archivo general; demás subestaciones, por prefijo."""
    if prefijo.upper() in ("ION", "BANCO"):
        return "ENERGIA_BESS_POR_DIA.csv"
    return f"ENERGIA_BESS_POR_DIA_{prefijo}.csv"


def ruta_energia_bess_por_dia(prefijo: str) -> Path:
    return DIRECTORIO_REPORTES / nombre_energia_bess_por_dia(prefijo)


ensure_data_dirs()
