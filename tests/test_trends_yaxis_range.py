"""Pruebas del rango de eje Y en las gráficas de tendencia
(bess/charts/trends.py).

Bug encontrado en producción: graficar_tendencia_con_sin_bess y
graficar_tendencia_bess_operacion usaban un rango de eje Y fijo
([0, 300_000] y [0, 30_000] kWh respectivamente), calibrado a la escala
de IUSA_1/IUSA_2. IUSA_ARAGON es ~400 veces más chico (consumo diario
máximo ~734 kWh vs ~310,672 kWh de IUSA_1) -- con el rango fijo, la curva
de ARAGON quedaba aplastada, pegada al cero, invisible. Además IUSA_1
llega a superar el propio límite fijo de 300,000 en algunos periodos, así
que también se recortaba.

El arreglo: el rango de eje Y se calcula dinámicamente desde el máximo
real de los datos graficados (con 8% de margen), igual que ya hacía
graficar_energia_diaria_por_periodo.
"""

from __future__ import annotations

import pandas as pd
import pytest

from bess.charts.trends import (
    graficar_tendencia_bess_operacion,
    graficar_tendencia_con_sin_bess,
)


def _df_consumo(total_con_max: float, total_sin_max: float) -> pd.DataFrame:
    fechas = pd.date_range('2026-07-01', periods=3, freq='D')
    return pd.DataFrame({
        'FECHA_DT': fechas,
        'TOTAL_CON': [total_con_max * 0.5, total_con_max, total_con_max * 0.7],
        'TOTAL_SIN': [total_sin_max * 0.5, total_sin_max * 0.6, total_sin_max],
    })


def _df_bess(carga_max: float, descarga_max: float) -> pd.DataFrame:
    fechas = pd.date_range('2026-07-01', periods=3, freq='D')
    return pd.DataFrame({
        'FECHA_DT': fechas,
        'BASE_REC': [carga_max * 0.3, carga_max, carga_max * 0.2],
        'INTERMEDIO_REC': [0.0, 0.0, 0.0],
        'PUNTA_REC': [0.0, 0.0, 0.0],
        'BASE_ENT': [descarga_max * 0.4, descarga_max * 0.5, descarga_max],
        'INTERMEDIO_ENT': [0.0, 0.0, 0.0],
        'PUNTA_ENT': [0.0, 0.0, 0.0],
    })


def test_consumo_con_sin_bess_escala_a_sitio_pequeno_como_aragon():
    """Un sitio chico (escala ARAGON, cientos de kWh) no debe quedar con
    un rango de eje Y de cientos de miles -- la curva se vería aplastada
    e invisible."""
    df = _df_consumo(total_con_max=733.8, total_sin_max=800.0)
    fig = graficar_tendencia_con_sin_bess(df, 'ARAGON')
    y_range = fig.layout.yaxis.range

    assert y_range is not None
    assert y_range[0] == 0
    # El techo debe estar cerca del máximo real (800 * 1.08), no en 300,000.
    assert 800 < y_range[1] < 1000


def test_consumo_con_sin_bess_no_recorta_sitio_grande_como_iusa1():
    """Un sitio grande (escala IUSA_1) puede superar el viejo límite fijo
    de 300,000 -- el rango dinámico no debe recortarlo."""
    df = _df_consumo(total_con_max=310_672.2, total_sin_max=350_000.0)
    fig = graficar_tendencia_con_sin_bess(df, 'IUSA_1')
    y_range = fig.layout.yaxis.range

    assert y_range is not None
    assert y_range[1] > 350_000  # con margen, por encima del máximo real


def test_bess_operacion_escala_a_sitio_pequeno_como_aragon():
    df = _df_bess(carga_max=254.0, descarga_max=200.0)
    fig = graficar_tendencia_bess_operacion(df, 'ARAGON')
    y_range = fig.layout.yaxis.range

    assert y_range is not None
    assert y_range[0] == 0
    assert 254 < y_range[1] < 400  # no 30,000


def test_bess_operacion_no_recorta_sitio_grande():
    df = _df_bess(carga_max=20_707.2, descarga_max=25_000.0)
    fig = graficar_tendencia_bess_operacion(df, 'IUSA_1')
    y_range = fig.layout.yaxis.range

    assert y_range is not None
    assert y_range[1] > 25_000


def test_consumo_con_sin_bess_rango_none_si_todo_es_cero():
    df = _df_consumo(total_con_max=0.0, total_sin_max=0.0)
    fig = graficar_tendencia_con_sin_bess(df, 'vacio')
    assert fig.layout.yaxis.range is None


def test_bess_operacion_rango_none_si_todo_es_cero():
    df = _df_bess(carga_max=0.0, descarga_max=0.0)
    fig = graficar_tendencia_bess_operacion(df, 'vacio')
    assert fig.layout.yaxis.range is None
