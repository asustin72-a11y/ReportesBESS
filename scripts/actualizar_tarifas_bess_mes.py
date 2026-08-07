#!/usr/bin/env python3
"""Actualiza tarifas BESS (DIST / GDMTH) del mes en curso desde CFE.

Política:
  - Arranca a partir del día 1 a las 02:00 (hora local).
  - Si el mes aún no está publicado en CFE, sale con código 1 (reintento).
  - Si ya hay precios del mes en BD, no hace nada (código 0).
  - Pensado para cron horario: `0 * * * *`.

Ejemplos:
  python scripts/actualizar_tarifas_bess_mes.py
  python scripts/actualizar_tarifas_bess_mes.py --forzar
  python scripts/actualizar_tarifas_bess_mes.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.constants import TIPOS_TARIFA, archivo_tarifas_csv
from bess.config.esquema_tarifa import ESQUEMAS_CALCULO
from bess.config.paths import DIRECTORIO_TARIFAS
from bess.data.ingest.cfe import PRESETS, PRESETS_BESS_AUTO, CfeTarifasError, consultar_preset
from bess.data.tariffs_db import guardar_tarifas_dict, leer_tarifas_dict
from bess.tariffs.loader import invalidar_cache_tarifas

ZONA = ZoneInfo("America/Mexico_City")
HORA_INICIO = 2  # 02:00 del día 1


def _mes_publicado_en_bd(esquema_id: str, anio: int, mes: int) -> bool:
    matriz = leer_tarifas_dict(esquema_id, anio)
    # Se considera publicado si hay energía Base o Intermedio/Punta > 0.
    for tipo in ("Base", "Intermedio", "Punta", "Capacidad"):
        if abs(float(matriz.get(tipo, {}).get(mes, 0) or 0)) > 1e-9:
            return True
    return False


def _escribir_csv(esquema_id: str, anio: int, matriz: dict) -> Path:
    ruta = DIRECTORIO_TARIFAS / archivo_tarifas_csv(anio, esquema=esquema_id)
    DIRECTORIO_TARIFAS.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Tarifa", *[str(m) for m in range(1, 13)]])
        for tipo in TIPOS_TARIFA:
            valores = matriz.get(tipo, {})
            writer.writerow([tipo, *[valores.get(m, 0.0) for m in range(1, 13)]])
    return ruta


def _debe_intentar(ahora: datetime, *, forzar: bool) -> tuple[bool, str]:
    if forzar:
        return True, "forzado"
    if ahora.day < 1:
        return False, "día inválido"
    if ahora.day == 1 and ahora.hour < HORA_INICIO:
        return False, f"esperando {HORA_INICIO:02d}:00 del día 1"
    return True, "ventana activa"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Actualiza DIST/GDMTH BESS del mes actual desde CFE."
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Ignora ventana horaria y vuelve a consultar aunque ya haya datos.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Consulta CFE pero no escribe CSV/BD.",
    )
    parser.add_argument("--headed", action="store_true", help="Chromium visible.")
    args = parser.parse_args()

    ahora = datetime.now(ZONA)
    anio, mes = ahora.year, ahora.month
    ok_ventana, motivo = _debe_intentar(ahora, forzar=args.forzar)
    print(f"[{ahora:%Y-%m-%d %H:%M %Z}] mes={anio}-{mes:02d} · {motivo}")
    if not ok_ventana:
        return 0

    pendientes = []
    for preset_id in PRESETS_BESS_AUTO:
        preset = PRESETS[preset_id]
        esquema = preset.esquema_id
        if esquema not in ESQUEMAS_CALCULO:
            continue
        if not args.forzar and _mes_publicado_en_bd(esquema, anio, mes):
            print(f"  OK {preset_id} ({esquema}): mes ya publicado en BD")
            continue
        pendientes.append(preset_id)

    if not pendientes:
        print("Nada pendiente.")
        return 0

    fallos_publicacion = 0
    errores = 0
    for preset_id in pendientes:
        preset = PRESETS[preset_id]
        print(f"  Consultando {preset.descripcion}…")
        try:
            resultado = consultar_preset(
                preset_id,
                anio=anio,
                mes=mes,
                headless=not args.headed,
            )
        except CfeTarifasError as exc:
            print(f"  PENDIENTE {preset_id}: CFE aún no publica / error de parseo ({exc})")
            fallos_publicacion += 1
            continue
        except Exception as exc:
            print(f"  ERROR {preset_id}: {exc}")
            errores += 1
            continue

        if not resultado.publicado():
            print(f"  PENDIENTE {preset_id}: respuesta sin cargos > 0")
            fallos_publicacion += 1
            continue

        print(
            f"  {preset_id}: "
            + ", ".join(f"{k}={v}" for k, v in list(resultado.cargos.items())[:6])
        )
        if args.dry_run:
            print("  (dry-run: no se escribe)")
            continue

        matriz = resultado.a_matriz_mes(
            leer_tarifas_dict(resultado.esquema_id, resultado.anio)
        )
        ruta = _escribir_csv(resultado.esquema_id, resultado.anio, matriz)
        guardar_tarifas_dict(matriz, resultado.esquema_id, resultado.anio)
        invalidar_cache_tarifas()
        print(f"  Guardado {resultado.esquema_id}/{resultado.anio} → {ruta.name}")

    if errores:
        return 2
    if fallos_publicacion:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
