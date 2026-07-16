#!/usr/bin/env python3
"""Borra de perfil_carga los registros con fecha futura (relleno por
adelantado que la API ISOL/Farm escribia antes del arreglo en
iusasol/sync_db.py y granja/sync_db.py) y ajusta sync_state al ultimo
registro real que se conserva.

Uso habitual (revisar primero, luego aplicar):
    python scripts/limpiar_relleno_futuro.py
    python scripts/limpiar_relleno_futuro.py --ejecutar

Por que hace falta este script y no basta con el arreglo de sync_db.py:
el arreglo evita que un sync NUEVO vuelva a escribir ceros de relleno
futuros, pero no borra los que ya se guardaron en corridas anteriores.
Esos registros viejos se autocorrigen solos al dia siguiente (el
solapamiento de 1 dia en el sync incremental vuelve a pedir y sobrescribir
el dia una vez que ya paso por completo), pero mientras el dia esta en
curso el aviso de "reporte desactualizado" (bess/ui/pipeline_status.py)
sigue viendo sync_state apuntando a esas horas futuras. Este script limpia
esa cola manualmente para no tener que esperar al dia siguiente.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import RUTA_BD_PERFILES
from bess.config.subestaciones import aliases_sync_api
from bess.data.ingest.ion import db
from bess.data.sync_cursor import guardar_ultima_fecha

ZONA_API = ZoneInfo('America/Mexico_City')
MEDIDOR_GRANJA = db.MEDIDOR_GRANJA_IUSA2


def medidores_api_bd() -> list[str]:
    """Todos los medidores sincronizados por API (IUSASOL + granja)."""
    ids: list[str] = []
    vistos: set[str] = set()
    for _alias, medidor_bd in aliases_sync_api():
        if medidor_bd not in vistos:
            ids.append(medidor_bd)
            vistos.add(medidor_bd)
    if MEDIDOR_GRANJA not in vistos:
        ids.append(MEDIDOR_GRANJA)
    return ids


def ahora_local() -> str:
    """Hora actual naive en America/Mexico_City, formateada como en BD."""
    return datetime.now(ZONA_API).replace(tzinfo=None, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')


def limpiar(medidor_id: str, corte: str, *, ejecutar: bool) -> dict:
    """Borra perfil_carga(medidor_id) con fecha > corte y reajusta sync_state
    al último registro real que se conserva (<= corte)."""
    conn = sqlite3.connect(RUTA_BD_PERFILES)
    conn.row_factory = sqlite3.Row
    try:
        pendiente = conn.execute(
            """
            SELECT COUNT(*) AS n, MIN(fecha) AS mn, MAX(fecha) AS mx
            FROM perfil_carga
            WHERE medidor_id = ? AND fecha > ?
            """,
            (medidor_id, corte),
        ).fetchone()
        previo = conn.execute(
            """
            SELECT MAX(fecha) AS mx
            FROM perfil_carga
            WHERE medidor_id = ? AND fecha <= ?
            """,
            (medidor_id, corte),
        ).fetchone()
        info = {
            'medidor': medidor_id,
            'eliminar': int(pendiente['n'] or 0),
            'rango': (pendiente['mn'], pendiente['mx']),
            'conservar_hasta': previo['mx'] if previo else None,
        }
        if not ejecutar or info['eliminar'] == 0:
            return info

        conn.execute(
            'DELETE FROM perfil_carga WHERE medidor_id = ? AND fecha > ?',
            (medidor_id, corte),
        )
        if info['conservar_hasta']:
            db.actualizar_sync_state(conn, medidor_id, info['conservar_hasta'])
            guardar_ultima_fecha(medidor_id, info['conservar_hasta'])
        else:
            conn.execute('DELETE FROM sync_state WHERE medidor_id = ?', (medidor_id,))
        conn.commit()
        return info
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--medidor',
        action='append',
        help='ID en BD (repita para varios). Default: todos los sincronizados por API/granja.',
    )
    parser.add_argument(
        '--corte',
        help="Hora de corte 'YYYY-MM-DD HH:MM:SS' (default: ahora en America/Mexico_City). "
        'Se borra lo posterior a este valor.',
    )
    parser.add_argument('--ejecutar', action='store_true', help='Aplicar borrado (sin esto solo muestra resumen).')
    args = parser.parse_args(argv)

    corte = args.corte or ahora_local()
    medidores = args.medidor or medidores_api_bd()

    print(f'Corte: {corte} (America/Mexico_City)')
    print(f'Modo: {"EJECUTAR" if args.ejecutar else "dry-run"}')
    print('-' * 60)

    total = 0
    for med in medidores:
        info = limpiar(med, corte, ejecutar=args.ejecutar)
        total += info['eliminar']
        r0, r1 = info['rango']
        rango_txt = f'{r0} .. {r1}' if info['eliminar'] else '-'
        print(
            f"{info['medidor']}: eliminar {info['eliminar']} ({rango_txt}) | "
            f"conservar hasta {info['conservar_hasta'] or '(ninguno)'}"
        )

    print('-' * 60)
    if total == 0:
        print('Sin registros futuros pendientes de limpiar.')
    elif not args.ejecutar:
        print(f'Total a eliminar: {total}. Agregue --ejecutar para borrar de verdad.')
    else:
        print(f'Total eliminado: {total}.')
        print('Sugerido: corra Reportes (o Procesar todo) para regenerar los reportes con el cursor limpio.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
