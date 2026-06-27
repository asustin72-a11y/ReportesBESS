"""Corrección legacy KWH_REC/KWH_ENT en ION (datos antiguos)."""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

from bess.data.ingest.ion import db


def main(argv: list[str] | None = None) -> int:
    warnings.warn(
        'fix_kwh es legacy: descarga y sync ya mapean KWH_REC correctamente.',
        DeprecationWarning,
        stacklevel=1,
    )
    parser = argparse.ArgumentParser(description='[LEGACY] Intercambiar KWH_REC/KWH_ENT de ION')
    parser.add_argument('--bd', type=Path, default=db.RUTA_BD_DEFAULT)
    parser.add_argument('--confirmar', action='store_true')
    args = parser.parse_args(argv)

    db.init_db(args.bd)
    with db.conectar_bd(args.bd) as conn:
        total = db.contar_registros(conn, db.MEDIDOR_ION)
        muestra = conn.execute(
            """
            SELECT fecha, kwh_rec, kwh_ent
            FROM perfil_carga
            WHERE medidor_id = ?
            ORDER BY fecha
            LIMIT 3
            """,
            (db.MEDIDOR_ION,),
        ).fetchall()

    print(f'Registros ION en BD: {total}')
    for row in muestra:
        print(f"  {row['fecha']}  REC={row['kwh_rec']}  ENT={row['kwh_ent']}")

    if muestra and muestra[0]['kwh_rec'] > 0 and muestra[0]['kwh_ent'] == 0:
        print('Los datos ya tienen energia en KWH_REC. No es necesario corregir.')
        return 0

    if not args.confirmar:
        print('Use --confirmar solo si REC=0 y ENT>0 (datos del mapeo antiguo).')
        return 0

    with db.conectar_bd(args.bd) as conn:
        n = db.intercambiar_kwh_medidor(conn, db.MEDIDOR_ION)
        conn.commit()
    print(f'Corregidos: {n} registros')
    return 0


if __name__ == '__main__':
    sys.exit(main())
