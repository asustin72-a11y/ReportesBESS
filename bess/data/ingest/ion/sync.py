"""Sincroniza perfil ION (Modbus) hacia SQLite."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bess.data.ingest.ion import db
from bess.data.sync_cursor import punto_sync_ion, registrar_exito_sync
from bess.data.ingest.ion.modbus import (
    DATA_RECORDER_MODULE,
    MEDIDOR_IP_DEFAULT,
    NUM_SOURCES_DEFAULT,
    PUERTO_DEFAULT,
    ZONA_HORARIA_DEFAULT,
    conectar,
    formatear_fecha,
    leer_registro_por_numero,
    mapear_sources_bess,
    parse_fecha_arg,
    resolver_rango_descarga,
)

FECHA_INICIO_DEFAULT = '2026-05-01'
LOTE_GUARDADO = 100


def registro_a_dict(valores: list[float], fecha: datetime) -> dict:
    datos = mapear_sources_bess(valores)
    return {
        'fecha': formatear_fecha(fecha),
        'kwh_rec': datos['KWH_REC'],
        'kwh_ent': datos['KWH_ENT'],
        'kvarh_q1': datos['KVARH_Q1'],
        'kvarh_q2': datos['KVARH_Q2'],
        'kvarh_q3': datos['KVARH_Q3'],
        'kvarh_q4': datos['KVARH_Q4'],
    }


def calcular_rango_sync(
    ultima_fecha: datetime | None,
    intervalo_min: int,
    zona: ZoneInfo,
    inicio_forzado: datetime | None,
    fin_forzado: datetime | None,
) -> tuple[datetime, datetime] | None:
    if inicio_forzado:
        desde = inicio_forzado
    elif ultima_fecha is None:
        desde = parse_fecha_arg(FECHA_INICIO_DEFAULT, zona)
    else:
        desde = ultima_fecha + timedelta(minutes=intervalo_min)

    if fin_forzado:
        hasta = fin_forzado
    else:
        hasta = datetime.now(zona).replace(microsecond=0)
        if hasta.second > 0:
            hasta = hasta.replace(second=0)

    if desde > hasta:
        return None
    return desde, hasta


def sincronizar(
    ruta_bd: Path,
    modulo_dr: int,
    num_sources: int,
    zona: ZoneInfo,
    desde_forzado: datetime | None,
    hasta_forzado: datetime | None,
    reiniciar: bool,
    ip: str = MEDIDOR_IP_DEFAULT,
    puerto: int = PUERTO_DEFAULT,
    *,
    medidor_id: str = db.MEDIDOR_ION,
    quiet: bool = False,
) -> tuple[int, dict]:
    stats = {'leidos': 0, 'insertados': 0, 'actualizados': 0, 'ultima': None, 'mensaje': ''}
    db.init_db(ruta_bd)

    desde_efectivo = desde_forzado
    ultima: datetime | None = None
    if desde_efectivo is None:
        cursor = punto_sync_ion(medidor_id, ruta_bd, zona, reiniciar=reiniciar)
        if cursor.desde_forzado is not None:
            desde_efectivo = cursor.desde_forzado
        elif cursor.ultima_incremental is not None:
            ultima = cursor.ultima_incremental
        elif not reiniciar:
            with db.conectar_bd(ruta_bd) as conn:
                ultima = db.get_ultima_fecha(conn, medidor_id, zona)

    with db.conectar_bd(ruta_bd) as conn:
        rango = calcular_rango_sync(ultima, 5, zona, desde_efectivo, hasta_forzado)
        if rango is None:
            if not quiet:
                print('Sin registros nuevos que descargar.')
            stats['mensaje'] = 'al dia'
            return 0, stats

        desde, hasta = rango
        if not quiet:
            print(f'BD: {ruta_bd}')
            print(f'Ultima fecha en BD: {formatear_fecha(ultima) if ultima else "(vacia)"}')
            print(f'Descarga: {formatear_fecha(desde)} -> {formatear_fecha(hasta)}')

        log_id = db.iniciar_sync_log(
            conn,
            medidor_id,
            formatear_fecha(desde),
            formatear_fecha(hasta),
        )
        conn.commit()

    client = conectar(ip, puerto)
    if not client.is_socket_open():
        if not quiet:
            print(f'ERROR: no se pudo conectar a {ip}:{puerto}')
        stats['mensaje'] = 'sin conexion'
        return 1, stats

    leidos = 0
    insertados = 0
    actualizados = 0
    ultima_guardada: str | None = None
    lote: list[dict] = []

    try:
        rango_regs = resolver_rango_descarga(
            client,
            modulo_dr,
            num_sources,
            desde,
            hasta,
            cantidad=None,
            zona=zona,
            como_float=True,
        )
        if rango_regs is None:
            if not quiet:
                print('ERROR: no se pudo resolver rango en el medidor')
            stats['mensaje'] = 'error rango'
            return 1, stats

        inicio, fin, total = rango_regs
        if not quiet:
            print(f'Registros Modbus: #{inicio} .. #{fin} ({total} total)')

        for idx, record_num in enumerate(range(inicio, fin + 1), start=1):
            registro = leer_registro_por_numero(client, record_num, num_sources, zona, True)
            if registro is None:
                continue
            if registro.fecha < desde or registro.fecha > hasta:
                continue

            leidos += 1
            lote.append(registro_a_dict(registro.valores, registro.fecha))
            ultima_guardada = formatear_fecha(registro.fecha)

            if len(lote) >= LOTE_GUARDADO:
                with db.conectar_bd(ruta_bd) as conn:
                    upsert_kwargs = (
                        {'respetar_fuente': 'csv'}
                        if medidor_id == db.MEDIDOR_ION
                        else {}
                    )
                    res = db.upsert_registros(
                        conn, medidor_id, lote, fuente='modbus', **upsert_kwargs
                    )
                    insertados += res.insertados
                    actualizados += res.actualizados
                    conn.commit()
                lote.clear()

            if not quiet and (idx % 100 == 0 or idx == total):
                print(f'  Progreso medidor: {idx}/{total}...')

        if lote:
            with db.conectar_bd(ruta_bd) as conn:
                upsert_kwargs = (
                    {'respetar_fuente': 'csv'}
                    if medidor_id == db.MEDIDOR_ION
                    else {}
                )
                res = db.upsert_registros(
                    conn, medidor_id, lote, fuente='modbus', **upsert_kwargs
                )
                insertados += res.insertados
                actualizados += res.actualizados
                conn.commit()

        with db.conectar_bd(ruta_bd) as conn:
            if ultima_guardada:
                db.actualizar_sync_state(conn, medidor_id, ultima_guardada)
            db.cerrar_sync_log(conn, log_id, 'ok', leidos, insertados, actualizados)
            conn.commit()

        if leidos > 0:
            registrar_exito_sync(medidor_id, ruta_bd)

        stats.update(
            leidos=leidos,
            insertados=insertados,
            actualizados=actualizados,
            ultima=ultima_guardada,
            mensaje='ok' if leidos else 'sin datos',
        )
        if not quiet:
            if leidos == 0:
                print('No se encontraron registros en el rango solicitado.')
            else:
                print(f'Leidos: {leidos} | Nuevos: {insertados} | Actualizados: {actualizados}')
                print(f'Ultima fecha guardada: {ultima_guardada}')
        return 0, stats

    except Exception as exc:
        with db.conectar_bd(ruta_bd) as conn:
            db.cerrar_sync_log(conn, log_id, 'error', leidos, insertados, actualizados, str(exc))
            conn.commit()
        stats.update(leidos=leidos, insertados=insertados, actualizados=actualizados, mensaje=str(exc))
        raise
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Sincronizar perfil ION a SQLite')
    parser.add_argument('--bd', type=Path, default=db.RUTA_BD_DEFAULT, help='Ruta SQLite')
    parser.add_argument('--init', action='store_true', help='Solo crear/inicializar la BD')
    parser.add_argument('--modulo-dr', type=int, default=DATA_RECORDER_MODULE)
    parser.add_argument('--sources', type=int, default=NUM_SOURCES_DEFAULT)
    parser.add_argument('--desde', help='Forzar fecha inicio (YYYY-MM-DD)')
    parser.add_argument('--hasta', help='Forzar fecha fin (YYYY-MM-DD)')
    parser.add_argument('--reiniciar', action='store_true', help='Ignorar ultima_fecha en BD')
    parser.add_argument('--tz', default=ZONA_HORARIA_DEFAULT)
    parser.add_argument('--ip', default=MEDIDOR_IP_DEFAULT)
    parser.add_argument('--puerto', type=int, default=PUERTO_DEFAULT)
    args = parser.parse_args(argv)

    ruta = db.init_db(args.bd)
    if args.init:
        print(f'Base de datos inicializada: {ruta}')
        return 0

    try:
        zona = ZoneInfo(args.tz)
        desde = parse_fecha_arg(args.desde, zona) if args.desde else None
        hasta = parse_fecha_arg(args.hasta, zona, es_hasta=True) if args.hasta else None
    except ValueError as exc:
        print(f'ERROR: {exc}')
        return 1

    print(f'Conectando a medidor {args.ip}:{args.puerto} ...')
    codigo, _ = sincronizar(
        ruta_bd=ruta,
        modulo_dr=args.modulo_dr,
        num_sources=args.sources,
        zona=zona,
        desde_forzado=desde,
        hasta_forzado=hasta,
        reiniciar=args.reiniciar,
        ip=args.ip,
        puerto=args.puerto,
    )
    return codigo


if __name__ == '__main__':
    sys.exit(main())
