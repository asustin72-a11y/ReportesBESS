#!/usr/bin/env python3
"""Inicializa data/Tarifas/Ultima_Sincronizacion.csv desde MAX(fecha) en SQLite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import RUTA_BD_PERFILES, RUTA_ULTIMA_SINCRONIZACION
from bess.data.sync_cursor import inicializar_desde_bd, leer_mapa


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sobrescribir",
        action="store_true",
        help="Reemplazar todas las filas del CSV con el estado actual de la BD.",
    )
    args = parser.parse_args()

    n = inicializar_desde_bd(
        RUTA_BD_PERFILES,
        RUTA_ULTIMA_SINCRONIZACION,
        sobrescribir=args.sobrescribir,
    )
    print(f"Archivo: {RUTA_ULTIMA_SINCRONIZACION}")
    print(f"Filas actualizadas: {n}")
    for med, fecha in sorted(leer_mapa().items()):
        print(f"  {med}: {fecha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
