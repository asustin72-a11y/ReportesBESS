"""Energía de consumo por periodo tarifario (netmetering vs neteo por intervalo)."""

from __future__ import annotations

import pandas as pd

from bess.config.esquema_tarifa import usa_netmetering

PERIODOS = ("base", "intermedio", "punta")

_COL_REC = {
    "base": "BASE_REC",
    "intermedio": "INTERMEDIO_REC",
    "punta": "PUNTA_REC",
}
_COL_ENT = {
    "base": "BASE_ENT",
    "intermedio": "INTERMEDIO_ENT",
    "punta": "PUNTA_ENT",
}
_COL_SIN = {
    "base": "BASE_REC_SIN_BESS",
    "intermedio": "INTERMEDIO_REC_SIN_BESS",
    "punta": "PUNTA_REC_SIN_BESS",
}
_COL_REC_ACUM = {p: f"{_COL_REC[p]}_ACUM" for p in PERIODOS}
_COL_ENT_ACUM = {p: f"{_COL_ENT[p]}_ACUM" for p in PERIODOS}


def _num(val) -> float:
    return float(pd.to_numeric(val, errors="coerce") if val is not None else 0) or 0.0


def kwh_consumo_periodo_fila(
    fila,
    periodo: str,
    esquema_id: str,
    *,
    con_bess: bool = True,
) -> float:
    """kWh facturables del periodo en una fila diaria o acumulada."""
    if con_bess and usa_netmetering(esquema_id):
        return _num(fila.get(_COL_REC[periodo], 0)) - _num(fila.get(_COL_ENT[periodo], 0))
    col = _COL_REC[periodo] if con_bess else _COL_SIN[periodo]
    return _num(fila.get(col, 0))


def kwh_consumo_acum_periodo_fila(fila, periodo: str, esquema_id: str) -> float:
    """kWh acumulados del mes al día (consumo con BESS)."""
    if usa_netmetering(esquema_id):
        rec = _num(fila.get(_COL_REC_ACUM[periodo], 0))
        ent = _num(fila.get(_COL_ENT_ACUM[periodo], 0))
        return rec - ent
    return _num(fila.get(_COL_REC_ACUM[periodo], 0))


def kwh_rec_acum_periodo_fila(fila, periodo: str) -> float:
    """kWh REC acumulados del mes al día (brutos, netmetering)."""
    return _num(fila.get(_COL_REC_ACUM[periodo], 0))


def kwh_ent_acum_periodo_fila(fila, periodo: str) -> float:
    """kWh ENT acumulados del mes al día (brutos, netmetering)."""
    return _num(fila.get(_COL_ENT_ACUM[periodo], 0))


def sumar_rec_por_periodo_df(df: pd.DataFrame) -> dict[str, float]:
    """Suma KWH_REC bruto por periodo sobre filas diarias."""
    resultado = {p: 0.0 for p in PERIODOS}
    if df is None or df.empty:
        return resultado
    for _, fila in df.iterrows():
        for p in PERIODOS:
            resultado[p] += _num(fila.get(_COL_REC[p], 0))
    return resultado


def sumar_ent_por_periodo_df(df: pd.DataFrame) -> dict[str, float]:
    """Suma KWH_ENT bruto por periodo sobre filas diarias."""
    resultado = {p: 0.0 for p in PERIODOS}
    if df is None or df.empty:
        return resultado
    for _, fila in df.iterrows():
        for p in PERIODOS:
            resultado[p] += _num(fila.get(_COL_ENT[p], 0))
    return resultado


def sumar_consumo_por_periodo_df(
    df: pd.DataFrame,
    esquema_id: str,
    *,
    con_bess: bool = True,
) -> dict[str, float]:
    """Suma kWh de consumo por periodo sobre filas diarias."""
    resultado = {p: 0.0 for p in PERIODOS}
    if df is None or df.empty:
        return resultado
    for _, fila in df.iterrows():
        for p in PERIODOS:
            resultado[p] += kwh_consumo_periodo_fila(fila, p, esquema_id, con_bess=con_bess)
    return resultado


def total_consumo_fila(fila, esquema_id: str, *, con_bess: bool = True) -> float:
    return sum(
        kwh_consumo_periodo_fila(fila, p, esquema_id, con_bess=con_bess)
        for p in PERIODOS
    )


def agregar_columnas_total_consumo(df: pd.DataFrame, esquema_id: str) -> pd.DataFrame:
    """Añade TOTAL_CON y TOTAL_SIN (si aplica) a un DataFrame diario."""
    out = df.copy()
    out["TOTAL_CON"] = out.apply(
        lambda row: total_consumo_fila(row, esquema_id, con_bess=True),
        axis=1,
    )
    if _COL_SIN["base"] in out.columns:
        out["TOTAL_SIN"] = out.apply(
            lambda row: total_consumo_fila(row, esquema_id, con_bess=False),
            axis=1,
        )
    return out


def df_energia_para_visualizacion(df: pd.DataFrame, esquema_id: str) -> pd.DataFrame:
    """
    Copia para gráficas/tablas UI: en netmetering, BASE_* muestra consumo (REC−ENT).
    El CSV conserva REC y ENT brutos.
    """
    out = df.copy()
    if usa_netmetering(esquema_id):
        for p in PERIODOS:
            rec = pd.to_numeric(out[_COL_REC[p]], errors="coerce").fillna(0)
            ent = pd.to_numeric(out[_COL_ENT[p]], errors="coerce").fillna(0)
            out[_COL_REC[p]] = rec - ent
    out["TOTAL_CON"] = sum(
        pd.to_numeric(out[_COL_REC[p]], errors="coerce").fillna(0) for p in PERIODOS
    )
    if _COL_SIN["base"] in out.columns:
        out["TOTAL_SIN"] = sum(
            pd.to_numeric(out[_COL_SIN[p]], errors="coerce").fillna(0) for p in PERIODOS
        )
    return out
