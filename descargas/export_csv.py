"""Conversión de perfiles API → CSV (bytes utf-8-sig, CRLF)."""

from __future__ import annotations

import csv
import io
from typing import Any

from bess.data.ingest.granja.farm_client import kw_desde_perfil
from bess.data.ingest.iusasol.to_csv import perfil_json_a_csv


def csv_isol_bytes(perfil: Any) -> bytes:
    """ISOL Profiles/Gral → CSV BESS (Fecha, KWH_REC, …)."""
    texto = perfil_json_a_csv(perfil)
    return ("\ufeff" + texto).encode("utf-8")


def csv_porteo_bytes(perfil: Any) -> bytes:
    """Porteo Meter/Profiles: mismo layout de canales que ISOL (probe 2026-07-30)."""
    if isinstance(perfil, list):
        perfil = {"profiles": perfil}
    return csv_isol_bytes(perfil)


def csv_farm_bytes(perfiles: list[dict]) -> bytes:
    """Farm profiles → Fecha,kwh_rec (canal 0)."""
    filas = kw_desde_perfil(perfiles)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["Fecha", "kwh_rec"])
    for fecha, kw in filas:
        writer.writerow([fecha, kw])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def slug_medidor(etiqueta: str, idcode: str) -> str:
    base = (etiqueta or idcode or "medidor").strip()
    limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
    limpio = limpio.strip("_") or "medidor"
    return limpio[:80]
