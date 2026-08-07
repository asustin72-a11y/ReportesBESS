"""Demanda máxima a partir del perfil cincominutal (kWh → kW)."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from deteccion_perfil import FMT_CANONICO, inspeccionar_perfil, parsear_fecha
from filtrar_perfil import fecha_operativa


def _parse_dt(texto: str, fmt_hint: str | None = None) -> datetime:
    t = (texto or "").strip().replace("T", " ", 1)
    if len(t) == 16:
        t = t + ":00"
    try:
        return datetime.strptime(t[:19], FMT_CANONICO)
    except ValueError:
        from deteccion_perfil import detectar_formato_fecha

        fmt = fmt_hint or detectar_formato_fecha(t)
        return parsear_fecha(t, fmt)


def _kw_desde_kwh(kwh: float, minutos: int) -> float:
    if minutos <= 0:
        minutos = 5
    return float(kwh) * (60.0 / float(minutos))


def demanda_pico_perfil(
    perfil: Path,
    columna: str = "KWH_REC",
) -> dict | None:
    """Encuentra el intervalo de máxima demanda (kW) en la columna indicada.

    Para intervalo de 5 min: kW = kWh × 12.
    """
    meta = inspeccionar_perfil(perfil)
    freq = int(meta.frecuencia_min or 5)
    if freq <= 0:
        freq = 5

    mejor_kw = -1.0
    mejor: dict | None = None
    n = 0

    with perfil.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return None
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos or columna.upper() not in campos:
            return None
        col_f = campos["FECHA"]
        col_v = campos[columna.upper()]
        fmt = getattr(meta, "formato_fecha", None)
        for row in reader:
            try:
                dt = _parse_dt(row.get(col_f) or "", fmt)
                kwh = float(row.get(col_v) or 0)
            except Exception:
                continue
            n += 1
            kw = _kw_desde_kwh(kwh, freq)
            if kw > mejor_kw:
                mejor_kw = kw
                dia = fecha_operativa(dt)
                mejor = {
                    "columna": columna.upper(),
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "dia": dia.isoformat(),
                    "hora": dt.strftime("%H:%M"),
                    "kwh_intervalo": round(kwh, 6),
                    "kw": round(kw, 3),
                    "frecuencia_min": freq,
                    "n_filas": 0,  # se rellena al final
                }

    if mejor is None:
        return None
    mejor["n_filas"] = n
    return mejor


def demanda_pico_consumo_real(perfil: Path) -> dict | None:
    """Pico de (KWH_REC + KWH_GEN − KWH_ENT) si existen las tres columnas."""
    meta = inspeccionar_perfil(perfil)
    freq = int(meta.frecuencia_min or 5)
    if freq <= 0:
        freq = 5
    energia = getattr(meta.columnas, "energia", {}) or {}
    if not all(c in energia for c in ("KWH_REC", "KWH_ENT", "KWH_GEN")):
        return None

    mejor_kw = -1.0
    mejor: dict | None = None
    n = 0
    with perfil.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return None
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        col_f = campos["FECHA"]
        col_r = campos["KWH_REC"]
        col_e = campos["KWH_ENT"]
        col_g = campos["KWH_GEN"]
        fmt = getattr(meta, "formato_fecha", None)
        for row in reader:
            try:
                dt = _parse_dt(row.get(col_f) or "", fmt)
                kwh = (
                    float(row.get(col_r) or 0)
                    + float(row.get(col_g) or 0)
                    - float(row.get(col_e) or 0)
                )
            except Exception:
                continue
            n += 1
            kw = _kw_desde_kwh(kwh, freq)
            if kw > mejor_kw:
                mejor_kw = kw
                dia = fecha_operativa(dt)
                mejor = {
                    "columna": "CONSUMO_REAL",
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "dia": dia.isoformat(),
                    "hora": dt.strftime("%H:%M"),
                    "kwh_intervalo": round(kwh, 6),
                    "kw": round(kw, 3),
                    "frecuencia_min": freq,
                    "n_filas": 0,
                }
    if mejor is None:
        return None
    mejor["n_filas"] = n
    return mejor
