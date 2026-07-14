"""Lectura, validación y persistencia de tarifas (DataFrame ↔ BD)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bess.config.constants import TIPOS_TARIFA
from bess.config.esquema_tarifa import ESQUEMA_DEFAULT, ESQUEMA_DIST, ESQUEMA_GDMTH, normalizar_esquema_tarifa
from bess.data.tariffs_db import ensure_tarifas_listo, guardar_tarifas_dict, leer_tarifas_dict
from bess.tariffs.loader import invalidar_cache_tarifas


def df_tarifas_plantilla() -> pd.DataFrame:
    filas = []
    for tipo in TIPOS_TARIFA:
        fila = {"Tarifa": tipo}
        for mes in range(1, 13):
            fila[str(mes)] = 0.0
        filas.append(fila)
    return pd.DataFrame(filas)


def leer_df_tarifas(esquema_id: str = ESQUEMA_DEFAULT) -> pd.DataFrame:
    """Tarifas como DataFrame editable (una fila por tipo × 12 meses)."""
    esquema = normalizar_esquema_tarifa(esquema_id)
    ensure_tarifas_listo()
    tarifas = leer_tarifas_dict(esquema)
    filas = []
    for tipo in TIPOS_TARIFA:
        fila = {"Tarifa": tipo}
        for mes in range(1, 13):
            fila[str(mes)] = float(tarifas.get(tipo, {}).get(mes, 0.0))
        filas.append(fila)
    return pd.DataFrame(filas)[["Tarifa"] + [str(m) for m in range(1, 13)]]


def validar_df_tarifas(df: pd.DataFrame | None) -> str | None:
    columnas_mes = [str(m) for m in range(1, 13)]
    if df is None or df.empty:
        return "No hay datos de tarifas."
    if "Tarifa" not in df.columns:
        return "Falta la columna Tarifa."
    faltantes = [c for c in columnas_mes if c not in df.columns]
    if faltantes:
        return f'Faltan columnas de mes: {", ".join(faltantes)}.'
    tipos = [str(t).strip() for t in df["Tarifa"].tolist()]
    if tipos != TIPOS_TARIFA:
        return f'Se requieren exactamente las filas: {", ".join(TIPOS_TARIFA)}.'
    for col in columnas_mes:
        valores = pd.to_numeric(df[col], errors="coerce")
        if valores.isna().any():
            return f"Valores no numéricos en el mes {col}."
        if (valores < 0).any():
            return f"Las tarifas del mes {col} no pueden ser negativas."
    return None


def guardar_df_tarifas(
    df: pd.DataFrame,
    esquema_id: str = ESQUEMA_DEFAULT,
) -> tuple[bool, str]:
    esquema = normalizar_esquema_tarifa(esquema_id)
    error = validar_df_tarifas(df)
    if error:
        return False, error
    tarifas: dict[str, dict[int, float]] = {}
    for _, row in df.iterrows():
        tipo = str(row["Tarifa"]).strip()
        tarifas[tipo] = {}
        for mes in range(1, 13):
            tarifas[tipo][mes] = round(
                float(pd.to_numeric(row[str(mes)], errors="coerce") or 0), 4
            )
    guardar_tarifas_dict(tarifas, esquema)
    invalidar_cache_tarifas()
    return True, f"base de datos ({esquema})"


def column_config_tarifas() -> dict:
    config = {
        "Tarifa": st.column_config.TextColumn("Tarifa", disabled=True, width="small"),
    }
    for mes in range(1, 13):
        config[str(mes)] = st.column_config.NumberColumn(
            f"M{mes}",
            min_value=0.0,
            format="%.4f",
            width="small",
        )
    return config
