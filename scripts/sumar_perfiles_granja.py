#!/usr/bin/env python3
"""Consolida perfiles MEGA: una columna kW por medidor + suma total."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _orden_mega(ruta: Path) -> int:
    coincidencia = re.search(r"MEGA_+(\d+)", ruta.stem)
    return int(coincidencia.group(1)) if coincidencia else 9999


def _nombre_columna(indice: int) -> str:
    return f"MEGA_{indice:02d}_kW"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolida CSV MEGA: columnas kW por medidor y total.",
    )
    parser.add_argument(
        "--entrada",
        type=Path,
        default=ROOT / "data" / "perfiles_granja",
        help="Carpeta con MEGA__N.csv",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help="CSV de salida (default: entrada/MEGA_total_20.csv)",
    )
    parser.add_argument("--cantidad", type=int, default=20, help="Cuántos archivos MEGA incluir.")
    args = parser.parse_args()

    carpeta = args.entrada.resolve()
    if not any(carpeta.glob("MEGA__*.csv")) and not any(
        a for a in carpeta.glob("MEGA_*.csv") if not a.name.startswith("MEGA_total")
    ):
        acumulado = carpeta / "Acumulado"
        if acumulado.is_dir():
            carpeta = acumulado

    archivos = sorted(carpeta.glob("MEGA__*.csv"), key=_orden_mega)
    if not archivos:
        archivos = sorted(
            (a for a in carpeta.glob("MEGA_*.csv") if not a.name.startswith("MEGA_total")),
            key=_orden_mega,
        )
    archivos = archivos[: args.cantidad]
    if not archivos:
        print(f"ERROR: no hay CSV MEGA en {carpeta}", file=sys.stderr)
        return 1

    columnas_mega = [_nombre_columna(i) for i in range(1, len(archivos) + 1)]
    filas: dict[str, dict[str, float]] = defaultdict(lambda: {c: 0.0 for c in columnas_mega})

    for indice, ruta in enumerate(archivos, start=1):
        columna = _nombre_columna(indice)
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                tiempo = fila["Fecha_Hora"]
                filas[tiempo][columna] += float(fila["kW"] or 0)

    encabezado = ["Fecha_Hora", *columnas_mega, "kW_total"]
    salida = args.salida or (carpeta / "MEGA_total_20.csv")
    salida.parent.mkdir(parents=True, exist_ok=True)

    with salida.open("w", encoding="utf-8-sig", newline="") as archivo:
        writer = csv.writer(archivo)
        writer.writerow(encabezado)
        for tiempo in sorted(filas):
            valores = [round(filas[tiempo][c], 4) for c in columnas_mega]
            total = round(sum(valores), 4)
            writer.writerow([tiempo, *valores, total])

    print(f"Consolidados {len(archivos)} archivos -> {len(filas)} registros")
    print(f"Columnas: Fecha_Hora + {len(columnas_mega)} MEGA + kW_total")
    print(f"Guardado: {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
