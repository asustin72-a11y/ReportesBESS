#!/usr/bin/env python3
"""
Sincroniza suma de generación granja IUSA 2 (20 MEGA) → SQLite → ArchivosFuente.

Uso:
  python scripts/sincronizar_granja_iusa2.py
  python scripts/sincronizar_granja_iusa2.py --export
  python scripts/sincronizar_granja_iusa2.py --desde 2026-05-01 --hasta 2026-06-30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import DIRECTORIO_FUENTE, RUTA_BD_PERFILES
from bess.data.ingest.granja.sync_db import sincronizar_granja_iusa2
from bess.data.ingest.ion import db
from bess.data.ingest.ion.export_csv import exportar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sincronizar granja IUSA 2 (suma 20 MEGA) vía API Farm.",
    )
    parser.add_argument("--bd", type=Path, default=RUTA_BD_PERFILES)
    parser.add_argument("--desde", help="YYYY-MM-DD inicio")
    parser.add_argument("--hasta", help="YYYY-MM-DD fin (default: mañana)")
    parser.add_argument("--granja", help="idcode de granja (default: primera)")
    parser.add_argument("--cantidad", type=int, default=20, help="Medidores MEGA a sumar")
    parser.add_argument("--export", action="store_true", help="Exportar GRANJA_IUSA2.csv")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        resultado = sincronizar_granja_iusa2(
            ruta_bd=args.bd,
            desde=args.desde,
            hasta=args.hasta,
            farm_idcode=args.granja,
            cantidad_medidores=args.cantidad,
            quiet=args.quiet,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f"{resultado['medidor']}: {resultado['leidos']} intervalos "
            f"({resultado['insertados']} nuevos) "
            f"{resultado.get('desde')} -> {resultado.get('hasta')}"
        )

    if args.export and resultado.get("leidos", 0) > 0:
        exportar(
            args.bd,
            db.MEDIDOR_GRANJA_IUSA2,
            DIRECTORIO_FUENTE / "GRANJA_IUSA2.csv",
            quiet=args.quiet,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
