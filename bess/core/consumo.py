"""Energía de consumo del medidor de facturación (IUSA 2: KWH_NETO)."""

from __future__ import annotations

import pandas as pd

from bess.config.subestaciones import medidor_consumo_por_prefijo


def usa_consumo_neto(prefijo: str) -> bool:
    med = medidor_consumo_por_prefijo(prefijo)
    return bool(med and med.usa_consumo_neto)


def kwh_neto_consumo(df: pd.DataFrame, prefijo: str) -> pd.Series:
    """
    kWh de consumo ION para energía y demanda.

    - IUSA 2: usa KWH_NETO si existe; si no max(0, REC − ENT) con columnas
      estándar (KWH_REC/ENT) o con sufijo (KWH_REC_IUSA2 / KWH_ENT_IUSA2).
    - IUSA 1 / Banco: KWH_REC (o KWH_REC_{prefijo}).
    """
    if usa_consumo_neto(prefijo):
        if "KWH_NETO" in df.columns:
            return pd.to_numeric(df["KWH_NETO"], errors="coerce").fillna(0)
        col_rec = f"KWH_REC_{prefijo}"
        col_ent = f"KWH_ENT_{prefijo}"
        if col_rec in df.columns and col_ent in df.columns:
            rec = pd.to_numeric(df[col_rec], errors="coerce").fillna(0)
            ent = pd.to_numeric(df[col_ent], errors="coerce").fillna(0)
            return (rec - ent).clip(lower=0)
        if "KWH_REC" in df.columns and "KWH_ENT" in df.columns:
            rec = pd.to_numeric(df["KWH_REC"], errors="coerce").fillna(0)
            ent = pd.to_numeric(df["KWH_ENT"], errors="coerce").fillna(0)
            return (rec - ent).clip(lower=0)
        return pd.Series(0.0, index=df.index)

    col = f"KWH_REC_{prefijo}" if f"KWH_REC_{prefijo}" in df.columns else "KWH_REC"
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


# Alias usado en reportes / gráficas (misma función).
kwh_ion_para_calculo = kwh_neto_consumo


def potencia_ion_con_bess_kw(df: pd.DataFrame, prefijo: str) -> pd.Series:
    return kwh_neto_consumo(df, prefijo) * 12


def potencia_ion_sin_bess_kw(df: pd.DataFrame, prefijo: str) -> pd.Series:
    kwh_ion = kwh_neto_consumo(df, prefijo)
    bess_rec = pd.to_numeric(df["KWH_REC_BESS"], errors="coerce").fillna(0)
    bess_ent = pd.to_numeric(df["KWH_ENT_BESS"], errors="coerce").fillna(0)
    return (kwh_ion - bess_rec + bess_ent) * 12


def columna_consumo_rec(prefijo: str) -> str:
    return "KWH_NETO" if usa_consumo_neto(prefijo) else "KWH_REC"


def enriquecer_consumo_neto(df: pd.DataFrame, prefijo: str) -> pd.DataFrame:
    """Añade KWH_NETO = max(0, KWH_REC - KWH_ENT); conserva REC y ENT originales."""
    if not usa_consumo_neto(prefijo):
        return df
    out = df.copy()
    out["KWH_NETO"] = kwh_neto_consumo(out, prefijo)
    return out


def orientar_kwh_consumo(df: pd.DataFrame, *, forzar: bool = False) -> pd.DataFrame:
    """Intercambia KWH_REC ↔ KWH_ENT (solo al generar Banco1_Filtrado)."""
    if not forzar:
        return df

    out = df.copy()
    out["KWH_REC"] = pd.to_numeric(df["KWH_ENT"], errors="coerce").fillna(0)
    out["KWH_ENT"] = pd.to_numeric(df["KWH_REC"], errors="coerce").fillna(0)
    return out


def df_consumo_para_calculo(df: pd.DataFrame, prefijo: str) -> pd.DataFrame:
    """
    DataFrame para combinar con BESS: KWH_REC pasa a ser el neto (REC-ENT),
    equivalente al único KWH_REC de IUSA 1.
    """
    if not usa_consumo_neto(prefijo):
        return df
    out = enriquecer_consumo_neto(df, prefijo).copy()
    out["KWH_REC"] = out["KWH_NETO"]
    out["KWH_ENT"] = 0.0
    return out


__all__ = [
    "columna_consumo_rec",
    "df_consumo_para_calculo",
    "enriquecer_consumo_neto",
    "kwh_ion_para_calculo",
    "kwh_neto_consumo",
    "orientar_kwh_consumo",
    "potencia_ion_con_bess_kw",
    "potencia_ion_sin_bess_kw",
    "usa_consumo_neto",
]
