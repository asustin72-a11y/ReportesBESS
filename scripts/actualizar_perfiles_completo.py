#!/usr/bin/env python3
"""
Actualiza perfiles y regenera reportes (flujo compatible con la app en producción).

  1. BESS + BANCO → SQLite (API IUSASOL), sin ION Modbus
  2. ION → SQLite desde CSV IUSASOL (obligatorio)
  3. Export → ArchivosFuente
  4. Verificar → Filtrar → Generar reportes

Uso:
  python scripts/actualizar_perfiles_completo.py ruta\\ION.csv
  python scripts/actualizar_perfiles_completo.py ruta\\ION.csv --desde 2026-05-01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.core.console import log as print
from bess_core import filtrar_datos, reporte_bess, verificar_datos_fuente
from bess.data.ingest.ion.export_csv import exportar_todos
from bess.data.ingest.ion.import_csv import importar_csv
from bess.config.paths import DIRECTORIO_FUENTE, RUTA_BD_PERFILES
from scripts.sincronizar_perfiles import main as sync_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Actualizar perfiles y regenerar CSV de reportes.")
    parser.add_argument("ion_csv", type=Path, help="CSV IUSASOL del medidor ION (IUSA.IUSA1_*.csv)")
    parser.add_argument("--desde", help="Forzar inicio sync API YYYY-MM-DD")
    parser.add_argument("--hasta", help="Forzar fin sync API YYYY-MM-DD")
    args = parser.parse_args(argv)

    if not args.ion_csv.is_file():
        print(f"ERROR: no existe {args.ion_csv}")
        return 1

    sync_args = ["--sin-ion"]
    if args.desde:
        sync_args.extend(["--desde", args.desde])
    if args.hasta:
        sync_args.extend(["--hasta", args.hasta])

    print("=" * 70)
    print("1/4 — BESS + BANCO (API → SQLite → export)")
    print("=" * 70)
    if sync_main(sync_args) != 0:
        return 1

    print("\n" + "=" * 70)
    print("2/4 — ION (CSV IUSASOL → SQLite, sobrescribe traslape Modbus)")
    print("=" * 70)
    if importar_csv(args.ion_csv, RUTA_BD_PERFILES, "ION") != 0:
        return 1

    print("\n" + "=" * 70)
    print("3/4 — Export ION → ArchivosFuente")
    print("=" * 70)
    if exportar_todos(RUTA_BD_PERFILES, DIRECTORIO_FUENTE) != 0:
        return 1

    print("\n" + "=" * 70)
    print("4/4 — Verificar → Filtrar → Reportes")
    print("=" * 70)
    ok, msg = verificar_datos_fuente()
    print(msg)
    if not ok:
        return 1
    ok, msg = filtrar_datos()
    print(msg)
    if not ok:
        return 1
    ok, mensajes = reporte_bess()
    if "_error" in mensajes:
        print(mensajes["_error"])
        return 1
    for prefijo, msg in mensajes.items():
        if not prefijo.startswith("_"):
            print(f"{prefijo}: {msg}")
    if not ok:
        return 1

    print("\nListo. Reinicie o recargue la app Streamlit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
