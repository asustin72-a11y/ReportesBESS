#!/usr/bin/env python3
"""Genera CSV Contrato / Serial / Último perfil (API IUSASOL).

Flujo:
  1. GET Reports/ISOL/Contracts
  2. GET Reports/ISOL/Contract?id=... por cada contrato (medidores)
  3. GET Reports/ISOL/Profiles/Gral — busca el último slot con energía ≠ 0
     (la API rellena ceros hasta el día en curso; max(time) no basta)

Credenciales: IUSASOL_CLIENT_ID / IUSASOL_CLIENT_SECRET o
.streamlit/secrets.toml [iusasol] (igual que el resto de scripts ISOL).

Ejemplos:
  python scripts/reporte_contratos_medidores_iusasol.py
  python scripts/reporte_contratos_medidores_iusasol.py --salida data/mi_reporte.csv
  python scripts/reporte_contratos_medidores_iusasol.py --sin-ultimo-perfil
  python scripts/reporte_contratos_medidores_iusasol.py --incluir-vacios --workers 8
"""

from __future__ import annotations

import argparse
import csv
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError
from bess.data.ingest.iusasol.config import IusasolConfig
from bess.data.ingest.iusasol.to_csv import TYE_ENERGIA, TYM_KWH

SALIDA_DEFAULT = ROOT / 'data' / 'consultas_usuarios' / 'reporte_principal.csv'
VENTANAS_DEFAULT = (30, 90, 365)
CAMPOS = ('Contrato', 'Serial', 'Ultimo_perfil', 'Nota')


@dataclass(frozen=True)
class MedidorContrato:
    contrato: str
    serial: str
    meter_id: str


def _parse_ventanas(texto: str) -> tuple[int, ...]:
    partes = [p.strip() for p in texto.split(',') if p.strip()]
    if not partes:
        raise argparse.ArgumentTypeError('Indique al menos una ventana en días.')
    try:
        vals = tuple(int(p) for p in partes)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            'Las ventanas deben ser enteros en días, p.ej. 30,90,365'
        ) from exc
    if any(v < 1 for v in vals):
        raise argparse.ArgumentTypeError('Cada ventana debe ser >= 1.')
    return vals


def _ultimo_con_energia(profiles: list[Any]) -> str | None:
    ultimo: str | None = None
    for item in profiles:
        if not isinstance(item, dict):
            continue
        tiempo = item.get('time')
        if not tiempo:
            continue
        canales = item.get('channels') or []
        if any(float(c or 0) != 0 for c in canales):
            marca = str(tiempo)
            if ultimo is None or marca > ultimo:
                ultimo = marca
    return ultimo


def _formatear_fecha(valor: str) -> str:
    return valor.replace('T', ' ') if valor else ''


def listar_medidores_por_contrato(
    client: IusasolClient,
    *,
    incluir_vacios: bool,
) -> tuple[list[MedidorContrato], list[str]]:
    """Devuelve (medidores, contratos_sin_medidor)."""
    data = client.listar_contratos()
    contratos = data.get('contracts') if isinstance(data, dict) else None
    if not isinstance(contratos, list):
        raise IusasolError('Respuesta de Contracts sin lista "contracts"')

    medidores: list[MedidorContrato] = []
    vacios: list[str] = []

    for i, contrato in enumerate(contratos, 1):
        if not isinstance(contrato, dict):
            continue
        nick = str(contrato.get('nickisol') or '').strip()
        cid = str(contrato.get('idcode') or '').strip()
        if not cid:
            continue
        det = client.medidores_de_contrato(cid)
        meters = det.get('meters') if isinstance(det, dict) else None
        if not isinstance(meters, list) or not meters:
            vacios.append(nick or cid)
            if incluir_vacios:
                medidores.append(MedidorContrato(contrato=nick, serial='', meter_id=''))
            continue
        for m in meters:
            if not isinstance(m, dict):
                continue
            serial = str(m.get('serial') or '').strip()
            mid = str(m.get('idcode') or '').strip()
            if not serial and not mid:
                continue
            medidores.append(MedidorContrato(contrato=nick, serial=serial, meter_id=mid))
        if i % 50 == 0 or i == len(contratos):
            print(f'  contratos {i}/{len(contratos)}', file=sys.stderr, flush=True)

    return medidores, vacios


