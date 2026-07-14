#!/usr/bin/env python3
"""Compara BD ION_IUSA2 vs CSV y vs medidor (muestra)."""
from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, RUTA_BD_PERFILES
from bess.config.subestaciones import subestacion_por_id
from bess.data.ingest.ion.modbus import (
    DATA_RECORDER_MODULE,
    NUM_SOURCES_DEFAULT,
    PUERTO_DEFAULT,
    ZONA_HORARIA_DEFAULT,
    conectar,
    leer_registro_por_numero,
    leer_rango_registros,
    mapear_sources_bess,
    seleccionar_data_recorder,
)
from zoneinfo import ZoneInfo
from datetime import datetime

DESDE = "2026-06-01 00:05:00"
HASTA = "2026-06-30 15:25:00"
COLS = ["kwh_rec", "kwh_ent", "kvarh_q1", "kvarh_q2", "kvarh_q3", "kvarh_q4"]
TOL = 1e-4


def load_csv(path: Path) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fecha = row.get("Fecha") or row.get("fecha") or ""
            if not fecha or fecha < DESDE or fecha > HASTA:
                continue
            out[fecha] = {
                c: float(row.get(c.upper(), row.get(c, 0)) or 0) for c in COLS
            }
    return out


def load_bd() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with sqlite3.connect(RUTA_BD_PERFILES) as conn:
        cur = conn.execute(
            """
            SELECT fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4, fuente
            FROM perfil_carga
            WHERE medidor_id = 'ION_IUSA2' AND fecha >= ? AND fecha <= ?
            ORDER BY fecha
            """,
            (DESDE, HASTA),
        )
        for row in cur:
            out[row[0]] = {COLS[i]: row[i + 1] for i in range(len(COLS))}
            out[row[0]]["fuente"] = row[7]
    return out


def diff_sets(a: dict, b: dict, name_a: str, name_b: str) -> tuple[int, int, int]:
    keys_a, keys_b = set(a), set(b)
    only_a = sorted(keys_a - keys_b)
    only_b = sorted(keys_b - keys_a)
    mism: list[tuple] = []
    for k in sorted(keys_a & keys_b):
        for c in COLS:
            va = a[k][c]
            vb = b[k][c]
            if abs(va - vb) > TOL:
                mism.append((k, c, va, vb))
                break
    print(f"=== {name_a} vs {name_b} ===")
    print(f"  Registros {name_a}: {len(a)} | {name_b}: {len(b)}")
    print(f"  Solo en {name_a}: {len(only_a)}")
    print(f"  Solo en {name_b}: {len(only_b)}")
    print(f"  Valores distintos: {len(mism)}")
    if only_a[:3]:
        print(f"  Ej solo {name_a}: {only_a[:3]}")
    if only_b[:3]:
        print(f"  Ej solo {name_b}: {only_b[:3]}")
    if mism[:8]:
        print("  Primeras diferencias:")
        for k, c, va, vb in mism[:8]:
            print(f"    {k} {c}: {va} vs {vb}")
    print()
    return len(only_a), len(only_b), len(mism)


def read_meter_at(fecha_str: str) -> dict[str, float] | None:
    ip = subestacion_por_id("IUSA2").modbus_ip or "172.16.205.203"
    zona = ZoneInfo(ZONA_HORARIA_DEFAULT)
    limite = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=zona)

    client = conectar(ip, PUERTO_DEFAULT)
    if not client.is_socket_open():
        return None
    try:
        if not seleccionar_data_recorder(client, DATA_RECORDER_MODULE):
            return None
        rango = leer_rango_registros(client)
        if rango is None:
            return None
        oldest, newest = rango
        lo, hi = oldest, newest
        found: int | None = None
        while lo <= hi:
            mid = (lo + hi) // 2
            reg = leer_registro_por_numero(
                client, mid, NUM_SOURCES_DEFAULT, zona, True
            )
            if reg is None:
                lo = mid + 1
                continue
            if reg.fecha < limite:
                lo = mid + 1
            else:
                found = mid
                hi = mid - 1
        if found is None:
            return None
        reg = leer_registro_por_numero(
            client, found, NUM_SOURCES_DEFAULT, zona, True
        )
        if reg is None or reg.fecha.strftime("%Y-%m-%d %H:%M:%S") != fecha_str:
            return None
        vals = mapear_sources_bess(reg.valores)
        return {
            "kwh_rec": vals["KWH_REC"],
            "kwh_ent": vals["KWH_ENT"],
            "kvarh_q1": vals["KVARH_Q1"],
            "kvarh_q2": vals["KVARH_Q2"],
            "kvarh_q3": vals["KVARH_Q3"],
            "kvarh_q4": vals["KVARH_Q4"],
        }
    finally:
        client.close()


def spot_check_meter(bd: dict, fechas: list[str]) -> None:
    print("=== Medidor vs BD (muestra) ===")
    ok = 0
    bad = 0
    for ts in fechas:
        if ts not in bd:
            print(f"  {ts}: no en BD")
            bad += 1
            continue
        meter = read_meter_at(ts)
        if meter is None:
            print(f"  {ts}: no leido del medidor")
            bad += 1
            continue
        diffs = [
            (c, bd[ts][c], meter[c])
            for c in COLS
            if abs(bd[ts][c] - meter[c]) > TOL
        ]
        if diffs:
            bad += 1
            print(f"  {ts}: DIFERENTE {diffs}")
        else:
            ok += 1
            print(
                f"  {ts}: OK  REC={bd[ts]['kwh_rec']:.6f} Q1={bd[ts]['kvarh_q1']:.6f}"
            )
    print(f"  Coinciden: {ok}/{len(fechas)}")
    print()


def main() -> None:
    print(f"Rango: {DESDE} -> {HASTA}\n")
    bd = load_bd()
    fuente = load_csv(DIRECTORIO_FUENTE / "ION_IUSA2.csv")
    proc = load_csv(DIRECTORIO_PROCESADOS / "ION_IUSA2.csv")

    diff_sets(bd, fuente, "BD", "ArchivosFuente CSV")
    if proc:
        diff_sets(bd, proc, "BD (post-sync)", "ArchivosProcesados CSV")

    from collections import Counter
    print("Fuentes en BD (rango):", dict(Counter(v["fuente"] for v in bd.values())))
    print()

    muestra = [
        "2026-06-01 00:05:00",
        "2026-06-01 00:10:00",
        "2026-06-01 00:15:00",
        "2026-06-01 00:20:00",
        "2026-06-01 00:25:00",
        "2026-06-15 12:00:00",
        "2026-06-24 00:00:00",
        "2026-06-30 15:25:00",
    ]
    spot_check_meter(bd, muestra)


if __name__ == "__main__":
    main()
