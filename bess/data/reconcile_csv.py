"""Reconciliación SQLite ↔ CSV Fuente (detecta cursores CSV congelados).

Compara por medidor y día calendario:
  SUM(kwh_rec), SUM(kwh_ent), COUNT(*) en perfil_carga
vs el CSV en ArchivosFuente del mismo medidor.

Caso típico (Aragón): BD con energía real y Fuente sin esas fechas (o en
cero) porque el export incremental solo reescribe ~1 día.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from bess.config.paths import RUTA_BD_PERFILES
from bess.data.ingest.ion import db
from bess.data.ingest.medidor_ids import destinos_export_bd

# Diferencia absoluta de kWh/día para marcar divergencia (ruido float).
UMBRAL_KWH = 0.05


@dataclass(frozen=True)
class DivergenciaDia:
    medidor_id: str
    dia: date
    sum_rec_bd: float
    sum_rec_csv: float
    sum_ent_bd: float
    sum_ent_csv: float
    filas_bd: int
    filas_csv: int
    ruta_csv: str

    @property
    def delta_rec(self) -> float:
        return self.sum_rec_bd - self.sum_rec_csv

    @property
    def delta_ent(self) -> float:
        return self.sum_ent_bd - self.sum_ent_csv

    @property
    def motivo(self) -> str:
        if self.filas_csv == 0 and self.filas_bd > 0:
            return "faltan en Fuente"
        if self.filas_bd == 0 and self.filas_csv > 0:
            return "solo en Fuente"
        if abs(self.delta_rec) > UMBRAL_KWH or abs(self.delta_ent) > UMBRAL_KWH:
            return "suma kWh distinta"
        return "divergencia"


def _agregar_bd(
    ruta_bd: Path,
    medidor_id: str,
    desde: date,
    hasta: date,
) -> dict[date, tuple[float, float, int]]:
    """dia -> (sum_rec, sum_ent, n)."""
    if not ruta_bd.is_file():
        return {}
    inicio = f"{desde.isoformat()} 00:00:00"
    fin = f"{hasta.isoformat()} 23:59:59"
    with db.conectar_bd(ruta_bd) as conn:
        conn.row_factory = sqlite3.Row
        filas = conn.execute(
            """
            SELECT date(fecha) AS d,
                   COALESCE(SUM(kwh_rec), 0) AS sum_rec,
                   COALESCE(SUM(kwh_ent), 0) AS sum_ent,
                   COUNT(*) AS n
            FROM perfil_carga
            WHERE medidor_id = ? AND fecha >= ? AND fecha <= ?
            GROUP BY date(fecha)
            ORDER BY d
            """,
            (medidor_id, inicio, fin),
        ).fetchall()
    out: dict[date, tuple[float, float, int]] = {}
    for row in filas:
        d = date.fromisoformat(str(row["d"]))
        out[d] = (float(row["sum_rec"]), float(row["sum_ent"]), int(row["n"]))
    return out


def _agregar_csv_fuente(
    ruta_csv: Path,
    desde: date,
    hasta: date,
) -> dict[date, tuple[float, float, int]]:
    """Lee ArchivosFuente (columna Fecha ISO o dayfirst)."""
    if not ruta_csv.is_file():
        return {}
    try:
        df = pd.read_csv(ruta_csv)
    except Exception:
        return {}
    if df.empty or "Fecha" not in df.columns:
        return {}

    fechas = pd.to_datetime(df["Fecha"], errors="coerce")
    if fechas.isna().all():
        fechas = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    df = df.copy()
    df["_dt"] = fechas
    df = df.dropna(subset=["_dt"])
    if df.empty:
        return {}

    df["KWH_REC"] = pd.to_numeric(df.get("KWH_REC", 0), errors="coerce").fillna(0)
    df["KWH_ENT"] = pd.to_numeric(df.get("KWH_ENT", 0), errors="coerce").fillna(0)
    mask = (df["_dt"].dt.date >= desde) & (df["_dt"].dt.date <= hasta)
    df = df.loc[mask]
    if df.empty:
        return {}

    g = df.groupby(df["_dt"].dt.date).agg(
        sum_rec=("KWH_REC", "sum"),
        sum_ent=("KWH_ENT", "sum"),
        n=("KWH_REC", "size"),
    )
    return {
        d: (float(r.sum_rec), float(r.sum_ent), int(r.n))
        for d, r in g.iterrows()
    }


def _es_divergencia(
    bd: tuple[float, float, int] | None,
    csv: tuple[float, float, int] | None,
) -> bool:
    br, be, bn = bd or (0.0, 0.0, 0)
    cr, ce, cn = csv or (0.0, 0.0, 0)
    if bn == 0 and cn == 0:
        return False
    # BD con energía y CSV ausente o vacío de filas
    if bn > 0 and cn == 0 and (br > UMBRAL_KWH or be > UMBRAL_KWH):
        return True
    # Sumas distintas
    if abs(br - cr) > UMBRAL_KWH or abs(be - ce) > UMBRAL_KWH:
        return True
    return False


def reconciliar_medidor(
    medidor_id: str,
    ruta_csv: Path,
    *,
    desde: date | None = None,
    hasta: date | None = None,
    ruta_bd: Path = RUTA_BD_PERFILES,
    dias: int = 30,
) -> list[DivergenciaDia]:
    """Divergencias día a día BD vs Fuente para un medidor."""
    hoy = date.today()
    hasta = hasta or hoy
    desde = desde or (hasta - timedelta(days=max(dias - 1, 0)))

    mapa_bd = _agregar_bd(ruta_bd, medidor_id, desde, hasta)
    mapa_csv = _agregar_csv_fuente(ruta_csv, desde, hasta)
    dias_set = sorted(set(mapa_bd) | set(mapa_csv))

    out: list[DivergenciaDia] = []
    for d in dias_set:
        bd = mapa_bd.get(d)
        csv = mapa_csv.get(d)
        if not _es_divergencia(bd, csv):
            continue
        br, be, bn = bd or (0.0, 0.0, 0)
        cr, ce, cn = csv or (0.0, 0.0, 0)
        out.append(
            DivergenciaDia(
                medidor_id=medidor_id,
                dia=d,
                sum_rec_bd=br,
                sum_rec_csv=cr,
                sum_ent_bd=be,
                sum_ent_csv=ce,
                filas_bd=bn,
                filas_csv=cn,
                ruta_csv=str(ruta_csv),
            )
        )
    return out


def reconciliar_todos(
    *,
    desde: date | None = None,
    hasta: date | None = None,
    dias: int = 30,
    ruta_bd: Path = RUTA_BD_PERFILES,
    solo_medidores: list[str] | None = None,
) -> list[DivergenciaDia]:
    """Recorre todos los destinos de exportación."""
    permitidos = {m for m in solo_medidores} if solo_medidores else None
    resultado: list[DivergenciaDia] = []
    for medidor_id, ruta_csv in destinos_export_bd(ruta_bd):
        if permitidos is not None and medidor_id not in permitidos:
            continue
        resultado.extend(
            reconciliar_medidor(
                medidor_id,
                ruta_csv,
                desde=desde,
                hasta=hasta,
                ruta_bd=ruta_bd,
                dias=dias,
            )
        )
    return resultado


def resumen_por_medidor(divergencias: list[DivergenciaDia]) -> list[dict]:
    """Una fila por medidor con conteo de días divergentes y deltas."""
    por: dict[str, list[DivergenciaDia]] = {}
    for d in divergencias:
        por.setdefault(d.medidor_id, []).append(d)
    filas = []
    for medidor_id, items in sorted(por.items()):
        filas.append(
            {
                "medidor_id": medidor_id,
                "dias_divergentes": len(items),
                "primer_dia": min(i.dia for i in items).isoformat(),
                "ultimo_dia": max(i.dia for i in items).isoformat(),
                "delta_rec_total": round(sum(i.delta_rec for i in items), 3),
                "delta_ent_total": round(sum(i.delta_ent for i in items), 3),
                "motivos": ", ".join(sorted({i.motivo for i in items})),
                "ruta_csv": items[0].ruta_csv,
            }
        )
    return filas


def divergencias_a_filas(divergencias: list[DivergenciaDia]) -> list[dict]:
    return [
        {
            "Medidor": d.medidor_id,
            "Día": d.dia.isoformat(),
            "Motivo": d.motivo,
            "REC BD": round(d.sum_rec_bd, 3),
            "REC Fuente": round(d.sum_rec_csv, 3),
            "Δ REC": round(d.delta_rec, 3),
            "ENT BD": round(d.sum_ent_bd, 3),
            "ENT Fuente": round(d.sum_ent_csv, 3),
            "Δ ENT": round(d.delta_ent, 3),
            "Filas BD": d.filas_bd,
            "Filas Fuente": d.filas_csv,
        }
        for d in divergencias
    ]
