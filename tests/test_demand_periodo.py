"""Demanda rodante 15 min continua + máscara TOU para máximos."""

from __future__ import annotations

import pandas as pd

from bess.core.demand import (
    aplicar_mascara_demanda_maximo,
    demanda_rodante_15min_por_mes,
    demanda_rodante_15min_por_periodo,
    mascara_valida_para_maximo,
)


def test_rolling_por_mes_continuo_al_cambiar_periodo():
    """Dentro del mismo mes, el cambio de periodo no mete ceros."""
    kw = pd.Series([12.0] * 9)
    mes = pd.Series(["2026-07"] * 9)
    periodo = pd.Series(
        ["Base", "Base", "Base", "Punta", "Punta", "Punta", "Base", "Base", "Base"]
    )
    dem = demanda_rodante_15min_por_mes(kw, mes)
    # Solo 0,0 al inicio del mes; el resto continuo a 12
    assert list(dem.iloc[:3]) == [0.0, 0.0, 12.0]
    assert list(dem.iloc[3:]) == [12.0] * 6
    # Contraste: por_periodo sí pondría ceros en cada cambio
    dem_p = demanda_rodante_15min_por_periodo(kw, periodo)
    assert list(dem_p.iloc[3:6]) == [0.0, 0.0, 12.0]


def test_mascara_excluye_dos_primeros_de_cada_racha():
    periodo = pd.Series(
        ["Base", "Base", "Base", "Punta", "Punta", "Punta", "Base", "Base", "Base"]
    )
    valida = mascara_valida_para_maximo(periodo, n_excluir=2)
    assert list(valida) == [
        False,
        False,
        True,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


def test_maximo_no_cae_en_borde_mezclado():
    """
    Rolling continuo: al entrar a Punta los 2 primeros promedian con Base.
    La máscara evita que ese borde gane el máximo de Punta.
    """
    # Base baja, luego un pico artificial en el 1.er intervalo de Punta
    # por mezcla (rolling), y Punta pura después más baja que ese borde.
    kw = pd.Series([3.0, 3.0, 3.0, 30.0, 30.0, 10.0, 10.0, 10.0])
    mes = pd.Series(["2026-07"] * 8)
    periodo = pd.Series(
        [
            "Intermedio",
            "Intermedio",
            "Intermedio",
            "Punta",
            "Punta",
            "Punta",
            "Punta",
            "Punta",
        ]
    )
    dem = demanda_rodante_15min_por_mes(kw, mes)
    # Índice 3 (1.er Punta): media (3+3+30)/3 = 12 — borde mezclado
    # Índice 5 (3.er Punta): media (30+30+10)/3 = 23.333 — ventana pura alta
    assert dem.iloc[3] == 12.0
    assert abs(dem.iloc[5] - (30 + 30 + 10) / 3) < 1e-9

    enmascarada = aplicar_mascara_demanda_maximo(dem, periodo)
    assert pd.isna(enmascarada.iloc[3])
    assert pd.isna(enmascarada.iloc[4])
    punta = enmascarada.loc[periodo == "Punta"]
    assert float(punta.max()) == float(enmascarada.iloc[5])
    assert punta.idxmax() == 5


def test_reinicio_mensual_sigue_en_cero_al_cambiar_mes():
    kw = pd.Series([12.0] * 6)
    mes = pd.Series(["2026-01", "2026-01", "2026-01", "2026-02", "2026-02", "2026-02"])
    dem = demanda_rodante_15min_por_mes(kw, mes)
    assert list(dem) == [0.0, 0.0, 12.0, 0.0, 0.0, 12.0]
