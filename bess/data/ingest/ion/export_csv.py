"""Exporta perfiles SQLite a CSV para el pipeline BESS."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

# La API ISOL (y en general cualquier fuente que rellene el dia completo con
# ceros desde temprano) puede seguir actualizando SQLite con valores reales
# para fechas que ya se exportaron antes en este mismo dia (ver
# bess/data/ingest/iusasol/sync_db.py: DIAS_SOLAPAMIENTO_API). Si el cursor
# incremental de aqui solo mirara "fecha > cursor", esas actualizaciones se
# quedarian encerradas en SQLite para siempre -- el CSV ya exportado nunca
# se volveria a tocar. Por eso el modo incremental no anexa estrictamente lo
# nuevo: siempre vuelve a pedir y sobrescribir una ventana de los ultimos
# `_MARGEN_REEXPORTAR_DIAS` dias (el mismo margen que usa el sync de la API),
# conservando intacto todo lo anterior a esa ventana.
_MARGEN_REEXPORTAR_DIAS = 1

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.data.ingest.ion import db
from bess.data.ingest.iusasol.gaps import (
    contexto_previo_bd,
    filas_a_dataframe,
    medidor_rellena_medianoche_api,
    persistir_slots_medianoche_bd,
    rellenar_slots_medianoche_api,
)
from bess.data.ingest.medidor_ids import destinos_export_bd, medidor_id_canonico

COLUMNAS_BESS = [
    'Fecha',
    'KWH_REC',
    'KWH_ENT',
    'KVARH_Q1',
    'KVARH_Q2',
    'KVARH_Q3',
    'KVARH_Q4',
]


def _cursor_exportado(salida: Path) -> str | None:
    """Última Fecha ya exportada en `salida`, o None si no existe/está vacío
    o no tiene una columna Fecha legible.

    exportar() siempre escribe ordenado por fecha ascendente (la consulta
    SQL trae `ORDER BY fecha`), así que basta con el máximo de la columna.
    """
    if not salida.exists():
        return None
    try:
        fechas = pd.read_csv(salida, usecols=['Fecha'], encoding='utf-8-sig')['Fecha']
    except (ValueError, KeyError):
        return None
    fechas = fechas.dropna()
    if fechas.empty:
        return None
    return str(fechas.max())


def _inicio_ventana_reexportar(cursor: str) -> str:
    """Inicio (00:00:00) del día `_MARGEN_REEXPORTAR_DIAS` días antes del
    día del cursor -- la ventana que se vuelve a pedir y sobrescribir en
    cada corrida incremental, para recoger actualizaciones del mismo día."""
    dia_cursor = pd.Timestamp(cursor).normalize()
    inicio = dia_cursor - pd.Timedelta(days=_MARGEN_REEXPORTAR_DIAS)
    return inicio.strftime('%Y-%m-%d %H:%M:%S')


def _filas_previas_a_ventana(salida: Path, inicio_ventana: str) -> list[str]:
    """Líneas crudas (con salto de línea) de `salida` cuya Fecha es anterior
    a `inicio_ventana`, tal cual estaban escritas -- se conservan sin
    reprocesar para no arriesgar diferencias de formato en filas ya
    cerradas. Devuelve [] si el archivo no existe o no tiene columna Fecha."""
    if not salida.exists():
        return []
    with salida.open('r', newline='', encoding='utf-8-sig') as f:
        lector = csv.reader(f)
        encabezado = next(lector, None)
        if not encabezado or encabezado[0] != 'Fecha':
            return []
        conservadas: list[list[str]] = []
        for fila in lector:
            if not fila:
                continue
            if fila[0] < inicio_ventana:
                conservadas.append(fila)
    return conservadas


def exportar(
    ruta_bd: Path,
    medidor_id: str,
    salida: Path,
    desde: str | None = None,
    hasta: str | None = None,
    *,
    quiet: bool = False,
) -> int:
    """Exporta perfil_carga -> CSV.

    Incremental: si no se piden `desde`/`hasta` explícitos y ya existe un
    CSV exportado para este medidor, se consulta desde el inicio de una
    ventana de `_MARGEN_REEXPORTAR_DIAS` días antes del cursor (última
    Fecha ya exportada) en adelante -- no solo filas estrictamente nuevas
    -- y esa ventana reemplaza lo que hubiera en el archivo para esas
    fechas; todo lo anterior a la ventana se conserva tal cual. Esto
    recoge actualizaciones que la fuente (típicamente la API ISOL, que
    rellena el día completo con ceros desde temprano y lo va completando
    con valores reales conforme pasan las horas) escribe en SQLite para
    fechas que ya se habían exportado antes. Un `desde` o `hasta` explícito
    (re-exportar un rango puntual, p.ej. para reparar datos) sigue
    sobrescribiendo el archivo completo como antes.
    """
    medidor_id = medidor_id_canonico(medidor_id)
    db.init_db(ruta_bd)
    salida.parent.mkdir(parents=True, exist_ok=True)

    cursor = None
    inicio_ventana = None
    if desde is None and hasta is None:
        cursor = _cursor_exportado(salida)
        if cursor is not None:
            inicio_ventana = _inicio_ventana_reexportar(cursor)

    query = """
        SELECT fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4
        FROM perfil_carga
        WHERE medidor_id = ?
    """
    params: list[str] = [medidor_id]

    if inicio_ventana is not None:
        query += ' AND fecha >= ?'
        params.append(inicio_ventana)
    else:
        if desde:
            query += ' AND fecha >= ?'
            inicio = desde if ' ' in desde else f'{desde} 00:00:00'
            if not medidor_rellena_medianoche_api(medidor_id) and ' ' not in desde:
                inicio = f'{desde} 00:05:00'
            params.append(inicio)
        if hasta:
            query += ' AND fecha <= ?'
            params.append(hasta if ' ' in hasta else f'{hasta} 23:59:59')

    query += ' ORDER BY fecha'

    with db.conectar_bd(ruta_bd) as conn:
        filas = conn.execute(query, params).fetchall()

    if not filas:
        if cursor is not None:
            if not quiet:
                print(f'  {medidor_id}: sin registros nuevos desde la última exportación')
            return 0
        if not quiet:
            print(f'  {medidor_id}: sin registros para exportar')
        return 1

    if medidor_rellena_medianoche_api(medidor_id):
        persistir_slots_medianoche_bd(medidor_id, ruta_bd)
        with db.conectar_bd(ruta_bd) as conn:
            filas = conn.execute(query, params).fetchall()
        df = filas_a_dataframe(filas)
        contexto = None
        if (desde or inicio_ventana) and filas:
            contexto = contexto_previo_bd(medidor_id, ruta_bd, df['Fecha'].min())
        df = rellenar_slots_medianoche_api(df, contexto_prev=contexto)
        filas_export = df
        usar_df = True
    else:
        filas_export = filas
        usar_df = False

    filas_previas: list[list[str]] = []
    if inicio_ventana is not None:
        filas_previas = _filas_previas_a_ventana(salida, inicio_ventana)

    modo = 'w' if (cursor is None or inicio_ventana is not None) else 'a'
    escribir_encabezado = modo == 'w'

    with salida.open(modo, newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if escribir_encabezado:
            writer.writerow(COLUMNAS_BESS)
        for fila in filas_previas:
            writer.writerow(fila)
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
        if inicio_ventana is not None:
            etiqueta = f'en ventana desde {inicio_ventana} (reemplazada)'
        elif cursor is not None:
            etiqueta = 'nuevo(s) anexado(s)'
        else:
            etiqueta = 'registros'
        print(f'  {medidor_id}: {n} {etiqueta} -> {salida}')
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
    desde: str | None = None,
    hasta: str | None = None,
    *,
    quiet: bool = False,
) -> int:
    destinos = destinos_export_bd(ruta_bd)
    if not quiet:
        print(f'Exportando {len(destinos)} perfiles desde {ruta_bd}')
    codigo = 0
    for medidor_id, salida in destinos:
        if exportar(ruta_bd, medidor_id, salida, desde, hasta, quiet=quiet) != 0:
            if not quiet:
                print(f'  {medidor_id}: sin registros, export omitido')
            codigo = 1
    return codigo


def _medidores_export_choices() -> list[str]:
    return [medidor_id for medidor_id, _ in destinos_export_bd()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Exportar perfiles SQLite a CSV BESS')
    parser.add_argument('--bd', type=Path, default=db.RUTA_BD_DEFAULT)
    parser.add_argument('--medidor', choices=_medidores_export_choices())
    parser.add_argument('--destino', choices=['fuente', 'procesados'], default='fuente')
    parser.add_argument('--salida', type=Path)
    parser.add_argument('--desde', help='Filtrar desde YYYY-MM-DD')
    parser.add_argument('--hasta', help='Filtrar hasta YYYY-MM-DD')
    args = parser.parse_args(argv)

    if args.medidor:
        if args.salida:
            salida = args.salida
        else:
            destinos = dict(destinos_export_bd())
            salida = destinos.get(args.medidor)
            if salida is None:
                carpeta = DIRECTORIO_FUENTE if args.destino == 'fuente' else DIRECTORIO_PROCESADOS
                salida = carpeta / f'{args.medidor}.csv'
        return exportar(args.bd, args.medidor, salida, args.desde, args.hasta)

    return exportar_todos(args.bd, args.desde, args.hasta)


if __name__ == '__main__':
    sys.exit(main())
