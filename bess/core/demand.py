"""Demanda rodante CFE (ventana móvil 15 min)."""

from __future__ import annotations

import pandas as pd


def demanda_rodante_15min_por_mes(
    potencia_kw: pd.Series,
    mes_operativo: pd.Series,
    *,
    ventana_min: int = 15,
    intervalo_min: int = 5,
) -> pd.Series:
    """
    Media móvil de demanda (kW) reiniciada al inicio de cada mes operativo.

    Conservada por compatibilidad; el flujo BESS usa
    ``demanda_rodante_15min_por_periodo`` (aislamiento TOU / guía ANSI).
    """
    ventana = ventana_min // intervalo_min
    tmp = pd.DataFrame({"kw": potencia_kw, "mes": mes_operativo})
    rodante = tmp.groupby("mes", group_keys=False)["kw"].transform(
        lambda s: s.rolling(window=ventana, min_periods=ventana).mean()
    )
    return rodante.fillna(0)


def demanda_rodante_15min_por_periodo(
    potencia_kw: pd.Series,
    periodo: pd.Series,
    *,
    ventana_min: int = 15,
    intervalo_min: int = 5,
) -> pd.Series:
    """
    Media móvil 15 min reiniciada en cada cambio de periodo tarifario
    (modo conservador / aislamiento TOU).

    No mezcla subintervalos de tarifas distintas. Hasta completar N
    intervalos consecutivos de la misma tarifa el valor es 0
    (con 5 min y ventana 15 min: los 2 primeros de cada racha → 0).
    """
    ventana = ventana_min // intervalo_min
    p = periodo.copy()
    # Normalizar: NaN / vacío rompen racha
    p = p.where(p.notna() & (p.astype(str).str.strip() != ""), other=pd.NA)
    prev = p.shift(1)
    nueva_racha = p.isna() | prev.isna() | p.ne(prev)
    racha = nueva_racha.cumsum()
    tmp = pd.DataFrame(
        {"kw": pd.to_numeric(potencia_kw, errors="coerce"), "racha": racha}
    )
    rodante = tmp.groupby("racha", group_keys=False)["kw"].transform(
        lambda s: s.rolling(window=ventana, min_periods=ventana).mean()
    )
    return rodante.where(p.notna(), 0).fillna(0)
