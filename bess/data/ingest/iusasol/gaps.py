"""Relleno de slots cincuminutales omitidos por la API ISOL."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from bess.data.ingest.iusasol.to_csv import COLUMNAS_PERFIL

MEDIDORES_RELLENAR_MEDIANOCHE_API = frozenset({
    "BESS",
    "BANCO",
    "BESS_IUSA2",
    "GRANJA_IUSA2",
})

FUENTE_MEDIANOCHE_API: dict[str, str] = {
    "GRANJA_IUSA2": "farm_api",
}


def _fila_cero_medianoche(fecha: datetime) -> dict[str, Any]:
    fila = {col: 0.0 for col in COLUMNAS_PERFIL if col != "Fecha"}
    fila["Fecha"] = fecha
    return fila


def _detectar_extras_medianoche(ordenado: pd.DataFrame) -> list[dict]:
    extras: list[dict] = []
    fechas_vistas = set(pd.to_datetime(ordenado["Fecha"]))

    for i in range(1, len(ordenado)):
        prev = pd.Timestamp(ordenado.at[i - 1, "Fecha"]).to_pydatetime()
        curr = pd.Timestamp(ordenado.at[i, "Fecha"]).to_pydatetime()
        if (
            prev.hour == 23
            and prev.minute == 55
            and curr.hour == 0
            and curr.minute == 5
            and curr.date() > prev.date()
        ):
            esperada = datetime.combine(curr.date(), datetime.min.time())
            if esperada not in fechas_vistas:
                extras.append(_fila_cero_medianoche(esperada))
                fechas_vistas.add(esperada)

    return extras


def rellenar_slots_medianoche_api(
    df: pd.DataFrame,
    *,
    contexto_prev: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Inserta 00:00 con ceros si la API salta de 23:55 (día N) a 00:05 (día N+1).

    contexto_prev: última fila ya persistida antes del lote actual (sync incremental).
    No aplica a ION (Modbus): ese caso lo resuelve verify con salto opcional.
    """
    if df.empty:
        return df

    trabajo = df.sort_values("Fecha").reset_index(drop=True)
    if contexto_prev is not None and not contexto_prev.empty:
        trabajo = pd.concat(
            [contexto_prev.tail(1), trabajo],
            ignore_index=True,
        ).sort_values("Fecha").reset_index(drop=True)

    extras = _detectar_extras_medianoche(trabajo)
    if not extras:
        return df.sort_values("Fecha").reset_index(drop=True)

    completo = pd.concat(
        [trabajo, pd.DataFrame(extras)],
        ignore_index=True,
    ).sort_values("Fecha").reset_index(drop=True)

    min_fecha = pd.Timestamp(df["Fecha"].min())
    return completo[completo["Fecha"] >= min_fecha].reset_index(drop=True)


def filas_a_dataframe(filas: list) -> pd.DataFrame:
    """Convierte filas SQLite perfil_carga a DataFrame estándar."""
    if not filas:
        return pd.DataFrame(columns=COLUMNAS_PERFIL)
    registros = []
    for row in filas:
        registros.append({
            "Fecha": row["fecha"],
            "KWH_REC": row["kwh_rec"],
            "KWH_ENT": row["kwh_ent"],
            "KVARH_Q1": row["kvarh_q1"],
            "KVARH_Q2": row["kvarh_q2"],
            "KVARH_Q3": row["kvarh_q3"],
            "KVARH_Q4": row["kvarh_q4"],
        })
    df = pd.DataFrame(registros, columns=COLUMNAS_PERFIL)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    return df.dropna(subset=["Fecha"]).sort_values("Fecha").reset_index(drop=True)


def _registro_desde_fila(row: pd.Series) -> dict[str, Any]:
    fecha = row["Fecha"]
    fecha_txt = fecha.strftime("%Y-%m-%d %H:%M:%S") if hasattr(fecha, "strftime") else str(fecha)
    return {
        "fecha": fecha_txt,
        "kwh_rec": float(row["KWH_REC"] or 0),
        "kwh_ent": float(row["KWH_ENT"] or 0),
        "kvarh_q1": float(row["KVARH_Q1"] or 0),
        "kvarh_q2": float(row["KVARH_Q2"] or 0),
        "kvarh_q3": float(row["KVARH_Q3"] or 0),
        "kvarh_q4": float(row["KVARH_Q4"] or 0),
    }


def registros_slots_medianoche_faltantes(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Registros 00:00 que faltan en df pero la secuencia 23:55→00:05 los requiere."""
    if df.empty:
        return []
    orig_fechas = {pd.Timestamp(t) for t in df["Fecha"]}
    completo = rellenar_slots_medianoche_api(df)
    registros: list[dict[str, Any]] = []
    for _, row in completo.iterrows():
        if pd.Timestamp(row["Fecha"]) not in orig_fechas:
            registros.append(_registro_desde_fila(row))
    return registros


def fuente_medianoche_medidor(medidor_id: str) -> str:
    return FUENTE_MEDIANOCHE_API.get(medidor_id, "iusasol")


def persistir_slots_medianoche_bd(
    medidor_id: str,
    ruta_bd: Path,
    *,
    fuente: str | None = None,
) -> int:
    """
    Escanea el perfil completo en SQLite e inserta slots 00:00 faltantes.
    Idempotente: no duplica filas existentes.
    """
    from bess.data.ingest.ion import db

    if medidor_id not in MEDIDORES_RELLENAR_MEDIANOCHE_API:
        return 0

    fuente = fuente or fuente_medianoche_medidor(medidor_id)

    db.init_db(ruta_bd)
    with db.conectar_bd(ruta_bd) as conn:
        filas = conn.execute(
            """
            SELECT fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4
            FROM perfil_carga
            WHERE medidor_id = ?
            ORDER BY fecha
            """,
            (medidor_id,),
        ).fetchall()
        if not filas:
            return 0
        df = filas_a_dataframe(filas)
        registros = registros_slots_medianoche_faltantes(df)
        if not registros:
            return 0
        insertados = db.insertar_registros_si_ausentes(
            conn, medidor_id, registros, fuente=fuente,
        )
        conn.commit()
        return insertados


def contexto_previo_bd(
    medidor_id: str,
    ruta_bd: Path,
    antes_de: datetime | pd.Timestamp,
) -> pd.DataFrame | None:
    """Última fila en BD anterior a un timestamp (para sync incremental)."""
    from bess.data.ingest.ion import db

    if hasattr(antes_de, "strftime"):
        limite = antes_de.strftime("%Y-%m-%d %H:%M:%S")
    else:
        limite = str(antes_de)

    with db.conectar_bd(ruta_bd) as conn:
        fila = conn.execute(
            """
            SELECT fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4
            FROM perfil_carga
            WHERE medidor_id = ? AND fecha < ?
            ORDER BY fecha DESC
            LIMIT 1
            """,
            (medidor_id, limite),
        ).fetchone()
    if not fila:
        return None
    return filas_a_dataframe([fila])
