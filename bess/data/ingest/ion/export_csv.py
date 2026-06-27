"""Exporta perfiles SQLite a CSV para el pipeline BESS."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.data.ingest.ion import db

MEDIDORES_EXPORT = {
    'ION': 'ION.csv',
    'BESS': 'BESS.csv',
    'BANCO': 'Banco1.csv',
}

COLUMNAS_BESS = [
    'Fecha',
    'KWH_REC',
    'KWH_ENT',
    'KVARH_Q1',
    'KVARH_Q2',
    'KVARH_Q3',
    'KVARH_Q4',
]


def exportar(
    ruta_bd: Path,
    medidor_id: str,
    salida: Path,
    desde: str | None = None,
    hasta: str | None = None,
    *,
    quiet: bool = False,
) -> int:
    db.init_db(ruta_bd)
    salida.parent.mkdir(parents=True, exist_ok=True)

    query = """
        SELECT fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4
        FROM perfil_carga
        WHERE medidor_id = ?
    """
    params: list[str] = [medidor_id]

    if desde:
        query += ' AND fecha >= ?'
        params.append(desde if ' ' in desde else f'{desde} 00:05:00')
    if hasta:
        query += ' AND fecha <= ?'
        params.append(hasta if ' ' in hasta else f'{hasta} 23:59:59')

    query += ' ORDER BY fecha'

    with db.conectar_bd(ruta_bd) as conn:
        filas = conn.execute(query, params).fetchall()

    if not filas:
        if not quiet:
            print(f'  {medidor_id}: sin registros para exportar')
        return 1

    with salida.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNAS_BESS)
        for row in filas:
            writer.writerow([
                row['fecha'],
                row['kwh_rec'],
                row['kwh_ent'],
                row['kvarh_q1'],
                row['kvarh_q2'],
                row['kvarh_q3'],
                row['kvarh_q4'],
            ])

    if not quiet:
        print(f'  {medidor_id}: {len(filas)} registros -> {salida.name}')
        print(f'    Rango: {filas[0]["fecha"]}  a  {filas[-1]["fecha"]}')
    return 0


def exportar_todos(
    ruta_bd: Path,
    carpeta: Path,
    desde: str | None,
    hasta: str | None,
    *,
    quiet: bool = False,
) -> int:
    if not quiet:
        print(f'Exportando a {carpeta}')
    errores = 0
    for medidor_id, nombre_archivo in MEDIDORES_EXPORT.items():
        salida = carpeta / nombre_archivo
        if exportar(ruta_bd, medidor_id, salida, desde, hasta, quiet=quiet) != 0:
            errores += 1
    return 1 if errores else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Exportar perfiles SQLite a CSV BESS')
    parser.add_argument('--bd', type=Path, default=db.RUTA_BD_DEFAULT)
    parser.add_argument('--medidor', choices=list(MEDIDORES_EXPORT.keys()))
    parser.add_argument('--destino', choices=['fuente', 'procesados'], default='fuente')
    parser.add_argument('--salida', type=Path)
    parser.add_argument('--desde', help='Filtrar desde YYYY-MM-DD')
    parser.add_argument('--hasta', help='Filtrar hasta YYYY-MM-DD')
    args = parser.parse_args(argv)

    carpeta = DIRECTORIO_FUENTE if args.destino == 'fuente' else DIRECTORIO_PROCESADOS

    if args.medidor:
        nombre = MEDIDORES_EXPORT[args.medidor]
        salida = args.salida or (carpeta / nombre)
        return exportar(args.bd, args.medidor, salida, args.desde, args.hasta)

    return exportar_todos(args.bd, carpeta, args.desde, args.hasta)


if __name__ == '__main__':
    sys.exit(main())
