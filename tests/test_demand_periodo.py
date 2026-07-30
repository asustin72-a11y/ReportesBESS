"""Demanda rodante 15 min: reinicio por periodo tarifario."""

from __future__ import annotations

import pandas as pd

from bess.core.demand import (
    demanda_rodante_15min_por_mes,
    demanda_rodante_15min_por_periodo,
)


def test_reinicio_al_cambiar_periodo_primeros_dos_en_cero():
    kw = pd.Series([12.0] * 9)
    periodo = pd.Series(
        ["Base", "Base", "Base", "Punta", "Punta", "Punta", "Base", "Base", "Base"]
    )
    dem = demanda_rodante_15min_por_periodo(kw, periodo)
    # Base: 0, 0, 12
    assert list(dem.iloc[:3]) == [0.0, 0.0, 12.0]
    # Punta (reset): 0, 0, 12
    assert list(dem.iloc[3:6]) == [0.0, 0.0, 12.0]
    # Base otra vez (reset): 0, 0, 12
    assert list(dem.iloc[6:9]) == [0.0, 0.0, 12.0]


def test_no_mezcla_tarifas_en_el_borde():
    # Últimos de Intermedio altos + primeros de Punta: no deben promediarse juntos
    kw = pd.Series([3.0, 3.0, 3.0, 30.0, 30.0, 30.0])
    periodo = pd.Series(
        ["Intermedio", "Intermedio", "Intermedio", "Punta", "Punta", "Punta"]
    )
    dem = demanda_rodante_15min_por_periodo(kw, periodo)
    assert dem.iloc[2] == 3.0
    assert dem.iloc[3] == 0.0  # no (3+3+30)/3
    assert dem.iloc[5] == 30.0


def test_mismo_periodo_cruza_mes_sin_reiniciar():
    """A diferencia del reinicio mensual, misma tarifa a través de mes no resetea."""
    kw = pd.Series([12.0] * 6)
    periodo = pd.Series(["Base"] * 6)
    dem_periodo = demanda_rodante_15min_por_periodo(kw, periodo)
    mes = pd.Series(["2026-01", "2026-01", "2026-01", "2026-02", "2026-02", "2026-02"])
    dem_mes = demanda_rodante_15min_por_mes(kw, mes)
    # Por periodo: solo 0,0 al inicio de la serie
    assert list(dem_periodo) == [0.0, 0.0, 12.0, 12.0, 12.0, 12.0]
    # Por mes: también resetea en febrero
    assert list(dem_mes) == [0.0, 0.0, 12.0, 0.0, 0.0, 12.0]
