#!/usr/bin/env python3
"""
Importa MEGA_total_20.csv (suma 20 MEGA) → SQLite (medidor GRANJA_IUSA2).

Útil para carga inicial histórica antes de usar solo la API Farm.

Uso:
  python scripts/importar_granja_iusa2.py
  python scripts/importar_granja_iusa2.py data\\perfiles_granja\\MEGA_total_20.csv
  python scripts/importar_granja_iusa2.py --solo-faltantes --export
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import DIRECTORIO_FUENTE, RUTA_BD_PERFILES
from bess.data.ingest.granja.import_csv import RUTA_MEGA_TOTAL_DEFAULT, importar_mega_total
from bess.data.ingest.ion import db
from bess.data.ingest.ion.export_csv import exportar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importar MEGA_total_20.csv · Subestación IUSA 2 (GRANJA_IUSA2)",
    )
    parser.add_argument(
        "csv",
        type=Path,
        nargs="?",
        default=RUTA_MEGA_TOTAL_DEFAULT,
        help=f"Ruta al CSV (default: {RUTA_MEGA_TOTAL_DEFAULT.name})",
    )
    parser.add_argument("--bd", type=Path, default=RUTA_BD_PERFILES)
    parser.add_argument(
        "--solo-faltantes",
        action="store_true",
        help="Insertar solo timestamps que no existen en BD.",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Exportar GRANJA_IUSA2.csv a ArchivosFuente tras importar.",
    )
    args = parser.parse_args(argv)

    codigo = importar_mega_total(
        args.csv.resolve(),
        args.bd,
        db.MEDIDOR_GRANJA_IUSA2,
        solo_faltantes=args.solo_faltantes,
    )
    if codigo != 0:
        return codigo

    if args.export:
        salida = DIRECTORIO_FUENTE / "GRANJA_IUSA2.csv"
        print(f"\nExportando -> {salida}")
        return exportar(args.bd, db.MEDIDOR_GRANJA_IUSA2, salida)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
