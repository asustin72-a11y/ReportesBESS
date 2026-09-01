#!/usr/bin/env python3
"""CLI de consulta/actualización de tarifas CFE (presets BESS + catálogo).

Consulta libre (cualquier código del catálogo):
  python scripts/consultar_tarifas_cfe.py --codigo DIST --mes 8 \\
      --estado "ESTADO DE MÉXICO" --municipio JOCOTITLAN --division "CENTRO SUR"

Presets:
  python scripts/consultar_tarifas_cfe.py --preset jocotitlan --mes 8
  python scripts/consultar_tarifas_cfe.py --preset tarifa1 --mes 8

Persistencia (DIST / GDMTH / PDBT / T1):
  python scripts/consultar_tarifas_cfe.py --preset jocotitlan --mes 8 --escribir-csv --actualizar-bd
  python scripts/consultar_tarifas_cfe.py --preset miguel_hidalgo --mes 8 --escribir-csv --actualizar-bd
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.constants import TIPOS_TARIFA, archivo_tarifas_csv
from bess.config.esquema_tarifa import ESQUEMAS_CATALOGO, ESQUEMAS_CALCULO
from bess.config.paths import DIRECTORIO_TARIFAS
from bess.data.ingest.cfe import (
    PRESETS,
    TARIFAS_CFE,
    CfeTarifasError,
    ResultadoTarifaCFE,
    consultar_preset,
    consultar_tarifa_catalogo,
)
from bess.data.tariffs_db import guardar_tarifas_dict, leer_tarifas_dict
from bess.tariffs.loader import invalidar_cache_tarifas


def _archivo_csv(esquema_id: str, anio: int) -> Path:
    esquema = (esquema_id or "").strip().upper()
    if esquema not in ESQUEMAS_CATALOGO:
        raise ValueError(
            f"El esquema {esquema_id} no tiene CSV "
            f"(solo {', '.join(sorted(ESQUEMAS_CATALOGO))})."
        )
    return DIRECTORIO_TARIFAS / archivo_tarifas_csv(anio, esquema=esquema)


def _imprimir(resultado: ResultadoTarifaCFE) -> None:
    titulo = resultado.codigo_tarifa or resultado.esquema_id
    print(
        f"{titulo} | {resultado.anio}-{resultado.mes:02d} | "
        f"{resultado.municipio} / {resultado.division}".strip(" /")
    )
    if resultado.nombre_tarifa:
        print(resultado.nombre_tarifa)
    print(f"URL: {resultado.url}")
    print()
    if resultado.tablas:
        for tabla in resultado.tablas:
            print(tabla.titulo)
            cols = tabla.columnas
            anchos = [len(c) for c in cols]
            for fila in tabla.filas:
                for i, col in enumerate(cols):
                    anchos[i] = max(anchos[i], len(str(fila.get(col, ""))))
            print("  " + "  ".join(c.ljust(anchos[i]) for i, c in enumerate(cols)))
            for fila in tabla.filas:
                print(
                    "  "
                    + "  ".join(
                        str(fila.get(col, "")).ljust(anchos[i])
                        for i, col in enumerate(cols)
                    )
                )
            print()
    else:
        ancho = max((len(str(k)) for k in resultado.cargos), default=10)
        for tipo, valor in resultado.cargos.items():
            print(f"  {tipo:<{ancho}}  {valor}")
    print(f"Publicado: {'sí' if resultado.publicado() else 'no'}")

def _escribir_csv(resultado: ResultadoTarifaCFE) -> Path:
    ruta = _archivo_csv(resultado.esquema_id, resultado.anio)
    matriz = resultado.a_matriz_mes(
        leer_tarifas_dict(resultado.esquema_id, resultado.anio)
    )
    DIRECTORIO_TARIFAS.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Tarifa", *[str(m) for m in range(1, 13)]])
        for tipo in TIPOS_TARIFA:
            valores = matriz.get(tipo, {})
            writer.writerow([tipo, *[valores.get(m, 0.0) for m in range(1, 13)]])
    return ruta


def _actualizar_bd(resultado: ResultadoTarifaCFE) -> None:
    matriz = resultado.a_matriz_mes(
        leer_tarifas_dict(resultado.esquema_id, resultado.anio)
    )
    guardar_tarifas_dict(matriz, resultado.esquema_id, resultado.anio)
    invalidar_cache_tarifas()


def main() -> int:
    hoy = date.today()
    parser = argparse.ArgumentParser(
        description="Consulta tarifas CFE (catálogo completo o presets BESS).",
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="Lista el catálogo de tarifas y sale.",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="Preset BESS (jocotitlan, aragon, …).",
    )
    parser.add_argument(
        "--codigo",
        help="Código CFE del catálogo (1, 1A, PDBT, GDMTH, DIST, …).",
    )
    parser.add_argument("--anio", type=int, default=hoy.year)
    parser.add_argument("--mes", type=int, default=hoy.month)
    parser.add_argument("--estado", default="")
    parser.add_argument("--municipio", default="")
    parser.add_argument("--division", default="")
    parser.add_argument("--region-tabla", default="")
    parser.add_argument(
        "--inicio-verano",
        default="MAYO",
        help="Inicio temporada verano (1A–1F): FEBRERO…MAYO.",
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--escribir-csv",
        action="store_true",
        help="Fusiona el mes en data/Tarifas (DIST/GDMTH/PDBT/T1).",
    )
    parser.add_argument(
        "--actualizar-bd",
        action="store_true",
        help="Fusiona el mes en catalog_tarifas (DIST/GDMTH/PDBT/T1).",
    )
    args = parser.parse_args()

    if args.listar:
        for t in TARIFAS_CFE:
            geo = "geo" if t.requiere_geo else "—"
            print(f"{t.categoria:10s} {t.codigo:6s} {t.nombre:40s} {geo}")
        return 0

    if not 1 <= args.mes <= 12:
        print("ERROR: --mes debe estar entre 1 y 12.", file=sys.stderr)
        return 2
    if not args.preset and not args.codigo:
        print("ERROR: indique --preset o --codigo (o --listar).", file=sys.stderr)
        return 2

    try:
        if args.preset:
            print(f"Consultando preset {args.preset}…")
            resultado = consultar_preset(
                args.preset,
                anio=args.anio,
                mes=args.mes,
                headless=not args.headed,
            )
        else:
            print(f"Consultando {args.codigo}…")
            resultado = consultar_tarifa_catalogo(
                args.codigo,
                anio=args.anio,
                mes=args.mes,
                estado=args.estado,
                municipio=args.municipio,
                division=args.division,
                region_tabla=args.region_tabla or None,
                inicio_verano=args.inicio_verano,
                headless=not args.headed,
            )
    except CfeTarifasError as exc:
        print(f"ERROR CFE: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    _imprimir(resultado)

    if args.escribir_csv or args.actualizar_bd:
        if resultado.esquema_id not in ESQUEMAS_CATALOGO:
            print(
                f"\nAVISO: esquema {resultado.esquema_id} no está en el catálogo "
                f"persistible ({', '.join(sorted(ESQUEMAS_CATALOGO))}); no se escribe.",
                file=sys.stderr,
            )
            return 0
        if resultado.esquema_id not in ESQUEMAS_CALCULO and args.actualizar_bd:
            # PDBT/T1 van a BD de catálogo; no son cálculo BESS.
            pass
    if args.escribir_csv:
        ruta = _escribir_csv(resultado)
        print(f"\nCSV actualizado: {ruta}")
    if args.actualizar_bd:
        _actualizar_bd(resultado)
        print(f"BD actualizada: esquema {resultado.esquema_id} · año {resultado.anio}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
