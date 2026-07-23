#!/usr/bin/env python3
"""
Importa un CSV de perfil del ION de facturación IUSA 2 → SQLite (medidor ION_IUSA2).

Uso:
  python scripts/importar_ion_iusa2.py ruta\\al\\perfil.csv
  python scripts/importar_ion_iusa2.py ruta\\al\\perfil.csv --solo-faltantes

Después puede exportar a ArchivosFuente:
  python -m bess.data.ingest.ion.export_csv --medidor ION_IUSA2
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
        description="Importar CSV del ION de facturación · Subestación IUSA 2",
    )
    parser.add_argument("csv", type=Path, help="Ruta al archivo CSV de perfil")
    parser.add_argument("--bd", type=Path, default=db.RUTA_BD_DEFAULT)
    parser.add_argument(
        "--solo-faltantes",
        action="store_true",
        help="Insertar solo timestamps que no existen en BD.",
    )
    args = parser.parse_args(argv)
    return importar_csv(
        args.csv,
        args.bd,
        db.MEDIDOR_ION_IUSA2,
        solo_faltantes=args.solo_faltantes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
