#!/usr/bin/env python3
"""Obtiene token OAuth y lista contratos activos ISOL (API IUSASOL)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError


def _formatear_salida(datos: Any, *, pretty: bool) -> str:
    if pretty:
        return json.dumps(datos, ensure_ascii=False, indent=2)
    return json.dumps(datos, ensure_ascii=False)


def _extraer_contratos(payload: Any) -> list[Any]:
    """La ayuda del API documenta `meters`; en la práctica puede venir `contracts`."""
    if not isinstance(payload, dict):
        return payload if isinstance(payload, list) else []
    for clave in ('contracts', 'contract', 'meters', 'items', 'data'):
        valor = payload.get(clave)
        if isinstance(valor, list):
            return valor
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Autentica en IUSASOL y lista contratos activos ISOL.',
    )
    parser.add_argument(
        '--company',
        default=None,
        help='Clave de empresa (default: ckey del token / ISM).',
    )
    parser.add_argument(
        '--contrato',
        default=None,
        help='Id encriptado de contrato: lista medidores de ese contrato.',
    )
    parser.add_argument(
        '--solo-token',
        action='store_true',
        help='Solo muestra datos del token (sin listar contratos).',
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

        company = args.company or client.company

        if args.contrato:
            detalle = client.listar_medidores_contrato(
                args.contrato,
                company=company,
            )
            salida = {
                'company': company,
                'contrato': args.contrato,
                'token_type': token_info.get('token_type'),
                'expires_in': token_info.get('expires_in'),
                'medidores': detalle,
            }
            print(_formatear_salida(salida, pretty=args.pretty))
            return 0

        contratos = client.listar_contratos(company=company)
        items = _extraer_contratos(contratos)
        salida = {
            'company': company,
            'token_type': token_info.get('token_type'),
            'expires_in': token_info.get('expires_in'),
            'total': len(items),
            'contratos': items,
            'raw': contratos,
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
