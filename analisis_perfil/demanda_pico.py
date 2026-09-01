"""Demanda máxima a partir del perfil cincominutal (kWh → kW)."""

from __future__ import annotations

import csv
from collections import deque
from datetime import datetime
from pathlib import Path

from deteccion_perfil import FMT_CANONICO, inspeccionar_perfil, parsear_fecha
from filtrar_perfil import fecha_operativa
from servicio_config import PERIODOS

# Tarifas horarias CFE donde la demanda entra en el cálculo de capacidad.
ESQUEMAS_CON_DEMANDA = frozenset({"DIST", "GDMTH"})


def esquema_requiere_demanda(esquema: str | None) -> bool:
    return (esquema or "").strip().upper() in ESQUEMAS_CON_DEMANDA


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


def _periodo_por_timestamp(esquema: str, dt: datetime) -> str:
    clave = (esquema or "DIST").strip().upper()
    if clave == "GDMTH":
        from energia_por_horario_gdmth import periodo_por_timestamp
    else:
        from energia_por_horario_dist import periodo_por_timestamp
    return periodo_por_timestamp(dt)


def _pico_dict(
    *,
    columna: str,
    dt: datetime,
    kwh: float,
    kw: float,
    freq: int,
    periodo: str | None = None,
) -> dict:
    dia = fecha_operativa(dt)
    out = {
        "columna": columna,
        "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "dia": dia.isoformat(),
        "hora": dt.strftime("%H:%M"),
        "kwh_intervalo": round(kwh, 6),
        "kw": round(kw, 3),
        "frecuencia_min": freq,
    }
    if periodo is not None:
        out["periodo"] = periodo
    return out


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
                mejor = _pico_dict(
                    columna=columna.upper(),
                    dt=dt,
                    kwh=kwh,
                    kw=kw,
                    freq=freq,
                )

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
                mejor = _pico_dict(
                    columna="CONSUMO_REAL",
                    dt=dt,
                    kwh=kwh,
                    kw=kw,
                    freq=freq,
                )
    if mejor is None:
        return None
    mejor["n_filas"] = n
    return mejor


def _leer_serie_kw(
    perfil: Path,
    *,
    modo: str,
    freq: int,
    fmt: str | None,
) -> list[tuple[datetime, float, float]] | None:
    """Lista (timestamp, kwh_intervalo, kw_instantaneo) ordenada del CSV."""
    with perfil.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return None
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos:
            return None
        col_f = campos["FECHA"]
        if modo == "CONSUMO_REAL":
            for req in ("KWH_REC", "KWH_ENT", "KWH_GEN"):
                if req not in campos:
                    return None
            col_r, col_e, col_g = campos["KWH_REC"], campos["KWH_ENT"], campos["KWH_GEN"]

            def _kwh(row: dict) -> float:
                return (
                    float(row.get(col_r) or 0)
                    + float(row.get(col_g) or 0)
                    - float(row.get(col_e) or 0)
                )
        else:
            if modo not in campos:
                return None
            col_v = campos[modo]

            def _kwh(row: dict) -> float:
                return float(row.get(col_v) or 0)

        serie: list[tuple[datetime, float, float]] = []
        for row in reader:
            try:
                dt = _parse_dt(row.get(col_f) or "", fmt)
                kwh = _kwh(row)
            except Exception:
                continue
            serie.append((dt, kwh, _kw_desde_kwh(kwh, freq)))
    return serie or None


def demanda_maxima_por_periodo(
    perfil: Path,
    esquema: str,
    *,
    columna: str = "KWH_REC",
    ventana_min: int = 15,
    n_excluir_inicio_periodo: int = 2,
) -> dict | None:
    """Demanda máxima por periodo tarifario (Base / Intermedio / Punta).

    Usa media rodante CFE de ``ventana_min`` (15 min) reiniciada al mes
    operativo, y excluye los ``n_excluir_inicio_periodo`` primeros intervalos
    de cada racha de periodo (misma lógica que BESS).
    """
    if not esquema_requiere_demanda(esquema):
        return None

    meta = inspeccionar_perfil(perfil)
    freq = int(meta.frecuencia_min or 5)
    if freq <= 0:
        freq = 5
    ventana = max(1, int(ventana_min // freq))
    modo = (columna or "KWH_REC").strip().upper()
    fmt = getattr(meta, "formato_fecha", None)
    serie = _leer_serie_kw(perfil, modo=modo, freq=freq, fmt=fmt)
    if not serie:
        return None

    buffer: deque[float] = deque(maxlen=ventana)
    mes_act: tuple[int, int] | None = None
    prev_periodo: str | None = None
    orden_racha = 0
    mejores: dict[str, dict] = {}
    n_validos = 0

    for dt, kwh, kw_inst in serie:
        dia = fecha_operativa(dt)
        mes = (dia.year, dia.month)
        if mes != mes_act:
            buffer.clear()
            mes_act = mes
            prev_periodo = None
            orden_racha = 0

        buffer.append(kw_inst)
        if len(buffer) < ventana:
            dem = 0.0
        else:
            dem = sum(buffer) / float(ventana)

        periodo = _periodo_por_timestamp(esquema, dt)
        if periodo != prev_periodo:
            prev_periodo = periodo
            orden_racha = 0
        else:
            orden_racha += 1

        if dem <= 0 or orden_racha < n_excluir_inicio_periodo:
            continue
        n_validos += 1
        actual = mejores.get(periodo)
        if actual is None or dem > float(actual["kw"]):
            mejores[periodo] = _pico_dict(
                columna=modo,
                dt=dt,
                kwh=kwh,
                kw=dem,
                freq=freq,
                periodo=periodo,
            )

    por_periodo = {p: mejores.get(p) for p in PERIODOS}
    if not any(por_periodo.values()):
        return None

    global_max = max(
        (p for p in por_periodo.values() if p is not None),
        key=lambda x: float(x["kw"]),
    )
    return {
        "esquema": (esquema or "").strip().upper(),
        "metodo": f"rodante_{ventana_min}min",
        "ventana_min": ventana_min,
        "frecuencia_min": freq,
        "columna": modo,
        "n_intervalos_validos": n_validos,
        "por_periodo": por_periodo,
        "max_global_periodos": global_max,
    }
