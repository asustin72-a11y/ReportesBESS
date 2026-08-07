"""Ajustes previos al pipeline: multiplicador e inversión de canales."""

from __future__ import annotations

import csv
from pathlib import Path


def _columna(fieldnames: list[str], nombre: str) -> str | None:
    alvo = nombre.strip().upper()
    for c in fieldnames:
        if c.strip().upper() == alvo:
            return c
    return None


def aplicar_multiplicador(ruta: Path, factor: float) -> Path:
    """Reescribe `ruta` multiplicando todas las columnas numéricas (excepto FECHA).

    Si factor ≈ 1, no modifica el archivo. Devuelve la misma ruta.
    """
    if abs(factor - 1.0) < 1e-15:
        return ruta
    if factor < 0:
        raise ValueError(f"Multiplicador inválido: {factor}")

    with ruta.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"Perfil sin encabezado: {ruta.name}")
        fieldnames = list(reader.fieldnames)
        filas = list(reader)

    col_fecha = _columna(fieldnames, "FECHA")

    out_rows: list[dict[str, str]] = []
    for row in filas:
        nueva = dict(row)
        for col, raw in row.items():
            if col_fecha is not None and col == col_fecha:
                continue
            texto = (raw or "").strip()
            if not texto:
                continue
            try:
                val = float(texto.replace(",", ""))
            except ValueError:
                continue
            nueva[col] = f"{val * factor:.10g}"
        out_rows.append(nueva)

    with ruta.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)
    return ruta


def invertir_canales_rec_ent(ruta: Path) -> Path:
    """Intercambia los valores de KWH_REC y KWH_ENT en cada fila.

    Si falta alguna de las dos columnas, no modifica el archivo.
    """
    with ruta.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"Perfil sin encabezado: {ruta.name}")
        fieldnames = list(reader.fieldnames)
        filas = list(reader)

    col_rec = _columna(fieldnames, "KWH_REC")
    col_ent = _columna(fieldnames, "KWH_ENT")
    if col_rec is None or col_ent is None:
        return ruta

    for row in filas:
        row[col_rec], row[col_ent] = row.get(col_ent, ""), row.get(col_rec, "")

    with ruta.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filas)
    return ruta