def ultimo_perfil_medidor(
    client: IusasolClient,
    meter_id: str,
    *,
    ventanas: tuple[int, ...],
    tym: str,
    tye: str,
) -> tuple[str, str]:
    """(Ultimo_perfil, Nota). Amplía ventana si solo hay ceros."""
    if not meter_id:
        return '', 'sin medidor'
    hoy = date.today()
    hubo_perfiles = False
    for dias in ventanas:
        begin = (hoy - timedelta(days=dias - 1)).isoformat()
        end = hoy.isoformat()
        try:
            data = client.obtener_perfil(
                meter_id,
                begin,
                end,
                tym=tym,
                tye=tye,
                permitir_vacio=True,
            )
        except IusasolError as exc:
            if exc.codigo in (401, 403):
                client.autenticar()
                data = client.obtener_perfil(
                    meter_id,
                    begin,
                    end,
                    tym=tym,
                    tye=tye,
                    permitir_vacio=True,
                )
            else:
                raise
        profiles = data.get('profiles') if isinstance(data, dict) else None
        if not isinstance(profiles, list) or not profiles:
            continue
        hubo_perfiles = True
        ultimo = _ultimo_con_energia(profiles)
        if ultimo:
            return _formatear_fecha(ultimo), ''
    if hubo_perfiles:
        return '', f'sin energía (ceros) en {ventanas[-1]}d'
    return '', 'sin perfiles'


def _clientes_por_hilo(config: IusasolConfig) -> threading.local:
    local = threading.local()

    def obtener() -> IusasolClient:
        client = getattr(local, 'client', None)
        if client is None:
            client = IusasolClient(config)
            client.autenticar()
            local.client = client
        return client

    local.obtener = obtener  # type: ignore[attr-defined]
    return local


def enriquecer_ultimo_perfil(
    config: IusasolConfig,
    medidores: list[MedidorContrato],
    *,
    ventanas: tuple[int, ...],
    workers: int,
    tym: str,
    tye: str,
) -> list[dict[str, str]]:
    local = _clientes_por_hilo(config)
    filas: list[dict[str, str]] = []
    errores = 0
    hechos = 0
    t0 = time.time()
    total = len(medidores)

    def trabajo(m: MedidorContrato) -> dict[str, str]:
        client = local.obtener()  # type: ignore[attr-defined]
        try:
            ultimo, nota = ultimo_perfil_medidor(
                client, m.meter_id, ventanas=ventanas, tym=tym, tye=tye,
            )
        except Exception as exc:  # noqa: BLE001 — reportar y seguir
            return {
                'Contrato': m.contrato,
                'Serial': m.serial,
                'Ultimo_perfil': '',
                'Nota': f'ERROR: {exc}',
            }
        return {
            'Contrato': m.contrato,
            'Serial': m.serial,
            'Ultimo_perfil': ultimo,
            'Nota': nota,
        }

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futuros = {pool.submit(trabajo, m): m for m in medidores}
        for fut in as_completed(futuros):
            fila = fut.result()
            filas.append(fila)
            hechos += 1
            if fila['Nota'].startswith('ERROR'):
                errores += 1
            if hechos % 25 == 0 or hechos == total:
                print(
                    f'  perfiles {hechos}/{total}  errores={errores}  '
                    f'{time.time() - t0:.0f}s',
                    file=sys.stderr,
                    flush=True,
                )

    filas.sort(key=lambda r: ((r['Contrato'] or '\uffff').casefold(), r['Serial']))
    return filas


