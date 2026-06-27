#!/usr/bin/env python3
"""Obtiene token OAuth y lista medidores ISOL (API IUSASOL)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError


def _formatear_salida(datos, *, pretty: bool) -> str:
    if pretty:
        return json.dumps(datos, ensure_ascii=False, indent=2)
    return json.dumps(datos, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Autentica en IUSASOL y lista medidores ISOL.',
    )
    parser.add_argument(
        '--solo-token',
        action='store_true',
        help='Solo muestra datos del token (sin listar medidores).',
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='JSON indentado.',
    )
    args = parser.parse_args()

    try:
        config = cargar_config_iusasol()
        client = IusasolClient(config)
        token_info = client.autenticar()

        if args.solo_token:
            print(_formatear_salida(token_info, pretty=args.pretty))
            return 0

        medidores = client.listar_medidores()
        items = medidores.get('meters', []) if isinstance(medidores, dict) else []
        destacados = []
        for item in items:
            serial = str(item.get('serial', '')).upper()
            if any(p in serial for p in ('CS3878', 'CS1996', 'BESS', 'BANCO')):
                destacados.append(item)
        salida = {
            'company': client.company,
            'token_type': token_info.get('token_type'),
            'expires_in': token_info.get('expires_in'),
            'medidores_destacados': destacados,
            'medidores': medidores,
        }
        print(_formatear_salida(salida, pretty=args.pretty))
        return 0
    except IusasolError as exc:
        print(f'Error API: {exc}', file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
