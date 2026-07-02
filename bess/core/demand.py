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

    Con intervalos de 5 min y ventana de 15 min, los dos primeros intervalos del mes
    (00:05 y 00:10) llevan **0**; el primer valor calculado es a las **00:15**.
    """
    ventana = ventana_min // intervalo_min
    tmp = pd.DataFrame({"kw": potencia_kw, "mes": mes_operativo})
    rodante = tmp.groupby("mes", group_keys=False)["kw"].transform(
        lambda s: s.rolling(window=ventana, min_periods=ventana).mean()
    )
    return rodante.fillna(0)
