#!/usr/bin/env python3
"""Descarga perfil ISOL (API IUSASOL) y lo guarda como JSON."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import DIRECTORIO_FUENTE
from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError
from bess.data.ingest.iusasol.meters import ALIAS_SERIAL, resolver_id_medidor
from bess.data.ingest.iusasol.to_csv import guardar_perfil_csv, perfil_json_a_csv


def _formatear_json(datos, *, pretty: bool) -> str:
    if pretty:
        return json.dumps(datos, ensure_ascii=False, indent=2)
    return json.dumps(datos, ensure_ascii=False)


def _nombre_salida(medidor: str, desde: str, hasta: str, detallado: bool) -> str:
    tipo = 'detailed' if detallado else 'gral'
    slug = medidor.replace('/', '_').replace('\\', '_')
    return f'perfil_{slug}_{desde}_{hasta}_{tipo}.json'


def main() -> int:
    ayer = (date.today() - timedelta(days=1)).isoformat()
    parser = argparse.ArgumentParser(
        description='Descarga perfil ISOL de un medidor (respuesta JSON de la API).',
    )
    parser.add_argument(
        '--medidor',
        required=True,
        help=f'Alias ({", ".join(ALIAS_SERIAL)}) o idcode completo.',
    )
    parser.add_argument('--desde', default=ayer, help='Fecha inicio YYYY-MM-DD.')
    parser.add_argument('--hasta', default=ayer, help='Fecha fin YYYY-MM-DD.')
    parser.add_argument(
        '--tym',
        help='Escala tym: 0=W, 1=Wh, 2=kWh, 3=MWh, 4=GWh (default 2).',
    )
    parser.add_argument('--tye', help='E=energía, P=potencia (default E).')
    parser.add_argument(
        '--detallado',
        action='store_true',
        help='Usar Profiles/Detailed en lugar de Profiles/Gral.',
    )
    parser.add_argument(
        '--solo-api',
        action='store_true',
        help='Guardar solo el JSON crudo de la API (sin metadatos del script).',
    )
    parser.add_argument(
        '--salida',
        type=Path,
        help='Ruta del JSON de salida (default: data/ArchivosFuente/perfiles_api/).',
    )
    parser.add_argument(
        '--stdout',
        action='store_true',
        help='Imprimir JSON en consola en lugar de guardar archivo.',
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='Guardar CSV compatible con BESS (Fecha,KWH_REC,...) en ArchivosFuente.',
    )
    parser.add_argument('--pretty', action='store_true', help='JSON indentado.')
    args = parser.parse_args()

    try:
        config = cargar_config_iusasol()
        tym = args.tym or config.tym
        tye = args.tye or config.tye
        if not tym or not tye:
            print(
                'Indique --tym y --tye, o configúrelos en secrets/env '
                '(recomendado: tym=2, tye=E para kWh).',
                file=sys.stderr,
            )
            return 1

        client = IusasolClient(config)
        medidores_api = client.listar_medidores()
        meter_id = resolver_id_medidor(args.medidor, medidores_api)
        perfil = client.obtener_perfil(
            meter_id,
            args.desde,
            args.hasta,
            tym=tym,
            tye=tye,
            detallado=args.detallado,
        )

        if args.csv:
            alias = args.medidor.strip().lower()
            nombre_csv = {
                "bess": "BESS.csv",
                "bess_iusa2": "BESS_IUSA2.csv",
                "banco1": "Banco1.csv",
                "banco": "Banco1.csv",
                "banco2": "Banco2.csv",
            }.get(alias, f"{args.medidor}.csv")
            ruta_csv = args.salida or (DIRECTORIO_FUENTE / nombre_csv)
            guardar_perfil_csv(perfil, ruta_csv)
            print(f'CSV guardado en: {ruta_csv}')
            return 0

        if args.solo_api:
            payload = perfil
        else:
            payload = {
                'medidor': args.medidor,
                'id': meter_id,
                'desde': args.desde,
                'hasta': args.hasta,
                'tym': tym,
                'tye': tye,
                'company': client.company,
                'detallado': args.detallado,
                'perfil': perfil,
            }
        texto = _formatear_json(payload, pretty=args.pretty)

        if args.stdout:
            print(texto)
            return 0

        carpeta = DIRECTORIO_FUENTE / 'perfiles_api'
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = args.salida or carpeta / _nombre_salida(args.medidor, args.desde, args.hasta, args.detallado)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto + '\n', encoding='utf-8')
        print(f'Perfil guardado en: {ruta}')
        return 0
    except IusasolError as exc:
        print(f'Error API: {exc}', file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
