#!/usr/bin/env python3
"""
Orquesta la actualizacion diaria de perfiles:

  1. ION  -> SQLite   (Modbus)
  2. BESS/BANCO -> SQLite (API IUSASOL)
  3. SQLite -> CSV en ArchivosFuente
  4. (opcional) Verificar en pipeline BESS

Uso habitual:
  python scripts/sincronizar_perfiles.py
  python scripts/sincronizar_perfiles.py --quiet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.core.console import log as print
from bess.config.paths import DIRECTORIO_FUENTE, RUTA_BD_PERFILES
from bess.data.ingest.ion import db
from bess.data.ingest.ion.export_csv import exportar_todos
from bess.data.ingest.ion.sync import sincronizar as sincronizar_ion
from bess.data.ingest.ion.modbus import (
    DATA_RECORDER_MODULE,
    MEDIDOR_IP_DEFAULT,
    NUM_SOURCES_DEFAULT,
    PUERTO_DEFAULT,
    ZONA_HORARIA_DEFAULT,
    parse_fecha_arg,
)
from bess.data.ingest.iusasol.sync_db import fecha_fin_api, sincronizar_api
from bess.data.sync_resumen import construir_lineas_resumen
from zoneinfo import ZoneInfo

MSG_ION_NO_DISPONIBLE = 'Medidor ION no disponible.'


def _resumen_bd() -> None:
    if not RUTA_BD_PERFILES.is_file():
        print(f'\nBD no encontrada: {RUTA_BD_PERFILES}')
        return

    print(f'\n{"=" * 70}')
    print(f'Resumen BD: {RUTA_BD_PERFILES}')
    print('=' * 70)
    with db.conectar_bd(RUTA_BD_PERFILES) as conn:
        for medidor in ('ION', 'BESS', 'BANCO'):
            total = db.contar_registros(conn, medidor)
            row = conn.execute(
                'SELECT MIN(fecha) AS mn, MAX(fecha) AS mx FROM perfil_carga WHERE medidor_id = ?',
                (medidor,),
            ).fetchone()
            mn = row['mn'] if row else '-'
            mx = row['mx'] if row else '-'
            print(f'  {medidor:<6} {total:>7} registros   {mn}  ->  {mx}')


def _imprimir_resumen_compacto(
    *,
    ion_stats,
    ion_no_disponible: bool,
    api_items: list,
    export_ok: bool,
) -> None:
    for linea in construir_lineas_resumen(
        ruta_bd=RUTA_BD_PERFILES,
        ion_stats=ion_stats,
        ion_no_disponible=ion_no_disponible,
        api_items=api_items,
        export_ok=export_ok,
    ):
        print(linea)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Sincroniza ION + BESS + BANCO hacia ArchivosFuente.',
    )
    parser.add_argument('--desde', help='Forzar inicio YYYY-MM-DD o YYYY-MM-DD HH:MM:SS.')
    parser.add_argument(
        '--hasta',
        help='Forzar fin YYYY-MM-DD (default API: hoy). Omita en ION para traer hasta ahora en el medidor.',
    )
    parser.add_argument(
        '--vaciar',
        action='store_true',
        help='Borrar todos los perfiles en BD antes de sincronizar.',
    )
    parser.add_argument('--init-bd', action='store_true', help='Solo crear/inicializar SQLite.')
    parser.add_argument('--sin-ion', action='store_true', help='Omitir sync Modbus ION.')
    parser.add_argument('--sin-api', action='store_true', help='Omitir sync API BESS/BANCO.')
    parser.add_argument('--sin-export', action='store_true', help='No exportar CSV a ArchivosFuente.')
    parser.add_argument('--solo-export', action='store_true', help='Solo exportar SQLite -> CSV.')
    parser.add_argument('--procesar', action='store_true', help='Verificar, filtrar y generar reportes al final.')
    parser.add_argument('--quiet', action='store_true', help='Salida resumida (sidebar).')
    parser.add_argument('--ip', default=MEDIDOR_IP_DEFAULT)
    parser.add_argument('--puerto', type=int, default=PUERTO_DEFAULT)
    args = parser.parse_args(argv)

    RUTA_BD_PERFILES.parent.mkdir(parents=True, exist_ok=True)

    if args.init_bd:
        ruta = db.init_db(RUTA_BD_PERFILES)
        print(f'Base de datos inicializada: {ruta}')
        return 0

    if args.vaciar:
        n = db.vaciar_perfiles(RUTA_BD_PERFILES)
        print(f'BD vaciada: {n} registros eliminados de perfil_carga.')

    recarga_completa = args.vaciar or bool(args.desde)
    fin_api = fecha_fin_api()
    hasta_api = args.hasta or fin_api
    export_desde = args.desde if recarga_completa and args.desde else None
    export_hasta = args.hasta if recarga_completa and args.hasta else None
    ion_no_disponible = False
    ion_stats = None
    api_items: list = []

    if not args.solo_export:
        if not args.sin_ion:
            if not args.quiet:
                print(f'\n{"=" * 70}')
                print('1/3 - ION (Modbus -> SQLite)')
                print('=' * 70)
            try:
                zona = ZoneInfo(ZONA_HORARIA_DEFAULT)
                if recarga_completa:
                    desde_txt = args.desde or '2026-05-01'
                    if ' ' in desde_txt:
                        desde = parse_fecha_arg(desde_txt, zona)
                    else:
                        desde = parse_fecha_arg(f'{desde_txt} 00:05:00', zona)
                    hasta = (
                        parse_fecha_arg(args.hasta, zona, es_hasta=True)
                        if args.hasta
                        else None
                    )
                    reiniciar = True
                else:
                    desde = None
                    hasta = None
                    reiniciar = False
                codigo, ion_stats = sincronizar_ion(
                    ruta_bd=RUTA_BD_PERFILES,
                    modulo_dr=DATA_RECORDER_MODULE,
                    num_sources=NUM_SOURCES_DEFAULT,
                    zona=zona,
                    desde_forzado=desde,
                    hasta_forzado=hasta,
                    reiniciar=reiniciar,
                    ip=args.ip,
                    puerto=args.puerto,
                    quiet=args.quiet,
                )
                if codigo != 0:
                    ion_no_disponible = True
                    if not args.quiet:
                        print(MSG_ION_NO_DISPONIBLE)
                        print('  Se exportara el perfil ION ya guardado en la base de datos.')
            except Exception as exc:
                ion_no_disponible = True
                if not args.quiet:
                    print(MSG_ION_NO_DISPONIBLE)
                    print(f'  Detalle: {exc}', file=sys.stderr)
                    print('  Se exportara el perfil ION ya guardado en la base de datos.')

        if not args.sin_api:
            if not args.quiet:
                print(f'\n{"=" * 70}')
                print('2/3 - BESS + BANCO (API IUSASOL -> SQLite)')
                print('=' * 70)
            try:
                api_items = sincronizar_api(
                    ruta_bd=RUTA_BD_PERFILES,
                    desde=(args.desde or '2026-05-01') if recarga_completa else None,
                    hasta=hasta_api if recarga_completa else None,
                    quiet=args.quiet,
                )
                if not args.quiet:
                    for item in api_items:
                        if 'error' in item:
                            print(f"  {item['medidor']}: ERROR - {item['error']}")
                        else:
                            print(
                                f"  {item['medidor']}: {item['leidos']} leidos "
                                f"({item['insertados']} nuevos, {item['actualizados']} act.) "
                                f"{item['desde']} -> {item['hasta']}"
                            )
            except Exception as exc:
                print(f'ERROR API: {exc}', file=sys.stderr)
                return 1

    export_ok = True
    if not args.sin_export:
        if not args.quiet:
            print(f'\n{"=" * 70}')
            print('3/3 - SQLite -> ArchivosFuente')
            print('=' * 70)
        codigo = exportar_todos(
            RUTA_BD_PERFILES,
            DIRECTORIO_FUENTE,
            export_desde,
            export_hasta,
            quiet=args.quiet,
        )
        export_ok = codigo == 0
        if codigo != 0:
            return codigo
        if not args.quiet:
            print(f'\nCSV listos en: {DIRECTORIO_FUENTE}')

    if args.quiet:
        _imprimir_resumen_compacto(
            ion_stats=ion_stats,
            ion_no_disponible=ion_no_disponible,
            api_items=api_items,
            export_ok=export_ok,
        )
    else:
        _resumen_bd()
        if not args.procesar:
            print('\nSiguiente paso en la app: Verificar -> Filtrar -> Generar reportes.')
        if ion_no_disponible:
            print(f'\n{MSG_ION_NO_DISPONIBLE}')

    if args.procesar:
        if not args.quiet:
            print(f'\n{"=" * 70}')
            print('Verificar archivos fuente')
            print('=' * 70)
        from bess_core import verificar_datos_fuente

        exito, mensaje = verificar_datos_fuente()
        if not args.quiet:
            print(f'OK: {mensaje}' if exito else f'ERROR: {mensaje}')
        if not exito:
            return 1

    if args.procesar:
        from bess_core import filtrar_datos, reporte_bess

        if not args.quiet:
            print(f'\n{"=" * 70}')
            print('Filtrar archivos')
            print('=' * 70)
        exito, mensaje = filtrar_datos()
        if not exito:
            if not args.quiet:
                print(f'ERROR: {mensaje}', file=sys.stderr)
            return 1
        if not args.quiet:
            print(f'OK: {mensaje}')

        if not args.quiet:
            print(f'\n{"=" * 70}')
            print('Generar reportes')
            print('=' * 70)
        exito, msg_ion, msg_banco = reporte_bess()
        if not args.quiet:
            if exito:
                print(f'OK ION: {msg_ion}')
                print(f'OK BANCO: {msg_banco}')
            else:
                print(f'PARCIAL ION: {msg_ion}', file=sys.stderr)
                print(f'PARCIAL BANCO: {msg_banco}', file=sys.stderr)
        if not exito:
            return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
