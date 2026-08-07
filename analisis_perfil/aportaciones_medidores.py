"""Aportación energética por medidor (perfil) al total del periodo."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from filtrar_perfil import _parse_dt, fecha_operativa
from deteccion_perfil import inspeccionar_perfil


def total_columna_perfil(
    ruta: Path,
    columna: str,
    *,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> float:
    """Suma una columna del perfil cincominutal (opcionalmente filtrada por día operativo)."""
    meta = inspeccionar_perfil(ruta)
    total = 0.0
    with ruta.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return 0.0
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos or columna.upper() not in campos:
            return 0.0
        col_f = campos["FECHA"]
        col_v = campos[columna.upper()]
        fmt = getattr(meta, "formato_fecha", None)
        for row in reader:
            if fecha_desde is not None or fecha_hasta is not None:
                try:
                    dt = _parse_dt(row[col_f], fmt)
                    dia = fecha_operativa(dt)
                except Exception:
                    continue
                if fecha_desde is not None and dia < fecha_desde:
                    continue
                if fecha_hasta is not None and dia > fecha_hasta:
                    continue
            try:
                total += float((row.get(col_v) or "0").replace(",", "") or 0)
            except ValueError:
                continue
    return total


def aportaciones_medidores(
    archivos: list[Path],
    columna: str,
    *,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> list[dict]:
    """Lista {nombre, kwh, pct} por archivo; solo tiene sentido con ≥2 archivos."""
    if len(archivos) < 2:
        return []
    filas: list[dict] = []
    for path in archivos:
        kwh = total_columna_perfil(
            path,
            columna,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )
        filas.append({"nombre": path.name, "kwh": float(kwh)})
    total = sum(f["kwh"] for f in filas)
    for f in filas:
        f["pct"] = (100.0 * f["kwh"] / total) if total > 1e-12 else 0.0
    filas.sort(key=lambda x: x["kwh"], reverse=True)
    return filas
