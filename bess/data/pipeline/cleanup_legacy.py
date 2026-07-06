"""Limpieza de CSV legacy (Fase 7) antes de regenerar con nomenclatura por subestación."""

from __future__ import annotations

import shutil
from pathlib import Path

from bess.config.paths import (
    DIRECTORIO_BASE,
    DIRECTORIO_FUENTE,
    DIRECTORIO_PROCESADOS,
    DIRECTORIO_REPORTES,
)
from bess.config.rutas import asegurar_carpetas_desde_catalogo
from bess.core.console import log

print = log

_PERFILES_GRANJA = DIRECTORIO_BASE / "perfiles_granja"

# CSV sueltos en data/ (pruebas ION, no pipeline)
_TMP_DATA_PATTERNS = ("tmp_*.csv", "ION_*primeros*.csv")

_CARPETAS_PIPELINE = (
    DIRECTORIO_FUENTE,
    DIRECTORIO_PROCESADOS,
    DIRECTORIO_REPORTES,
)


def _csv_pipeline_en(carpeta: Path) -> list[Path]:
    if not carpeta.is_dir():
        return []
    return sorted(
        p
        for p in carpeta.rglob("*.csv")
        if p.is_file() and p.name != ".gitkeep"
    )


def _csv_por_hora() -> list[Path]:
    encontrados: list[Path] = []
    for base in (DIRECTORIO_REPORTES, DIRECTORIO_PROCESADOS, DIRECTORIO_BASE):
        if not base.is_dir():
            continue
        for p in base.rglob("*POR_HORA*.csv"):
            if p.is_file():
                encontrados.append(p)
    return sorted(set(encontrados))


def _archivos_tmp_data() -> list[Path]:
    encontrados: list[Path] = []
    for patron in _TMP_DATA_PATTERNS:
        encontrados.extend(DIRECTORIO_BASE.glob(patron))
    return sorted({p for p in encontrados if p.is_file()})


def _contenido_perfiles_granja() -> list[Path]:
    if not _PERFILES_GRANJA.is_dir():
        return []
    return sorted(p for p in _PERFILES_GRANJA.rglob("*") if p.is_file())


def listar_archivos_legacy() -> list[Path]:
    """Lista todo lo que borraría limpiar_datos_legacy (sin tocar Tarifas ni SQLite)."""
    candidatos: list[Path] = []
    for carpeta in _CARPETAS_PIPELINE:
        candidatos.extend(_csv_pipeline_en(carpeta))
    candidatos.extend(_csv_por_hora())
    candidatos.extend(_archivos_tmp_data())
    candidatos.extend(_contenido_perfiles_granja())
    return sorted({p.resolve() for p in candidatos})


def limpiar_columna_validado() -> int:
    """Vacía Validado en el catálogo SQLite (requiere nuevo sync antes de Generar reportes)."""
    from bess.config.catalog import invalidar_cache_catalogo
    from bess.data.catalog_db import limpiar_validado_bd

    n = limpiar_validado_bd()
    invalidar_cache_catalogo()
    print(f"Validado reiniciado en catálogo BD ({n} medidor(es))")
    return n


def limpiar_datos_legacy(
    *,
    ejecutar: bool = False,
    reset_validado: bool = False,
) -> tuple[list[Path], list[str]]:
    """
    Elimina CSV legacy del pipeline y perfiles_granja/.
    Conserva: Tarifas/, logos, modbus_map, bess_perfiles.db, ReportesDiarios/.
    """
    archivos = listar_archivos_legacy()
    errores: list[str] = []
    borrados: list[Path] = []

    if not ejecutar:
        return archivos, errores

    for ruta in archivos:
        try:
            ruta.unlink()
            borrados.append(ruta)
            print(f"  eliminado: {ruta.relative_to(DIRECTORIO_BASE)}")
        except OSError as exc:
            errores.append(f"{ruta}: {exc}")

    if _PERFILES_GRANJA.is_dir():
        try:
            shutil.rmtree(_PERFILES_GRANJA)
            _PERFILES_GRANJA.mkdir(parents=True, exist_ok=True)
            print(f"  vaciado: { _PERFILES_GRANJA.relative_to(DIRECTORIO_BASE) }/")
        except OSError as exc:
            errores.append(f"perfiles_granja: {exc}")

    asegurar_carpetas_desde_catalogo()

    if reset_validado:
        limpiar_columna_validado()

    print(f"\nLimpieza: {len(borrados)} archivo(s) eliminado(s).")
    return borrados, errores
