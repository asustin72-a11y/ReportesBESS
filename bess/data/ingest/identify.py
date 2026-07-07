"""Identificación y ubicación de archivos fuente según catálogo CSV."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from bess.config import rutas as rutas_mod
from bess.config.catalog import obtener_catalogo
from bess.config.paths import DIRECTORIO_FUENTE
from bess.config.subestaciones import SUBESTACIONES

from bess.core.console import log

print = log

# Patrones en nombre de archivo → Nombre catálogo (más específicos primero)
_PATRONES_A_NOMBRE: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("ION_TESTIGO_IUSA2", ("ION_IUSA2", "205.203", "IUSA2"), ("IUSA1", "GRANJA", "MEGA")),
    ("Generacion_IUSA_2", ("GRANJA_IUSA2", "MEGA_total", "Generacion_IUSA"), ()),
    ("BESS_SUR", ("BESS_IUSA2", "BESSIUSA2", "CS3190"), ()),
    ("Banco_1", ("CS1996", "BANCO1", "Banco1", "BANCO"), ("IUSA2",)),
    ("ION_Testigo_IUSA1", ("IUSA1", "ION_Testigo", "ION.csv"), ("IUSA2", "CS3190", "CS1996")),
    ("BESS_NORTE", ("CS3878", "BESS.csv"), ("IUSA2", "CS3190", "CS1996", "BANCO")),
    ("Cogeneracion", ("CS1305", "Cogeneracion", "COGEN"), ("IUSA2", "CS3190", "CS1996")),
)


def _coincide_patron(
    archivo: str,
    patrones: tuple[str, ...],
    excluir: tuple[str, ...],
) -> bool:
    archivo_lower = archivo.lower()
    if any(ex.lower() in archivo_lower for ex in excluir):
        return False
    return any(p.lower() in archivo_lower for p in patrones)


def _destino_catalogo(nombre_catalogo: str) -> Path | None:
    cat = obtener_catalogo()
    for m in cat.medidores:
        if m.nombre == nombre_catalogo:
            return rutas_mod.ruta_fuente_medidor(m.nombre, m.subestacion_nombre)
    if nombre_catalogo == "Generacion_IUSA_2":
        return rutas_mod.ruta_fuente("IUSA_2", rutas_mod.nombre_generacion_subestacion("IUSA_2"))
    return None


def _resolver_nombre_desde_archivo(nombre_archivo: str) -> str | None:
    base = nombre_archivo
    if base.lower().endswith(".csv"):
        base = base[:-4]
    cat = obtener_catalogo()
    for m in cat.medidores:
        if m.nombre == base:
            return m.nombre
    for nombre_cat, patrones, excluir in _PATRONES_A_NOMBRE:
        if _coincide_patron(nombre_archivo, patrones, excluir):
            return nombre_cat
    return None


def _archivos_csv_en_fuente() -> list[Path]:
    encontrados: list[Path] = []
    if not DIRECTORIO_FUENTE.exists():
        return encontrados
    for item in DIRECTORIO_FUENTE.iterdir():
        if not item.is_dir():
            continue
        for csv in item.glob("*.csv"):
            if "_backup" not in csv.name.lower():
                encontrados.append(csv)
    return encontrados


def identificar_y_renombrar_archivos():
    """
    Ubica CSV en ArchivosFuente/{Subestacion}/{Nombre}.csv según catálogo.
    Solo procesa archivos ya dentro de subcarpetas por subestación.
    """
    renombrados: dict[str, dict[str, str]] = {}
    errores: list[str] = []

    DIRECTORIO_FUENTE.mkdir(parents=True, exist_ok=True)
    for sub in SUBESTACIONES:
        rutas_mod.dir_subestacion(DIRECTORIO_FUENTE, sub.id).mkdir(parents=True, exist_ok=True)

    archivos = _archivos_csv_en_fuente()
    usados: set[Path] = set()

    print("\n" + "=" * 70)
    print("IDENTIFICANDO ARCHIVOS FUENTE (CATALOGO)")
    print("=" * 70)
    if archivos:
        for a in archivos:
            print(f"   - {a.relative_to(DIRECTORIO_FUENTE)}")
    else:
        print("   (sin CSV en ArchivosFuente)")
    print("=" * 70)

    for ruta in archivos:
        if ruta in usados:
            continue
        nombre_catalogo = _resolver_nombre_desde_archivo(ruta.name)
        if not nombre_catalogo:
            errores.append(f"No se reconoce: {ruta.name}")
            continue

        destino = _destino_catalogo(nombre_catalogo)
        if destino is None:
            errores.append(f"Sin destino en catalogo para {nombre_catalogo}")
            continue

        destino.parent.mkdir(parents=True, exist_ok=True)
        if ruta.resolve() == destino.resolve():
            usados.add(ruta)
            renombrados[nombre_catalogo] = {"origen": str(ruta.name), "destino": str(destino)}
            print(f"OK {destino.relative_to(DIRECTORIO_FUENTE)} (ya en lugar)")
            continue

        backup = destino.with_suffix(".csv_backup")
        try:
            if destino.exists():
                shutil.move(destino, backup)
            shutil.move(str(ruta), destino)
            usados.add(destino)
            renombrados[nombre_catalogo] = {
                "origen": str(ruta.relative_to(DIRECTORIO_FUENTE)),
                "destino": str(destino.relative_to(DIRECTORIO_FUENTE)),
            }
            print(f"OK {ruta.name} -> {destino.relative_to(DIRECTORIO_FUENTE)}")
        except OSError as exc:
            if backup.exists() and not destino.exists():
                shutil.move(backup, destino)
            errores.append(f"Error moviendo {ruta.name}: {exc}")

    print("=" * 70)
    if errores:
        print("Advertencias:")
        for err in errores:
            print(f"   {err}")
    print("=" * 70)

    return {"renombrados": renombrados, "errores": errores}
