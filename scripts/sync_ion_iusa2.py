#!/usr/bin/env python3
"""
Sincroniza el ION de facturación IUSA 2 (Modbus) → SQLite (medidor ION_IUSA2).

No modifica sincronizar_perfiles.py (lo invoca como paso 2/4).

Uso:
  python scripts/sync_ion_iusa2.py
  python scripts/sync_ion_iusa2.py --desde 2026-05-01 --reiniciar
  python scripts/sync_ion_iusa2.py --export
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import DIRECTORIO_FUENTE, RUTA_BD_PERFILES
from bess.config.subestaciones import subestacion_por_id
from bess.data.ingest.ion import db
from bess.data.ingest.ion.export_csv import exportar
from bess.data.ingest.ion.modbus import (
    DATA_RECORDER_MODULE,
    NUM_SOURCES_DEFAULT,
    PUERTO_DEFAULT,
    ZONA_HORARIA_DEFAULT,
    parse_fecha_arg,
)
from bess.data.ingest.ion.sync import sincronizar

IP_ION_IUSA2 = subestacion_por_id("IUSA2").modbus_ip or "172.16.205.203"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sincronizar ION facturación Subestación IUSA 2 (Modbus → SQLite).",
    )
    parser.add_argument("--bd", type=Path, default=RUTA_BD_PERFILES)
    parser.add_argument("--desde", help="Forzar inicio YYYY-MM-DD o YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--hasta", help="Forzar fin YYYY-MM-DD")
    parser.add_argument("--reiniciar", action="store_true", help="Ignorar ultima_fecha en BD")
    parser.add_argument("--ip", default=IP_ION_IUSA2)
    parser.add_argument("--puerto", type=int, default=PUERTO_DEFAULT)
    parser.add_argument("--modulo-dr", type=int, default=DATA_RECORDER_MODULE)
    parser.add_argument("--sources", type=int, default=NUM_SOURCES_DEFAULT)
    parser.add_argument("--tz", default=ZONA_HORARIA_DEFAULT)
    parser.add_argument(
        "--export",
        action="store_true",
        help="Exportar ION_IUSA2.csv a ArchivosFuente tras sincronizar",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    zona = ZoneInfo(args.tz)
    desde = parse_fecha_arg(args.desde, zona) if args.desde else None
    hasta = parse_fecha_arg(args.hasta, zona, es_hasta=True) if args.hasta else None

    if not args.quiet:
        print(f"ION IUSA 2 · Modbus {args.ip}:{args.puerto}")

    codigo, stats = sincronizar(
        ruta_bd=args.bd,
        modulo_dr=args.modulo_dr,
        num_sources=args.sources,
        zona=zona,
        desde_forzado=desde,
        hasta_forzado=hasta,
        reiniciar=args.reiniciar,
        ip=args.ip,
        puerto=args.puerto,
        medidor_id=db.MEDIDOR_ION_IUSA2,
        quiet=args.quiet,
    )
    if codigo != 0:
        return codigo

    if args.export:
        salida = DIRECTORIO_FUENTE / "ION_IUSA2.csv"
        exportar(args.bd, db.MEDIDOR_ION_IUSA2, salida, quiet=args.quiet)

    if not args.quiet and stats.get("ultima"):
        print(f"Listo. Ultima fecha: {stats['ultima']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
