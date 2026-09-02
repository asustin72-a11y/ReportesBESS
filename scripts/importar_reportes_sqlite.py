#!/usr/bin/env python3
"""Importa CSV de ArchivosReporte → tablas reporte_serie_* (bootstrapping Fase 7).

Uso:
  python scripts/importar_reportes_sqlite.py
  python scripts/importar_reportes_sqlite.py --dir data/ArchivosReporte
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.data.report_store import ensure_reportes_listo, importar_directorio_reportes


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa ArchivosReporte CSV → SQLite")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Directorio base (default: data/ArchivosReporte)",
    )
    args = parser.parse_args()
    ensure_reportes_listo()
    contadores = importar_directorio_reportes(args.dir)
    ok = sum(1 for n in contadores.values() if n >= 0)
    fail = sum(1 for n in contadores.values() if n < 0)
    filas = sum(n for n in contadores.values() if n > 0)
    print(f"Series importadas: {ok} OK, {fail} error(es), {filas} filas totales")
    for ruta, n in sorted(contadores.items()):
        marca = "ERR" if n < 0 else str(n)
        print(f"  {marca:>6}  {ruta}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
