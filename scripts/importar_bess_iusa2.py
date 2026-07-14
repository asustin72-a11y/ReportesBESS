#!/usr/bin/env python3
"""
Importa un CSV de perfil del BESS IUSA 2 (CS3190) → SQLite (medidor BESS_IUSA2).

Útil para backfill histórico desde exportación IUSASOL antes de usar solo API.

Uso:
  python scripts/importar_bess_iusa2.py ruta\\00000000CS3190*.csv
  python scripts/importar_bess_iusa2.py ruta\\archivo.csv --solo-faltantes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.data.ingest.ion import db
from bess.data.ingest.ion.import_csv import importar_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importar CSV del BESS · Subestación IUSA 2 (CS3190)",
    )
    parser.add_argument("csv", type=Path, help="Ruta al archivo CSV de perfil")
    parser.add_argument("--bd", type=Path, default=db.RUTA_BD_DEFAULT)
    parser.add_argument("--solo-faltantes", action="store_true")
    parser.add_argument(
        "--sin-filtro-dia",
        action="store_true",
        help="No omitir el primer registro del día si no es 00:05.",
    )
    args = parser.parse_args(argv)
    return importar_csv(
        args.csv,
        args.bd,
        db.MEDIDOR_BESS_IUSA2,
        solo_faltantes=args.solo_faltantes,
        sin_filtro_dia=args.sin_filtro_dia,
    )


if __name__ == "__main__":
    raise SystemExit(main())
