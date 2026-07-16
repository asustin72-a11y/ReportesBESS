"""Pruebas de _rango_y_perfil() (bess/charts/profile.py).

Bug encontrado en producción: para un sitio con demanda real (netmetering
GDMTH) Y consumo neto a la vez -- el caso real de IUSA_ARAGON --,
graficar_perfil() dibuja de forma independiente las series 'Demanda real'
(KW_DEMANDA_REAL) y 'kW recibidos' (KW_REC_ION). _rango_y_perfil() las
trataba como mutuamente excluyentes (if/elif): cuando tiene_demanda_real
era True, KW_REC_ION nunca entraba al cálculo del máximo del eje Y, así
que si su pico superaba al de KW_DEMANDA_REAL/generación/BESS, la línea
'kW recibidos' se cortaba por arriba. Confirmado con datos reales de
IUSA_ARAGON del 15/07: KW_REC_ION llegaba a 90 kW, el rango calculado
solo llegaba a ~75 kW.

El arreglo: ambas series contribuyen al máximo del eje (if en vez de
elif), igual que ya se dibujan de forma independiente en la gráfica.
"""

from __future__ import annotations

import pandas as pd

from bess.charts.profile import _rango_y_perfil


def test_no_recorta_pico_de_kw_recibidos_cuando_hay_demanda_real():
    """Reproduce el bug real de IUSA_ARAGON: KW_REC_ION (90) supera a
    KW_DEMANDA_REAL/generación/BESS -- el rango debe alcanzar a cubrirlo."""
    df = pd.DataFrame({
        'KW_DEMANDA_REAL': [-10.8, 20.0, 46.8, 10.0],
        'KW_REC_ION': [15.0, 40.0, 90.0, 20.0],
        'KW_GENERACION': [0.0, 0.0, 0.0, 0.0],
        'BESS_REC_kW': [0.0, 70.9, 0.0, 0.0],
        'BESS_ENT_kW': [0.0, 0.0, 0.0, 0.0],
    })
    y_range = _rango_y_perfil(df, 'col_con_no_usado', True, tiene_demanda_real=True)

    assert y_range is not None
    assert y_range[1] >= df['KW_REC_ION'].max()


def test_no_recorta_pico_de_demanda_real_cuando_es_mayor():
    """Caso inverso: si el pico de demanda real supera a kW recibidos,
    debe seguir cubierto (comportamiento que ya funcionaba)."""
    df = pd.DataFrame({
        'KW_DEMANDA_REAL': [-10.0, 500.0, 100.0],
        'KW_REC_ION': [15.0, 40.0, 90.0],
        'KW_GENERACION': [0.0, 0.0, 0.0],
        'BESS_REC_kW': [0.0, 0.0, 0.0],
        'BESS_ENT_kW': [0.0, 0.0, 0.0],
    })
    y_range = _rango_y_perfil(df, 'col_con_no_usado', True, tiene_demanda_real=True)

    assert y_range is not None
    assert y_range[1] >= df['KW_DEMANDA_REAL'].max()
    assert y_range[1] >= df['KW_REC_ION'].max()


def test_sitio_sin_demanda_real_sigue_usando_kw_rec_ion():
    """Sitios sin netmetering (tiene_demanda_real=False) siguen usando
    solo KW_REC_ION, sin cambio de comportamiento."""
    df = pd.DataFrame({
        'KW_REC_ION': [15.0, 40.0, 90.0],
        'BESS_REC_kW': [0.0, 0.0, 0.0],
        'BESS_ENT_kW': [0.0, 30.0, 0.0],
    })
    y_range = _rango_y_perfil(df, 'col_con_no_usado', True, tiene_demanda_real=False)

    assert y_range is not None
    assert y_range[1] >= df['KW_REC_ION'].max()


def test_sitio_con_col_con_y_demanda_real_cubre_ambos_picos():
    """Sitio sin consumo neto propio (perfil_rec_ent=False) pero con
    demanda real: col_con y KW_DEMANDA_REAL también deben combinarse."""
    df = pd.DataFrame({
        'KW_DEMANDA_REAL': [-5.0, 30.0],
        'IUSA_CON_BESS_x_kW': [12.0, 200.0],
        'BESS_REC_kW': [0.0, 0.0],
        'BESS_ENT_kW': [0.0, 0.0],
    })
    y_range = _rango_y_perfil(
        df, 'IUSA_CON_BESS_x_kW', False, tiene_demanda_real=True
    )

    assert y_range is not None
    assert y_range[1] >= df['IUSA_CON_BESS_x_kW'].max()
