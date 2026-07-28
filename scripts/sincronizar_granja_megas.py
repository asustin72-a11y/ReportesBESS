#!/usr/bin/env python3
"""Sincroniza los 21 MEGAs (API Farm → SQLite). Uso cron Linux / CLI.

Produccion (servidor):
  bash scripts/cron_sincronizar_granja.sh
  bash deploy/install-cron-granja.sh

Manual:
  python scripts/sincronizar_granja_megas.py
  python scripts/sincronizar_granja_megas.py --quiet
  python scripts/sincronizar_granja_megas.py --desde 2026-01-01 --hasta 2026-07-28
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from granja.data.sync import MENSAJE_SYNC_OCUPADO, sincronizar_megas_con_lock


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sincronizar 21 MEGAs Granja (API Farm → SQLite)."
    )
    parser.add_argument("--desde", default=None, help="YYYY-MM-DD (opcional)")
    parser.add_argument("--hasta", default=None, help="YYYY-MM-DD (opcional)")
    parser.add_argument("--quiet", action="store_true", help="Menos salida en consola")
    parser.add_argument(
        "--timeout-lock",
        type=float,
        default=0,
        help="Segundos de espera del lock (0 = omitir si hay otra sync)",
    )
    args = parser.parse_args()

    try:
        resumen = sincronizar_megas_con_lock(
            timeout=args.timeout_lock,
            desde=args.desde,
            hasta=args.hasta,
            quiet=args.quiet,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR sync Granja: {exc}", file=sys.stderr)
        return 1

    if resumen is None:
        if not args.quiet:
            print(MENSAJE_SYNC_OCUPADO)
        return 0

    ok = [r for r in resumen if "error" not in r]
    err = [r for r in resumen if "error" in r]
    if not args.quiet:
        print(f"Granja sync: {len(ok)} OK · {len(err)} error(es)")
        for r in err:
            print(f"  ERROR {r.get('medidor')}: {r.get('error')}", file=sys.stderr)

    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
