"""Perfil cincominutal de un día (drill-down desde Energía Entregada)."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path


def fecha_operativa(dt: datetime):
    """Día D = 00:05 D … 00:00 D+1 (el 00:00 cuenta para el día anterior)."""
    if dt.hour == 0 and dt.minute < 5:
        return (dt - timedelta(days=1)).date()
    return dt.date()


def inferir_perfil_cincominutal(diario: Path, job: Path | None = None) -> Path | None:
    """Localiza el CSV cincominutal a partir del diario o de la carpeta de trabajo."""
    stem = diario.stem
    for suf in (
        "_gdmth_energia_por_dia",
        "_t01_energia_por_dia",
        "_energia_por_dia",
    ):
        if stem.endswith(suf):
            base = stem[: -len(suf)]
            cand = diario.with_name(f"{base}.csv")
            if cand.is_file():
                return cand
    if job and job.is_dir():
        preferidos: list[Path] = []
        for p in sorted(job.glob("*.csv")):
            n = p.name.lower()
            if any(
                x in n
                for x in (
                    "energia_por",
                    "consumo_tipico",
                    "perfil_tipico",
                    "grafica",
                )
            ):
                continue
            if n.endswith("_rango.csv") or "_bidi_" in n or n.endswith(
                ("_suma.csv", "_bidireccional.csv")
            ):
                preferidos.append(p)
        if preferidos:
            for p in preferidos:
                if p.name.lower().endswith("_rango.csv"):
                    return p
            return preferidos[0]
    return None


def puntos_perfil_dia(
    perfil: Path,
    dia: str,
    columna: str = "KWH_REC",
) -> tuple[list[str], list[float]]:
    """Devuelve (horas HH:MM, valores) del día operativo indicado (YYYY-MM-DD).

    columna especial CONSUMO_REAL = KWH_REC + KWH_GEN − KWH_ENT.
    """
    from deteccion_perfil import inspeccionar_perfil

    meta = inspeccionar_perfil(perfil)
    xs: list[str] = []
    ys: list[float] = []
    with perfil.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return xs, ys
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos:
            return xs, ys
        col_f = campos["FECHA"]
        usar_real = columna.upper() == "CONSUMO_REAL"
        if usar_real:
            if "KWH_REC" not in campos or "KWH_ENT" not in campos:
                return xs, ys
            tiene_gen = "KWH_GEN" in campos
        elif columna.upper() not in campos:
            return xs, ys
        fmt = getattr(meta, "formato_fecha", None)
        pares: list[tuple[str, float]] = []
        for row in reader:
            texto = (row.get(col_f) or "").strip()
            if not texto:
                continue
            try:
                t = texto.replace("T", " ", 1)
                if len(t) == 16:
                    t += ":00"
                try:
                    dt = datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    from deteccion_perfil import detectar_formato_fecha, parsear_fecha

                    dt = parsear_fecha(t, fmt or detectar_formato_fecha(t))
                if fecha_operativa(dt).isoformat() != dia:
                    continue
                if usar_real:
                    val = float(row.get(campos["KWH_REC"]) or 0) - float(
                        row.get(campos["KWH_ENT"]) or 0
                    )
                    if tiene_gen:
                        val += float(row.get(campos["KWH_GEN"]) or 0)
                else:
                    val = float(row.get(campos[columna.upper()]) or 0)
                pares.append((dt.strftime("%H:%M"), val))
            except Exception:
                continue
        pares.sort(key=lambda p: p[0])
        xs = [p[0] for p in pares]
        ys = [p[1] for p in pares]
    return xs, ys
