"""Importa CSV de perfil a SQLite."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

from bess.core.dates import validar_y_convertir_fecha
from bess.data.ingest.ion import db
from bess.data.ingest.medidor_ids import ids_medidores_perfil_bd
from bess.data.sync_cursor import registrar_exito_sync

MEDIDOR_BESS = db.MEDIDOR_BESS
MEDIDOR_BANCO = db.MEDIDOR_BANCO
LOTE = 500
PRIMER_INTERVALO = (0, 5)

MEDIDORES_IMPORTABLES = tuple(ids_medidores_perfil_bd())


def _es_ion_facturacion(medidor_id: str) -> bool:
    return medidor_id in (db.MEDIDOR_ION, db.MEDIDOR_ION_IUSA2)


def _parse_fecha(texto: str) -> datetime:
    normalizada = validar_y_convertir_fecha(texto)
    try:
        return datetime.strptime(normalizada, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError(f"Fecha invalida: {texto!r}") from exc


def _leer_valor(fila: dict[str, str], *claves: str) -> float:
    for clave in claves:
        val = fila.get(clave)
        if val not in (None, ''):
            return float(val)
    return 0.0


def _normalizar_kwh_ion(kwh_rec: float, kwh_ent: float) -> tuple[float, float]:
    if kwh_rec == 0 and kwh_ent > 0:
        return kwh_ent, kwh_rec
    return kwh_rec, kwh_ent


def _fila_a_registro(encabezados: list[str], valores: list[str], medidor_id: str) -> dict | None:
    fila = {
        encabezados[i].strip().lower(): valores[i].strip()
        for i in range(min(len(encabezados), len(valores)))
    }
    fecha_txt = fila.get('fecha', '')
    if not fecha_txt:
        return None

    fecha_dt = _parse_fecha(fecha_txt)

    kwh_rec = _leer_valor(fila, 'kwh_rec')
    kwh_ent = _leer_valor(fila, 'kwh_ent')
    # Solo IUSA 1: CSV legacy con REC/ENT invertidos. ION_IUSA2 conserva columnas del medidor.
    if medidor_id == db.MEDIDOR_ION:
        kwh_rec, kwh_ent = _normalizar_kwh_ion(kwh_rec, kwh_ent)

    return {
        'fecha': fecha_dt.strftime("%Y-%m-%d %H:%M:%S"),
        'fecha_dt': fecha_dt,
        'kwh_rec': kwh_rec,
        'kwh_ent': kwh_ent,
        'kvarh_q1': _leer_valor(fila, 'kvarh_q1'),
        'kvarh_q2': _leer_valor(fila, 'kvarh_q2'),
        'kvarh_q3': _leer_valor(fila, 'kvarh_q3'),
        'kvarh_q4': _leer_valor(fila, 'kvarh_q4'),
    }


def filtrar_primer_registro_dia(registros: list[dict]) -> tuple[list[dict], int]:
    registros.sort(key=lambda r: r['fecha_dt'])
    vistos_dia: set[str] = set()
    validos: list[dict] = []
    omitidos = 0

    for reg in registros:
        dia = reg['fecha_dt'].date().isoformat()
        if dia not in vistos_dia:
            vistos_dia.add(dia)
            hora, minuto = reg['fecha_dt'].hour, reg['fecha_dt'].minute
            if (hora, minuto) != PRIMER_INTERVALO:
                omitidos += 1
                continue

        validos.append({
            'fecha': reg['fecha'],
            'kwh_rec': reg['kwh_rec'],
            'kwh_ent': reg['kwh_ent'],
            'kvarh_q1': reg['kvarh_q1'],
            'kvarh_q2': reg['kvarh_q2'],
            'kvarh_q3': reg['kvarh_q3'],
            'kvarh_q4': reg['kvarh_q4'],
        })

    return validos, omitidos


def importar_csv(
    ruta_csv: Path,
    ruta_bd: Path,
    medidor_id: str = db.MEDIDOR_ION,
    solo_faltantes: bool = False,
    sin_filtro_dia: bool = False,
) -> int:
    if not ruta_csv.exists():
        print(f'ERROR: no existe {ruta_csv}')
        return 1

    db.init_db(ruta_bd)
    print(f'Leyendo {ruta_csv} ...')

    todos: list[dict] = []
    with ruta_csv.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        encabezados = next(reader, None)
        if not encabezados:
            print('ERROR: CSV vacio')
            return 1

        for fila in reader:
            if not fila or not any(c.strip() for c in fila):
                continue
            reg = _fila_a_registro(encabezados, fila, medidor_id)
            if reg:
                todos.append(reg)

    print(f'Filas leidas en CSV: {len(todos)}')

    if solo_faltantes:
        with db.conectar_bd(ruta_bd) as conn:
            existentes = {
                row['fecha']
                for row in conn.execute(
                    'SELECT fecha FROM perfil_carga WHERE medidor_id = ?',
                    (medidor_id,),
                )
            }
        antes = len(todos)
        todos = [r for r in todos if r['fecha'] not in existentes]
        print(f'Solo faltantes en BD: {len(todos)} (omitidos ya presentes: {antes - len(todos)})')
        if not todos:
            print('BD ya contiene todos los timestamps del CSV.')
            return 0

    if sin_filtro_dia or medidor_id in (db.MEDIDOR_ION_IUSA2, MEDIDOR_BANCO):
        validos = [
            {
                'fecha': reg['fecha'],
                'kwh_rec': reg['kwh_rec'],
                'kwh_ent': reg['kwh_ent'],
                'kvarh_q1': reg['kvarh_q1'],
                'kvarh_q2': reg['kvarh_q2'],
                'kvarh_q3': reg['kvarh_q3'],
                'kvarh_q4': reg['kvarh_q4'],
            }
            for reg in sorted(todos, key=lambda r: r['fecha_dt'])
        ]
        omitidos = 0
        if medidor_id == db.MEDIDOR_ION_IUSA2:
            print('ION_IUSA2: perfil a BD sin filtrar (tal cual del medidor)')
        elif medidor_id == MEDIDOR_BANCO:
            print('BANCO: perfil a BD sin filtrar (conserva slots 00:00)')
    else:
        validos, omitidos = filtrar_primer_registro_dia(todos)
    if medidor_id not in (db.MEDIDOR_ION_IUSA2, MEDIDOR_BANCO):
        print(f'Omitidos (1er registro del dia != 00:05): {omitidos}')
    print(f'Registros a guardar: {len(validos)}')

    if not validos:
        print('ERROR: no quedaron registros tras filtrar')
        return 1

    insertados = 0
    actualizados = 0
    for i in range(0, len(validos), LOTE):
        lote = validos[i:i + LOTE]
        with db.conectar_bd(ruta_bd) as conn:
            res = db.upsert_registros(conn, medidor_id, lote, fuente='csv')
            insertados += res.insertados
            actualizados += res.actualizados
            conn.commit()
        print(f'  Guardados {min(i + LOTE, len(validos))}/{len(validos)}...')

    with db.conectar_bd(ruta_bd) as conn:
        total_bd = db.contar_registros(conn, medidor_id)

    # Alinea sync_state + Ultima_Sincronizacion.csv con MAX(fecha) en BD.
    # Las filas quedan con fuente='csv'; el sync API las protege con
    # respetar_fuente='csv' (no pisa energía real aunque traiga el día completo).
    cursor = registrar_exito_sync(medidor_id, ruta_bd)
    if cursor:
        print(f'Cursor sync alineado: {cursor}')

    print(f'Medidor: {medidor_id} | Nuevos: {insertados} | Actualizados: {actualizados} | Total BD: {total_bd}')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Importar CSV de perfil a SQLite')
    parser.add_argument('csv', type=Path, help='Ruta al CSV')
    parser.add_argument(
        "--medidor",
        required=True,
        choices=ids_medidores_perfil_bd(),
    )
    parser.add_argument('--bd', type=Path, default=db.RUTA_BD_DEFAULT)
    parser.add_argument(
        '--solo-faltantes',
        action='store_true',
        help='Insertar solo timestamps que no existen en BD (no actualiza existentes).',
    )
    parser.add_argument(
        '--sin-filtro-dia',
        action='store_true',
        help='No omitir primer registro del dia si no es 00:05 (util para backfill ION).',
    )
    args = parser.parse_args(argv)
    return importar_csv(
        args.csv,
        args.bd,
        args.medidor,
        solo_faltantes=args.solo_faltantes,
        sin_filtro_dia=args.sin_filtro_dia,
    )


if __name__ == '__main__':
    sys.exit(main())
