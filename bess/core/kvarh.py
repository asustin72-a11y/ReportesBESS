"""Columnas y agregación de kVArh por medidor."""

from __future__ import annotations

import pandas as pd

COLUMNAS_KVARH = ("KVARH_Q1", "KVARH_Q2", "KVARH_Q3", "KVARH_Q4")


def columnas_kvarh(df: pd.DataFrame) -> list[str]:
    return [c for c in COLUMNAS_KVARH if c in df.columns]


def normalizar_columnas_kvarh(df: pd.DataFrame) -> pd.DataFrame:
    for col in columnas_kvarh(df):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def columnas_kvarh_prefijo(prefijo: str) -> tuple[str, ...]:
    """Cuadrantes de kVArh: ION/IUSA2=Q1; BANCO legado=Q1+Q4."""
    if prefijo in ("ION", "IUSA2"):
        return ("KVARH_Q1",)
    if prefijo == "BANCO":
        return ("KVARH_Q1", "KVARH_Q4")
    return COLUMNAS_KVARH


def kvarh_total(df: pd.DataFrame, prefijo: str | None = None) -> pd.Series:
    cols = (
        [c for c in columnas_kvarh_prefijo(prefijo) if c in df.columns]
        if prefijo
        else columnas_kvarh(df)
    )
    if not cols:
        return pd.Series(0.0, index=df.index)
    return df[cols].sum(axis=1)
