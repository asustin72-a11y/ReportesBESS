#!/usr/bin/env python3
"""
Sincroniza el BESS de Subestación IUSA 2 (serial CS3190) vía API IUSASOL → SQLite.

Uso:
  python scripts/sincronizar_bess_iusa2.py
  python scripts/sincronizar_bess_iusa2.py --export
  python scripts/sincronizar_bess_iusa2.py --desde 2026-05-01 --hasta 2026-06-29 --export

Requiere credenciales IUSASOL en .streamlit/secrets.toml o variables de entorno.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import DIRECTORIO_FUENTE, RUTA_BD_PERFILES
from bess.core.console import log as print
from bess.data.ingest.ion import db
from bess.data.ingest.ion.export_csv import exportar
from bess.data.ingest.iusasol.sync_db import sincronizar_bess_iusa2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync API del BESS · Subestación IUSA 2 (CS3190)",
    )
    parser.add_argument("--desde", help="Forzar inicio YYYY-MM-DD")
    parser.add_argument("--hasta", help="Forzar fin YYYY-MM-DD")
    parser.add_argument(
        "--export",
        action="store_true",
        help="Exportar BESS_IUSA2.csv a ArchivosFuente tras sincronizar",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    db.init_db(RUTA_BD_PERFILES)
    resultado = sincronizar_bess_iusa2(
        ruta_bd=RUTA_BD_PERFILES,
        desde=args.desde,
        hasta=args.hasta,
        quiet=args.quiet,
    )

    if "error" in resultado:
        print(f"ERROR BESS IUSA 2: {resultado['error']}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f"BESS IUSA 2: {resultado.get('leidos', 0)} leídos "
            f"({resultado.get('insertados', 0)} nuevos, "
            f"{resultado.get('actualizados', 0)} actualizados) "
            f"{resultado.get('desde')} -> {resultado.get('hasta')}"
        )
        if resultado.get("mensaje") == "Sin rango pendiente (BD al día).":
            print("BD al día; no hubo registros nuevos por descargar.")

    if args.export:
        salida = DIRECTORIO_FUENTE / "BESS_IUSA2.csv"
        codigo = exportar(
            RUTA_BD_PERFILES,
            db.MEDIDOR_BESS_IUSA2,
            salida,
            args.desde,
            args.hasta,
            quiet=args.quiet,
        )
        if codigo != 0:
            return codigo
        if not args.quiet:
            print(f"Exportado: {salida}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
