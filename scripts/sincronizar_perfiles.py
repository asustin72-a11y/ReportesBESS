#!/usr/bin/env python3
"""
Orquesta la actualizacion diaria de perfiles:

  1. ION IUSA 1  -> SQLite (Modbus)
  2. ION IUSA 2  -> SQLite (Modbus)
  3. BESS/BANCO  -> SQLite (API IUSASOL)
  4. Granja IUSA 2 (20 MEGA, API Farm) -> SQLite
  5. SQLite -> CSV en ArchivosFuente
  6. (opcional) Verificar en pipeline BESS

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
from bess.core.ui_progress import emit_ui_progress
from bess.config.paths import DIRECTORIO_FUENTE, RUTA_BD_PERFILES
from bess.config.subestaciones import subestacion_por_id
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
from bess.data.ingest.granja.sync_db import sincronizar_granja_iusa2
from bess.data.sync_resumen import construir_lineas_resumen
from bess.data.sync_validacion import (
    ResultadoValidacionSync,
    aplicar_validacion_post_sync,
    detectar_fallo_sync,
)
from zoneinfo import ZoneInfo

MSG_ION_NO_DISPONIBLE = 'Medidor ION no disponible.'
MSG_ION_IUSA2_NO_DISPONIBLE = 'Medidor ION IUSA 2 no disponible.'

_SYNC_UI_TOTAL = 6


def _sync_ui_progress(args, step: int, label: str) -> None:
    if getattr(args, 'ui_progress', False):
        emit_ui_progress(step, _SYNC_UI_TOTAL, label)


def _parametros_sync_ion(recarga_completa: bool, args, zona: ZoneInfo):
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
        return desde, hasta, True
    return None, None, False


def _ejecutar_sync_ion_modbus(
    *,
    medidor_id: str,
    ip: str,
    puerto: int,
    recarga_completa: bool,
    args,
    zona: ZoneInfo,
    quiet: bool,
) -> tuple[int, dict | None]:
    desde, hasta, reiniciar = _parametros_sync_ion(recarga_completa, args, zona)
    return sincronizar_ion(
        ruta_bd=RUTA_BD_PERFILES,
        modulo_dr=DATA_RECORDER_MODULE,
        num_sources=NUM_SOURCES_DEFAULT,
        zona=zona,
        desde_forzado=desde,
        hasta_forzado=hasta,
        reiniciar=reiniciar,
        ip=ip,
        puerto=puerto,
        medidor_id=medidor_id,
        quiet=quiet,
    )


def _resumen_bd() -> None:
    if not RUTA_BD_PERFILES.is_file():
        print(f'\nBD no encontrada: {RUTA_BD_PERFILES}')
        return

    print(f'\n{"=" * 70}')
    print(f'Resumen BD: {RUTA_BD_PERFILES}')
    print('=' * 70)
    with db.conectar_bd(RUTA_BD_PERFILES) as conn:
        for fila in db.MEDIDORES_CATALOGO:
            medidor_id, nombre, *_resto, activo = fila
            if not activo:
                continue
            total = db.contar_registros(conn, medidor_id)
            row = conn.execute(
                'SELECT MIN(fecha) AS mn, MAX(fecha) AS mx FROM perfil_carga WHERE medidor_id = ?',
                (medidor_id,),
            ).fetchone()
            mn = row['mn'] if row else '-'
            mx = row['mx'] if row else '-'
            print(f'  {medidor_id:<10} {total:>7} registros   {mn}  ->  {mx}  ({nombre})')


def _imprimir_resumen_compacto(
    *,
    ion_stats,
    ion_no_disponible: bool,
    ion_iusa2_stats,
    ion_iusa2_no_disponible: bool,
    api_items: list,
    granja_item: dict | None,
    export_ok: bool,
    validacion=None,
    incluir_ion_iusa2: bool = True,
    incluir_granja: bool = True,
) -> None:
    for linea in construir_lineas_resumen(
        ruta_bd=RUTA_BD_PERFILES,
        ion_stats=ion_stats,
        ion_no_disponible=ion_no_disponible,
        ion_iusa2_stats=ion_iusa2_stats,
        ion_iusa2_no_disponible=ion_iusa2_no_disponible,
        incluir_ion_iusa2=incluir_ion_iusa2,
        api_items=api_items,
        granja_item=granja_item,
        incluir_granja=incluir_granja,
        export_ok=export_ok,
    ):
        print(linea)
    if validacion and validacion.marcados:
        print(f'Validado: {len(validacion.marcados)} medidor(es)')
    if validacion and validacion.pendientes_ion:
        print(f'ION pendiente: {", ".join(validacion.pendientes_ion)}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Sincroniza ION (Modbus) + BESS por subestación (API) hacia ArchivosFuente.',
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
    parser.add_argument('--sin-ion', action='store_true', help='Omitir sync Modbus ION IUSA 1.')
    parser.add_argument('--sin-ion-iusa2', action='store_true', help='Omitir sync Modbus ION IUSA 2.')
    parser.add_argument('--sin-api', action='store_true', help='Omitir sync API (BESS y Banco 1).')
    parser.add_argument('--sin-granja', action='store_true', help='Omitir sync granja IUSA 2 (20 MEGA).')
    parser.add_argument('--sin-export', action='store_true', help='No exportar CSV a ArchivosFuente.')
    parser.add_argument('--solo-export', action='store_true', help='Solo exportar SQLite -> CSV.')
    parser.add_argument('--procesar', action='store_true', help='Verificar, filtrar y generar reportes al final.')
    parser.add_argument('--quiet', action='store_true', help='Salida resumida (sidebar).')
    parser.add_argument(
        '--ui-progress',
        action='store_true',
        help='Eventos de progreso en stderr (barra en la UI Streamlit).',
    )
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
    ion_iusa2_no_disponible = False
    ion_iusa2_stats = None
    api_items: list = []
    granja_item: dict | None = None

    if getattr(args, 'ui_progress', False):
        emit_ui_progress(0, _SYNC_UI_TOTAL, 'Iniciando sincronización…')

    if not args.solo_export:
        if not args.sin_ion:
            _sync_ui_progress(args, 1, 'ION IUSA 1 (Modbus → SQLite)')
            if not args.quiet:
                print(f'\n{"=" * 70}')
                print('1/5 - ION IUSA 1 (Modbus -> SQLite)')
                print('=' * 70)
            try:
                zona = ZoneInfo(ZONA_HORARIA_DEFAULT)
                codigo, ion_stats = _ejecutar_sync_ion_modbus(
                    medidor_id=db.MEDIDOR_ION,
                    ip=args.ip,
                    puerto=args.puerto,
                    recarga_completa=recarga_completa,
                    args=args,
                    zona=zona,
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

        if not args.sin_ion_iusa2:
            _sync_ui_progress(args, 2, 'ION IUSA 2 (Modbus → SQLite)')
            sub_iusa2 = subestacion_por_id('IUSA_2')
            ip_iusa2 = (sub_iusa2.modbus_ip if sub_iusa2 else None) or '172.16.205.203'
            if not args.quiet:
                print(f'\n{"=" * 70}')
                print(f'2/5 - ION IUSA 2 (Modbus {ip_iusa2} -> SQLite)')
                print('=' * 70)
            try:
                zona = ZoneInfo(ZONA_HORARIA_DEFAULT)
                codigo2, ion_iusa2_stats = _ejecutar_sync_ion_modbus(
                    medidor_id=db.MEDIDOR_ION_IUSA2,
                    ip=ip_iusa2,
                    puerto=args.puerto,
                    recarga_completa=recarga_completa,
                    args=args,
                    zona=zona,
                    quiet=args.quiet,
                )
                if codigo2 != 0:
                    ion_iusa2_no_disponible = True
                    if not args.quiet:
                        print(MSG_ION_IUSA2_NO_DISPONIBLE)
                        print('  Se exportara el perfil ION_IUSA2 ya guardado en la base de datos.')
            except Exception as exc:
                ion_iusa2_no_disponible = True
                if not args.quiet:
                    print(MSG_ION_IUSA2_NO_DISPONIBLE)
                    print(f'  Detalle: {exc}', file=sys.stderr)
                    print('  Se exportara el perfil ION_IUSA2 ya guardado en la base de datos.')

        if not args.sin_api:
            _sync_ui_progress(args, 3, 'BESS y medidores (API → SQLite)')
            if not args.quiet:
                print(f'\n{"=" * 70}')
                print('3/5 - BESS + Banco 1 (API IUSASOL -> SQLite)')
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
                            if item.get('mensaje') == 'Sin rango pendiente (BD al día).':
                                ultima = item.get('ultima_bd') or '-'
                                print(
                                    f"  {item['medidor']}: BD al día "
                                    f"(último registro {ultima})"
                                )
                            else:
                                print(
                                    f"  {item['medidor']}: {item['leidos']} leidos "
                                    f"({item['insertados']} nuevos, {item['actualizados']} act.) "
                                    f"{item['desde']} -> {item['hasta']}"
                                )
                fallo_api = detectar_fallo_sync(
                    api_items=api_items,
                    granja_item=None,
                    incluir_api=True,
                    incluir_granja=False,
                )
                if fallo_api:
                    if not args.quiet:
                        print(f'\n{fallo_api}', file=sys.stderr)
                    return 1
            except Exception as exc:
                print(f'ERROR API: {exc}', file=sys.stderr)
                return 1

        if not args.sin_granja:
            _sync_ui_progress(args, 4, 'Granja IUSA 2 (API → SQLite)')
            if not args.quiet:
                print(f'\n{"=" * 70}')
                print('4/5 - Granja IUSA 2 (20 MEGA · API Farm -> SQLite)')
                print('=' * 70)
            try:
                granja_item = sincronizar_granja_iusa2(
                    ruta_bd=RUTA_BD_PERFILES,
                    desde=(args.desde or '2026-05-01') if recarga_completa else None,
                    hasta=hasta_api if recarga_completa else None,
                    quiet=args.quiet,
                )
                if not args.quiet:
                    if 'error' in granja_item:
                        print(f"  GRANJA_IUSA2: ERROR - {granja_item['error']}")
                    else:
                        print(
                            f"  {granja_item['medidor']}: {granja_item['leidos']} intervalos "
                            f"({granja_item['insertados']} nuevos, {granja_item['actualizados']} act.) "
                            f"{granja_item['desde']} -> {granja_item['hasta']} "
                            f"· {granja_item.get('medidores_mega', 20)} MEGA"
                        )
                fallo_granja = detectar_fallo_sync(
                    api_items=[],
                    granja_item=granja_item,
                    incluir_api=False,
                    incluir_granja=True,
                )
                if fallo_granja:
                    if not args.quiet:
                        print(f'\n{fallo_granja}', file=sys.stderr)
                    return 1
            except Exception as exc:
                granja_item = {
                    'medidor': db.MEDIDOR_GRANJA_IUSA2,
                    'error': str(exc),
                }
                if not args.quiet:
                    print(f'ERROR Granja: {exc}', file=sys.stderr)
                return 1

    export_ok = True
    if not args.sin_export:
        _sync_ui_progress(args, 5, 'Exportar perfiles a ArchivosFuente')
        if not args.quiet:
            print(f'\n{"=" * 70}')
            print('5/5 - SQLite -> ArchivosFuente')
            print('=' * 70)
        codigo = exportar_todos(
            RUTA_BD_PERFILES,
            desde=export_desde,
            hasta=export_hasta,
            quiet=args.quiet,
        )
        export_ok = codigo == 0
        if codigo != 0:
            return codigo
        if not args.quiet:
            print(f'\nCSV listos en: {DIRECTORIO_FUENTE}')

    validacion = ResultadoValidacionSync(True, "")
    if not args.sin_export and not args.solo_export:
        _sync_ui_progress(args, 6, 'Validar medidores sincronizados')
        validacion = aplicar_validacion_post_sync(
        ion_no_disponible=ion_no_disponible,
        ion_iusa2_no_disponible=ion_iusa2_no_disponible,
        api_items=api_items,
        granja_item=granja_item,
        export_ok=export_ok and not args.sin_export and not args.solo_export,
        incluir_ion=not args.sin_ion and not args.solo_export,
        incluir_ion_iusa2=not args.sin_ion_iusa2 and not args.solo_export,
        incluir_api=not args.sin_api and not args.solo_export,
        incluir_granja=not args.sin_granja and not args.solo_export,
        )
        if not validacion.exito:
            if not args.quiet:
                print(f'\n{validacion.mensaje}', file=sys.stderr)
            return 1
        if not args.quiet and validacion.marcados:
            print(f'\n{validacion.mensaje}')

    if args.quiet:
        _imprimir_resumen_compacto(
            ion_stats=ion_stats,
            ion_no_disponible=ion_no_disponible,
            ion_iusa2_stats=ion_iusa2_stats,
            ion_iusa2_no_disponible=ion_iusa2_no_disponible,
            api_items=api_items,
            export_ok=export_ok,
            validacion=validacion,
            incluir_ion_iusa2=not args.sin_ion_iusa2,
            granja_item=granja_item,
            incluir_granja=not args.sin_granja,
        )
    else:
        _resumen_bd()
        if not args.procesar:
            print('\nSiguiente paso en la app: Verificar -> Filtrar -> Generar reportes.')
        if ion_no_disponible:
            print(f'\n{MSG_ION_NO_DISPONIBLE}')
        if ion_iusa2_no_disponible:
            print(f'\n{MSG_ION_IUSA2_NO_DISPONIBLE}')

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
        exito, mensajes = reporte_bess()
        if not args.quiet:
            if "_error" in mensajes:
                print(f'ERROR: {mensajes["_error"]}', file=sys.stderr)
            elif exito:
                for prefijo, msg in mensajes.items():
                    if not prefijo.startswith("_"):
                        print(f'OK {prefijo}: {msg}')
            else:
                for prefijo, msg in mensajes.items():
                    if not prefijo.startswith("_"):
                        print(f'PARCIAL {prefijo}: {msg}', file=sys.stderr)
        if not exito:
            return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

