"""Filtra un perfil cincominutal por rango de fechas operativas."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from deteccion_perfil import FMT_CANONICO, inspeccionar_perfil, parsear_fecha


def fecha_operativa(dt: datetime) -> date:
    """Día D = 00:05 D … 00:00 D+1 (el 00:00 cuenta para el día anterior)."""
    if dt.hour == 0 and dt.minute < 5:
        return (dt - timedelta(days=1)).date()
    return dt.date()


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


def rango_fechas_perfil(ruta: Path) -> tuple[date, date] | None:
    """Devuelve (fecha_min, fecha_max) operativa del perfil, o None si vacío."""
    meta = inspeccionar_perfil(ruta)
    minimo: date | None = None
    maximo: date | None = None
    with ruta.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return None
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos:
            return None
        col = campos["FECHA"]
        for row in reader:
            try:
                dt = _parse_dt(row[col], getattr(meta, "formato_fecha", None))
            except Exception:
                continue
            dia = fecha_operativa(dt)
            if minimo is None or dia < minimo:
                minimo = dia
            if maximo is None or dia > maximo:
                maximo = dia
    if minimo is None or maximo is None:
        return None
    return minimo, maximo


def filtrar_perfil_fechas(
    perfil: Path,
    fecha_desde: date | None,
    fecha_hasta: date | None,
) -> Path:
    """Escribe *_rango.csv con filas cuya fecha operativa está en [desde, hasta]."""
    if fecha_desde is None and fecha_hasta is None:
        return perfil

    meta = inspeccionar_perfil(perfil)
    out = perfil.with_name(f"{perfil.stem}_rango.csv")
    n_in = 0
    n_out = 0
    n_skip = 0
    with perfil.open(newline="", encoding="utf-8-sig") as fin, out.open(
        "w", newline="", encoding="utf-8-sig"
    ) as fout:
        reader = csv.DictReader(fin)
        if not reader.fieldnames:
            raise ValueError(f"Perfil sin encabezado: {perfil.name}")
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos:
            raise ValueError(f"Falta FECHA en {perfil.name}")
        col_fecha = campos["FECHA"]
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            n_in += 1
            try:
                dt = _parse_dt(row[col_fecha], getattr(meta, "formato_fecha", None))
            except Exception:
                n_skip += 1
                continue
            dia = fecha_operativa(dt)
            if fecha_desde is not None and dia < fecha_desde:
                continue
            if fecha_hasta is not None and dia > fecha_hasta:
                continue
            writer.writerow(row)
            n_out += 1

    if n_out == 0:
        raise ValueError(
            f"Ninguna fila en el rango "
            f"{fecha_desde or '...'} -> {fecha_hasta or '...'} "
            f"(perfil tenia {n_in:,} filas"
            + (f", {n_skip} invalidas" if n_skip else "")
            + ")."
        )
    print(
        f"  Filtro fechas {fecha_desde or '...'} -> {fecha_hasta or '...'}: "
        f"{n_out:,}/{n_in:,} filas -> {out.name}"
    )
    return out
