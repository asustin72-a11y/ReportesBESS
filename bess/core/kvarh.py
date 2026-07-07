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
    """Cuadrantes de kVArh según reglas del tipo de medidor en catálogo."""
    from bess.config.catalog import obtener_catalogo
    from bess.config.subestaciones import medidor_consumo_por_nombre

    med = medidor_consumo_por_nombre(prefijo)
    if not med:
        return COLUMNAS_KVARH
    cat = obtener_catalogo()
    m_cat = cat.medidor_por_nombre(med.nombre)
    if not m_cat:
        return COLUMNAS_KVARH
    reglas = cat.reglas_tipo(m_cat.tipo_medidor)
    if not reglas:
        return COLUMNAS_KVARH
    if reglas.reactivos == 1:
        return ("KVARH_Q1",)
    if reglas.reactivos == 2:
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