def escribir_csv(ruta: Path, filas: list[dict[str, str]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open('w', newline='', encoding='utf-8-sig') as archivo:
        writer = csv.DictWriter(archivo, fieldnames=list(CAMPOS))
        writer.writeheader()
        writer.writerows(filas)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            'Reporte ISOL: contratos, medidores y último perfil con energía '
            '(CSV: Contrato, Serial, Ultimo_perfil, Nota).'
        ),
    )
    parser.add_argument(
        '--salida',
        type=Path,
        default=SALIDA_DEFAULT,
        help=f'CSV de salida (default: {SALIDA_DEFAULT}).',
    )
    parser.add_argument(
        '--sin-ultimo-perfil',
        action='store_true',
        help='Solo contratos y seriales (sin consultar Profiles/Gral).',
    )
    parser.add_argument(
        '--incluir-vacios',
        action='store_true',
        help='Incluir contratos sin medidores (Serial y Ultimo_perfil vacíos).',
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=6,
        help='Hilos para consultar perfiles (default: 6).',
    )
    parser.add_argument(
        '--ventanas',
        type=_parse_ventanas,
        default=VENTANAS_DEFAULT,
        help='Días a probar en orden, p.ej. 30,90,365 (default: 30,90,365).',
    )
    parser.add_argument(
        '--tym',
        default=None,
        help=f'Escala tym (default: config o {TYM_KWH}=kWh).',
    )
    parser.add_argument(
        '--tye',
        default=None,
        help=f'Tipo tye (default: config o {TYE_ENERGIA}=energía).',
    )
    args = parser.parse_args()

    try:
        config = cargar_config_iusasol()
        tym = (args.tym or config.tym or TYM_KWH).strip() or TYM_KWH
        tye = (args.tye or config.tye or TYE_ENERGIA).strip() or TYE_ENERGIA

        print('Autenticando…', file=sys.stderr, flush=True)
        client = IusasolClient(config)
        client.autenticar()
        print(f'Company={client.company}', file=sys.stderr, flush=True)

        print('Listando contratos y medidores…', file=sys.stderr, flush=True)
        medidores, vacios = listar_medidores_por_contrato(
            client, incluir_vacios=args.incluir_vacios,
        )
        print(
            f'Medidores={len(medidores)}  contratos_vacíos={len(vacios)}',
            file=sys.stderr,
            flush=True,
        )

        if args.sin_ultimo_perfil:
            filas = [
                {
                    'Contrato': m.contrato,
                    'Serial': m.serial,
                    'Ultimo_perfil': '',
                    'Nota': 'sin medidor' if not m.serial else '',
                }
                for m in medidores
            ]
            filas.sort(
                key=lambda r: ((r['Contrato'] or '\uffff').casefold(), r['Serial'])
            )
        else:
            print(
                f'Buscando último perfil con energía (ventanas={args.ventanas}, '
                f'workers={args.workers})…',
                file=sys.stderr,
                flush=True,
            )
            # Solo consultar perfiles de filas con meter_id
            con_id = [m for m in medidores if m.meter_id]
            sin_id = [m for m in medidores if not m.meter_id]
            filas = enriquecer_ultimo_perfil(
                config,
                con_id,
                ventanas=args.ventanas,
                workers=args.workers,
                tym=tym,
                tye=tye,
            )
            for m in sin_id:
                filas.append({
                    'Contrato': m.contrato,
                    'Serial': m.serial,
                    'Ultimo_perfil': '',
                    'Nota': 'sin medidor',
                })
            filas.sort(
                key=lambda r: ((r['Contrato'] or '\uffff').casefold(), r['Serial'])
            )

        escribir_csv(args.salida, filas)
        con_energia = sum(1 for r in filas if r['Ultimo_perfil'])
        print(
            f'OK → {args.salida}  filas={len(filas)}  '
            f'con_ultimo_perfil={con_energia}',
            file=sys.stderr,
            flush=True,
        )
        print(args.salida)
        return 0
    except IusasolError as exc:
        print(f'Error API: {exc}', file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
