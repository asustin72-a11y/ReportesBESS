"""Exporta perfiles SQLite a CSV para el pipeline BESS."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.data.ingest.ion import db
from bess.data.ingest.iusasol.gaps import (
    MEDIDORES_RELLENAR_MEDIANOCHE_API,
    contexto_previo_bd,
    filas_a_dataframe,
    persistir_slots_medianoche_bd,
    rellenar_slots_medianoche_api,
)

MEDIDORES_EXPORT = {
    "ION": "ION.csv",
    "BESS": "BESS.csv",
    "ION_IUSA2": "ION_IUSA2.csv",
    "BESS_IUSA2": "BESS_IUSA2.csv",
    "GRANJA_IUSA2": "GRANJA_IUSA2.csv",
    "BANCO": "Banco1.csv",
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
        inicio = desde if ' ' in desde else f'{desde} 00:00:00'
        if medidor_id not in MEDIDORES_RELLENAR_MEDIANOCHE_API and ' ' not in desde:
            inicio = f'{desde} 00:05:00'
        params.append(inicio)
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

    if medidor_id in MEDIDORES_RELLENAR_MEDIANOCHE_API:
        persistir_slots_medianoche_bd(medidor_id, ruta_bd)
        with db.conectar_bd(ruta_bd) as conn:
            filas = conn.execute(query, params).fetchall()
        df = filas_a_dataframe(filas)
        contexto = None
        if desde and filas:
            contexto = contexto_previo_bd(medidor_id, ruta_bd, df['Fecha'].min())
        df = rellenar_slots_medianoche_api(df, contexto_prev=contexto)
        filas_export = df
        usar_df = True
    else:
        filas_export = filas
        usar_df = False

    with salida.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNAS_BESS)
        if usar_df:
            for _, row in filas_export.iterrows():
                fecha = row['Fecha']
                fecha_txt = fecha.strftime('%Y-%m-%d %H:%M:%S') if hasattr(fecha, 'strftime') else str(fecha)
                writer.writerow([
                    fecha_txt,
                    row['KWH_REC'],
                    row['KWH_ENT'],
                    row['KVARH_Q1'],
                    row['KVARH_Q2'],
                    row['KVARH_Q3'],
                    row['KVARH_Q4'],
                ])
        else:
            for row in filas_export:
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
        n = len(filas_export) if usar_df else len(filas)
        print(f'  {medidor_id}: {n} registros -> {salida.name}')
        if usar_df:
            primero = filas_export.iloc[0]['Fecha']
            ultimo = filas_export.iloc[-1]['Fecha']
            n_medianoche = int(
                ((filas_export['Fecha'].dt.hour == 0) & (filas_export['Fecha'].dt.minute == 0)).sum()
            )
            print(f'    Rango: {primero}  a  {ultimo}  ({n_medianoche} slots 00:00)')
        else:
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
    activos = {fila[0] for fila in db.MEDIDORES_CATALOGO if fila[6]}
    for medidor_id, nombre_archivo in MEDIDORES_EXPORT.items():
        if medidor_id not in activos:
            continue
        salida = carpeta / nombre_archivo
        if exportar(ruta_bd, medidor_id, salida, desde, hasta, quiet=quiet) != 0:
            if not quiet:
                print(f'  {medidor_id}: sin registros, export omitido')
    return 0


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
