#!/usr/bin/env python3
"""Diagnóstico de conectividad para sync BESS (ION / API ISOL / Granja).

Útil cuando hay afectación de red: prueba cada origen por separado y reporta
qué responde (y qué vería la UI en un sync).

Ejemplos (Windows):

  cd C:\\Proyectos_IUSASOL\\ReporteadorIUSASOL
  .\\.venv\\Scripts\\Activate.ps1
  python scripts/diagnosticar_conectividad_sync.py

  python scripts/diagnosticar_conectividad_sync.py --sin-ion
  python scripts/diagnosticar_conectividad_sync.py --solo-api
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ok(msg: str) -> None:
    print(f'  OK   {msg}')


def _fail(msg: str) -> None:
    print(f'  FAIL {msg}')


def _probar_tcp(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f'{host}:{port} abierto ({(time.time() - t0) * 1000:.0f} ms)'
    except OSError as exc:
        return False, f'{host}:{port} — {exc}'


def _probar_ion(sin_ion: bool) -> bool:
    print('\n== ION Modbus (Ethernet planta) ==')
    if sin_ion:
        print('  (omitido)')
        return True
    from bess.config.subestaciones import subestacion_por_id
    from bess.data.ingest.ion.modbus import MEDIDOR_IP_DEFAULT, PUERTO_DEFAULT

    sub1 = subestacion_por_id('IUSA_1')
    sub2 = subestacion_por_id('IUSA_2')
    ip1 = (sub1.modbus_ip if sub1 else None) or MEDIDOR_IP_DEFAULT
    port1 = PUERTO_DEFAULT
    ip2 = (sub2.modbus_ip if sub2 else None) or '172.16.205.203'
    port2 = PUERTO_DEFAULT

    ok_all = True
    for nombre, host, port in (
        ('ION IUSA 1', ip1, port1),
        ('ION IUSA 2', ip2, port2),
    ):
        ok, detalle = _probar_tcp(str(host), int(port))
        if ok:
            _ok(f'{nombre}: {detalle}')
        else:
            _fail(f'{nombre}: {detalle}')
            ok_all = False
            print('         → En UI: warning “Medidor ION no disponible” (soft-fail, sync sigue).')
    return ok_all


def _probar_api() -> bool:
    print('\n== API IUSASOL (ISOL) ==')
    try:
        from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
        from bess.data.ingest.iusasol.client import IusasolError
    except Exception as exc:
        _fail(f'No se pudo importar cliente: {exc}')
        return False

    try:
        cfg = cargar_config_iusasol()
    except RuntimeError as exc:
        _fail(str(exc))
        print('         → Configure .streamlit/secrets.toml [iusasol] o IUSASOL_CLIENT_*.')
        return False

    client = IusasolClient(cfg)
    t0 = time.time()
    try:
        token = client.autenticar()
        ms = (time.time() - t0) * 1000
        _ok(f'OAuth Token ({ms:.0f} ms) company={client.company}')
        print(f'         token_type={token.get("token_type")} expires_in={token.get("expires_in")}')
    except IusasolError as exc:
        _fail(f'OAuth/API: {exc}')
        print('         → En UI: warning “API no disponible (sync parcial)” + export ION.')
        print('         → Fallback: Mantenimiento DB → PCarga → Fallback IUSA 1/2.')
        return False
    except Exception as exc:
        _fail(f'OAuth/API inesperado: {exc}')
        return False

    t0 = time.time()
    try:
        data = client.listar_medidores()
        n = len(data.get('meters') or []) if isinstance(data, dict) else 0
        _ok(f'Meters ({(time.time() - t0) * 1000:.0f} ms) n={n}')
    except Exception as exc:
        _fail(f'Meters: {exc}')
        return False
    return True


def _probar_granja() -> bool:
    print('\n== Granja IUSA 2 (Farm API) ==')
    try:
        from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
        from bess.data.ingest.granja.farm_client import FarmClient
    except Exception as exc:
        _fail(f'Import: {exc}')
        return False

    try:
        cfg = cargar_config_iusasol()
        isol = IusasolClient(cfg)
        isol.autenticar()
        farm = FarmClient(isol)
        t0 = time.time()
        granjas = farm.listar_granjas()
        _ok(f'Farms ({(time.time() - t0) * 1000:.0f} ms) n={len(granjas)}')
        return True
    except Exception as exc:
        _fail(f'Farm: {exc}')
        print('         → Soft-fail: sync exporta sin actualizar generación IUSA 2.')
        print('         → No hay fallback pcarga para Mega01–20.')
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Prueba conectividad ION / API ISOL / Granja para sync BESS.',
    )
    parser.add_argument('--sin-ion', action='store_true', help='No probar Modbus.')
    parser.add_argument('--solo-api', action='store_true', help='Solo OAuth + Meters.')
    parser.add_argument('--sin-granja', action='store_true', help='No probar Farm.')
    args = parser.parse_args()

    print('Diagnóstico de conectividad — sync BESS')
    print(f'Raíz: {ROOT}')

    resultados: list[tuple[str, bool]] = []
    if not args.solo_api:
        resultados.append(('ION', _probar_ion(args.sin_ion)))
    resultados.append(('API', _probar_api()))
    if not args.solo_api and not args.sin_granja:
        resultados.append(('Granja', _probar_granja()))

    print('\n== Resumen ==')
    for nombre, ok in resultados:
        print(f'  {nombre}: {"OK" if ok else "FALLA"}')

    print('\nPrueba en la app (con la afectación actual):')
    print('  1. Login admin → sidebar → “Sincronizar ahora”.')
    print('  2. Anote: ¿warning ION, warning API parcial, o éxito?')
    print('  3. Si API FALLA y planta OK: Mantenimiento DB → PCarga → Fallback IUSA 1/2.')
    print('  4. En consola, solo ION (manual):')
    print('       python scripts/sincronizar_perfiles.py --quiet --sin-api --sin-granja')
    print('  5. Sync completo con API caída (soft-fail + export):')
    print('       python scripts/sincronizar_perfiles.py --quiet')

    return 0 if all(ok for _, ok in resultados) else 1


if __name__ == '__main__':
    raise SystemExit(main())
