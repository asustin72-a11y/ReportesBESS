"""Demanda real DIST (IUSA 1 / IUSA 2): solo fórmula y rolling, sin I/O."""

from __future__ import annotations

import pandas as pd

from bess.charts.profile import (
    _enriquecer_demanda_real_perfil,
    kwh_demanda_real_intervalo,
    serie_demanda_real_15min,
)
from bess.core.demand import demanda_rodante_15min_por_mes


def test_kwh_demanda_real_es_ion_mas_gen_mas_bess_neto():
    ion = pd.Series([100.0, 100.0, 100.0])
    gen = pd.Series([10.0, 10.0, 10.0])
    ent = pd.Series([5.0, 0.0, 0.0])
    rec = pd.Series([0.0, 20.0, 0.0])
    kwh = kwh_demanda_real_intervalo(ion, gen, ent, rec)
    assert list(kwh) == [115.0, 90.0, 110.0]


def test_rolada_15min_de_demanda_real_es_media_de_tres():
    kw = pd.Series([1200.0, 1500.0, 1800.0])
    mes = pd.Series(["2026-09"] * 3)
    dem = demanda_rodante_15min_por_mes(kw, mes)
    assert dem.iloc[0] == 0.0
    assert dem.iloc[1] == 0.0
    assert abs(float(dem.iloc[2]) - 1500.0) < 1e-9


def test_perfil_gdmth_no_agrega_demanda_real_en_dist(monkeypatch):
    """No contaminar el perfil/PDF de IUSA 1-2 (sigue gated a netmetering)."""
    monkeypatch.setattr(
        "bess.charts.profile.usa_netmetering", lambda _esquema=None: False
    )
    monkeypatch.setattr(
        "bess.charts.profile.esquema_tarifa_prefijo", lambda _p: "DIST"
    )
    df = pd.DataFrame({
        "KWH_REC_ION_Testigo_IUSA1": [1.0],
        "KWH_ENT_ION_Testigo_IUSA1": [0.0],
        "KWH_ENT_BESS": [0.0],
        "KWH_REC_BESS": [0.0],
    })
    out = _enriquecer_demanda_real_perfil(df, "ION_Testigo_IUSA1")
    assert "KW_DEMANDA_REAL" not in out.columns


def test_serie_demanda_real_sin_gen_iguala_ion_deshaciendo_bess(monkeypatch):
    monkeypatch.setattr(
        "bess.charts.profile._kwh_generacion_alineada",
        lambda df, prefijo: pd.Series(0.0, index=df.index),
    )
    monkeypatch.setattr(
        "bess.core.consumo.usa_consumo_neto",
        lambda prefijo: False,
    )
    df = pd.DataFrame({
        "FECHA": ["09/09/2026", "09/09/2026", "09/09/2026"],
        "FECHA_HORA": [
            "09/09/2026 01:45",
            "09/09/2026 01:50",
            "09/09/2026 01:55",
        ],
        "KWH_REC": [1670.0, 1692.0, 1670.0],
        "KWH_ENT_BESS": [0.0, 0.0, 0.0],
        "KWH_REC_BESS": [624.0, 624.0, 624.0],
    })
    dem = serie_demanda_real_15min(df, "ION_Testigo_IUSA1")
    # kWh planta = ION - recarga = 1670-624, 1692-624, 1670-624
    # kW = *12 → 12552, 12816, 12552; media 15 min del 3.er punto
    esperado = (12552.0 + 12816.0 + 12552.0) / 3
    assert abs(float(dem.iloc[2]) - esperado) < 1e-6
    assert dem.iloc[0] == 0.0
