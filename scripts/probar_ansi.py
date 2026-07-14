#!/usr/bin/env python3
"""
Prueba de comunicación ANSI C12.18/C12.19 con medidor ION 8650.

Requiere:
  - Sonda óptica ANSI Type II (IEC) conectada por USB (COMx)
  - Puerto óptico frontal del medidor (COM3)
  - Protocolo COM3 configurado en ION Setup (no Modbus ni ION propietario)

Instalación:
  pip install -r requirements-ansi.txt

Ejemplos:
  python scripts/probar_ansi.py --listar
  python scripts/probar_ansi.py --puerto COM3 --prueba ident
  python scripts/probar_ansi.py --puerto COM3 --baudrate 9600 --prueba info
  python scripts/probar_ansi.py --puerto COM3 --probar-baudios --prueba ident
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BAUDIOS_COMUNES = (9600, 19200, 57600)
STANDARD_LABELS = {
    0: 'ANSI C12.18',
    2: 'ANSI C12.21',
    3: 'ANSI C12.22',
}


def _import_ansi():
    try:
        import serial
        from c1218.connection import Connection
        from c1218.data import C1218IdentRequest, C1218Packet, C1218_RESPONSE_CODES
        from c1218.errors import C1218IOError, C1218NegotiateError, C1218ReadTableError
        from c1219.access.general import C1219GeneralAccess
        from termineter.utilities import get_default_serial_settings
    except ImportError as exc:
        print(
            'Faltan dependencias ANSI. Ejecute:\n'
            '  pip install -r requirements-ansi.txt',
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    return {
        'serial': serial,
        'Connection': Connection,
        'C1218IdentRequest': C1218IdentRequest,
        'C1218Packet': C1218Packet,
        'C1218_RESPONSE_CODES': C1218_RESPONSE_CODES,
        'C1218IOError': C1218IOError,
        'C1218NegotiateError': C1218NegotiateError,
        'C1218ReadTableError': C1218ReadTableError,
        'C1219GeneralAccess': C1219GeneralAccess,
        'get_default_serial_settings': get_default_serial_settings,
    }


def listar_puertos() -> None:
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        print('Instale pyserial: pip install -r requirements-ansi.txt', file=sys.stderr)
        raise SystemExit(1) from exc

    puertos = list(list_ports.comports())
    if not puertos:
        print('No se detectaron puertos serie/USB.')
        return
    print('Puertos serie detectados:')
    for puerto in puertos:
        print(f'  {puerto.device:<8} {puerto.description}')


def _abrir_conexion(ansi, puerto: str, baudrate: int):
    serial_settings = ansi['get_default_serial_settings']()
    serial_settings['baudrate'] = baudrate
    return ansi['Connection'](puerto, serial_settings=serial_settings)


def prueba_identificacion(ansi, puerto: str, baudrate: int) -> bool:
    C1218IdentRequest = ansi['C1218IdentRequest']
    C1218Packet = ansi['C1218Packet']
    C1218_RESPONSE_CODES = ansi['C1218_RESPONSE_CODES']
    C1218IOError = ansi['C1218IOError']
    C1218NegotiateError = ansi['C1218NegotiateError']
    Connection = ansi['Connection']

    print(f'\n--- Identificación ANSI @ {puerto} {baudrate} bps ---')
    conn = None
    try:
        conn = _abrir_conexion(ansi, puerto, baudrate)
        conn.start()
        print('Negociación C12.18: OK')

        conn.send(C1218IdentRequest())
        resp = C1218Packet(conn.recv())
        codigo = resp.data[0] if resp.data else None
        if codigo != 0x00:
            etiqueta = C1218_RESPONSE_CODES.get(codigo, 'desconocido')
            print(f'Respuesta identificación no OK: 0x{codigo:02x} ({etiqueta})')
            return False

        if len(resp.data) < 4:
            print('Respuesta identificación demasiado corta.')
            return False

        standard, ver, rev = resp.data[1:4]
        print(f'Estándar: {STANDARD_LABELS.get(standard, f"0x{standard:02x}")}')
        print(f'Versión: {ver}.{rev}')
        print('Prueba IDENT: OK')
        return True
    except (C1218IOError, C1218NegotiateError, OSError) as exc:
        print(f'Sin respuesta ANSI: {exc}')
        return False
    finally:
        if conn is not None:
            try:
                conn.stop(force=True)
            except Exception:
                pass
            conn.close()


def prueba_info(ansi, puerto: str, baudrate: int, password: str | None) -> bool:
    C1218ReadTableError = ansi['C1218ReadTableError']
    C1218IOError = ansi['C1218IOError']
    C1218NegotiateError = ansi['C1218NegotiateError']
    C1219GeneralAccess = ansi['C1219GeneralAccess']

    print(f'\n--- Información C12.19 @ {puerto} {baudrate} bps ---')
    conn = None
    try:
        conn = _abrir_conexion(ansi, puerto, baudrate)
        conn.start()
        if not conn.login(username='0000', userid=0, password=password):
            print('Login rechazado (usuario 0000 / id 0). Pruebe --password si el medidor lo exige.')
            return False

        general = C1219GeneralAccess(conn)
        print(f'Fabricante: {general.manufacturer}')
        print(f'Modelo: {general.ed_model}')
        print(f'Serie: {general.mfg_serial_no}')
        print(f'Firmware: {general.fw_version_no}.{general.fw_revision_no}')
        print(f'Hardware: {general.hw_version_no}.{general.hw_revision_no}')
        version = {0: 'Pre-release', 1: 'C12.19-1997', 2: 'C12.19-2008'}.get(
            general.std_version_no, 'Desconocida'
        )
        print(f'Versión tablas C12.19: {version}')
        print('Prueba INFO: OK')
        return True
    except C1218ReadTableError as exc:
        print(f'No se pudieron leer tablas C12.19: {exc}')
        return False
    except (C1218IOError, C1218NegotiateError, OSError) as exc:
        print(f'Sin respuesta ANSI: {exc}')
        return False
    finally:
        if conn is not None:
            try:
                conn.stop(force=True)
            except Exception:
                pass
            conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Prueba ANSI C12.18/C12.19 en puerto óptico ION 8650 (COM3 + sonda USB).',
    )
    parser.add_argument('--listar', action='store_true', help='Listar puertos serie/USB')
    parser.add_argument('--puerto', default=None, help='Puerto de la sonda óptica (ej. COM4)')
    parser.add_argument('--baudrate', type=int, default=9600, help='Velocidad serie (default 9600)')
    parser.add_argument(
        '--probar-baudios',
        action='store_true',
        help=f'Probar baudios {BAUDIOS_COMUNES} hasta obtener respuesta',
    )
    parser.add_argument(
        '--prueba',
        choices=('ident', 'info'),
        default='ident',
        help='ident = negociación C12.18; info = tablas C12.19 (requiere login)',
    )
    parser.add_argument('--password', default=None, help='Contraseña ANSI si el medidor la pide')
    args = parser.parse_args()

    ansi = _import_ansi()

    if args.listar:
        listar_puertos()

    if args.puerto is None:
        if args.listar:
            return 0
        parser.error('Indique --puerto (use --listar para ver COM disponibles)')

    baudios = BAUDIOS_COMUNES if args.probar_baudios else (args.baudrate,)
    ok = False
    for baud in baudios:
        if args.prueba == 'info':
            ok = prueba_info(ansi, args.puerto, baud, args.password) or ok
        else:
            ok = prueba_identificacion(ansi, args.puerto, baud) or ok
        if ok and args.probar_baudios:
            print(f'\nBaudrate que respondió: {baud}')
            break

    if not ok:
        print(
            '\nNo hubo respuesta ANSI. Revise:\n'
            '  1. Sonda óptica bien colocada en el puerto frontal del ION\n'
            '  2. COM3 en ION Setup con protocolo ANSI C12.18 (no Modbus/ION)\n'
            '  3. Puerto USB correcto (--listar)\n'
            '  4. Baudrate (--probar-baudios)\n'
            '  Ver docs/PROBAR_ANSI.md',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
