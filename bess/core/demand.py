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

    Con intervalos de 5 min y ventana de 15 min, los dos primeros intervalos
    del mes (00:05 y 00:10) llevan **0**; el primer valor calculado es a las
    **00:15**. La serie es continua dentro del mes (no reinicia al cambiar
    periodo tarifario) — apta para gráficas.
    """
    ventana = ventana_min // intervalo_min
    tmp = pd.DataFrame({"kw": potencia_kw, "mes": mes_operativo})
    rodante = tmp.groupby("mes", group_keys=False)["kw"].transform(
        lambda s: s.rolling(window=ventana, min_periods=ventana).mean()
    )
    return rodante.fillna(0)


def mascara_valida_para_maximo(
    periodo: pd.Series,
    *,
    n_excluir: int = 2,
) -> pd.Series:
    """
    True donde la demanda rolada puede usarse para máximos por periodo.

    Excluye los ``n_excluir`` primeros intervalos de cada racha de PERIODO
    (con ventana 15 min = 3×5 min, los 2 primeros aún pueden mezclar la
    tarifa anterior en un rolling continuo).
    """
    p = periodo.copy()
    p = p.where(p.notna() & (p.astype(str).str.strip() != ""), other=pd.NA)
    prev = p.shift(1)
    nueva_racha = p.isna() | prev.isna() | p.ne(prev)
    racha = nueva_racha.cumsum()
    orden = racha.groupby(racha).cumcount()
    return p.notna() & (orden >= n_excluir)


def aplicar_mascara_demanda_maximo(
    demanda: pd.Series,
    periodo: pd.Series,
    *,
    n_excluir: int = 2,
) -> pd.Series:
    """Demanda rolada con NA en inicios de periodo (no cuentan para idxmax)."""
    valida = mascara_valida_para_maximo(periodo, n_excluir=n_excluir)
    out = pd.to_numeric(demanda, errors="coerce").where(valida)
    return out


def demanda_rodante_15min_por_periodo(
    potencia_kw: pd.Series,
    periodo: pd.Series,
    *,
    ventana_min: int = 15,
    intervalo_min: int = 5,
) -> pd.Series:
    """
    Media móvil 15 min reiniciada en cada cambio de periodo tarifario.

    Conservada por compatibilidad / pruebas. El flujo BESS publica la
    demanda con ``demanda_rodante_15min_por_mes`` y aísla TOU al detectar
    máximos vía ``mascara_valida_para_maximo``.
    """
    ventana = ventana_min // intervalo_min
    p = periodo.copy()
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
