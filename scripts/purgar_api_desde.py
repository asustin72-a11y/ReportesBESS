#!/usr/bin/env python3
"""Borra perfil_carga API desde una fecha y ajusta sync_state (re-sync incremental)."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import RUTA_BD_PERFILES
from bess.config.subestaciones import aliases_sync_api
from bess.data.ingest.ion import db
from bess.data.sync_cursor import guardar_ultima_fecha

MEDIDOR_GRANJA = db.MEDIDOR_GRANJA_IUSA2


def medidores_api_bd() -> list[str]:
    ids: list[str] = []
    vistos: set[str] = set()
    for _alias, medidor_bd in aliases_sync_api():
        if medidor_bd not in vistos:
            ids.append(medidor_bd)
            vistos.add(medidor_bd)
    if MEDIDOR_GRANJA not in vistos:
        ids.append(MEDIDOR_GRANJA)
    return ids


def purgar(
    medidor_id: str,
    corte: str,
    *,
    ejecutar: bool,
) -> dict:
    conn = sqlite3.connect(RUTA_BD_PERFILES)
    conn.row_factory = sqlite3.Row
    try:
        pendiente = conn.execute(
            """
            SELECT COUNT(*) AS n, MIN(fecha) AS mn, MAX(fecha) AS mx
            FROM perfil_carga
            WHERE medidor_id = ? AND fecha >= ?
            """,
            (medidor_id, corte),
        ).fetchone()
        previo = conn.execute(
            """
            SELECT MAX(fecha) AS mx
            FROM perfil_carga
            WHERE medidor_id = ? AND fecha < ?
            """,
            (medidor_id, corte),
        ).fetchone()
        info = {
            "medidor": medidor_id,
            "eliminar": int(pendiente["n"]),
            "rango": (pendiente["mn"], pendiente["mx"]),
            "conservar_hasta": previo["mx"],
        }
        if not ejecutar or pendiente["n"] == 0:
            return info

        conn.execute(
            """
            DELETE FROM perfil_carga
            WHERE medidor_id = ? AND fecha >= ?
            """,
            (medidor_id, corte),
        )
        if previo["mx"]:
            db.actualizar_sync_state(conn, medidor_id, previo["mx"])
            guardar_ultima_fecha(medidor_id, previo["mx"])
        else:
            conn.execute("DELETE FROM sync_state WHERE medidor_id = ?", (medidor_id,))
        conn.commit()
        return info
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--desde",
        default="2026-06-20 00:00:00",
        help="Borrar registros con fecha >= este valor (default: 2026-06-20 00:00:00)",
    )
    parser.add_argument(
        "--medidor",
        action="append",
        help="ID en BD (repita para varios). Default: todos los de API IUSASOL.",
    )
    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Aplicar borrado (sin esto solo muestra resumen).",
    )
    args = parser.parse_args()

    medidores = args.medidor or medidores_api_bd()
    print(f"Corte: {args.desde}")
    print(f"Modo: {'EJECUTAR' if args.ejecutar else 'dry-run'}")
    print("-" * 60)

    for med in medidores:
        info = purgar(med, args.desde, ejecutar=args.ejecutar)
        r0, r1 = info["rango"]
        rango_txt = f"{r0} .. {r1}" if info["eliminar"] else "-"
        print(
            f"{info['medidor']}: eliminar {info['eliminar']} ({rango_txt}) | "
            f"conservar hasta {info['conservar_hasta'] or '(ninguno)'}"
        )

    if not args.ejecutar:
        print("-" * 60)
        print("Dry-run. Agregue --ejecutar para borrar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
