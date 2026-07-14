"""Pruebas de bess/core/numbers.py: redondeos financieros y de energia.

Estas funciones alimentan directamente costos en pesos y kWh facturados;
un error de redondeo aqui se traduce en un recibo mal calculado sin que
nada mas lo detecte. Los valores esperados se tomaron corriendo la
implementacion real (no son calculos "a mano"), para que la prueba sirva
como regresion: si el comportamiento cambia sin querer, esto lo marca.
"""

from __future__ import annotations

import pandas as pd
import pytest

from bess.core.numbers import (
    a_num,
    fmt_kwh,
    kwh_para_calculo,
    redondear_arriba_kw,
    redondear_arriba_mxn,
    redondear_kwh,
    redondear_mxn_energia,
    sumar_energia,
)


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (None, 0.0),
        ("", 0.0),
        ("abc", 0.0),
        ("42.5", 42.5),
        (42, 42.0),
        (-3.2, -3.2),
    ],
)
def test_a_num_convierte_o_cae_a_cero(valor, esperado):
    assert a_num(valor) == esperado


def test_sumar_energia_series_ignora_nan():
    serie = pd.Series([1.1, 2.2, None, 3.3])
    assert sumar_energia(serie) == pytest.approx(6.6)


def test_sumar_energia_lista_ignora_no_numericos():
    assert sumar_energia([1, 2, "x", 3]) == 6.0


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (2.5, 3),      # mitad exacta: half-up, no redondeo bancario (2.5 -> 2)
        (2.4, 2),
        (2.49999, 2),
        (0.5, 1),
        (0, 0),
        (-2.5, -3),    # half-up: la mitad se aleja de cero tambien en negativos
    ],
)
def test_redondear_kwh_half_up(valor, esperado):
    assert redondear_kwh(valor) == esperado


def test_kwh_para_calculo_es_alias_de_redondear_kwh():
    assert kwh_para_calculo(7.6) == redondear_kwh(7.6) == 8


def test_fmt_kwh_agrega_separador_de_miles():
    assert fmt_kwh(1234.6) == "1,235"
    assert fmt_kwh(1_000_000) == "1,000,000"


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (10.125, 10.13),   # tercer decimal exacto en 5: half-up
        (10.005, 10.01),
        (10.004, 10.0),
        (-5.005, -5.01),
    ],
)
def test_redondear_mxn_energia_dos_decimales_half_up(valor, esperado):
    assert redondear_mxn_energia(valor) == esperado


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (4.0, 4),      # ya es entero: no sube de mas
        (4.001, 5),    # cualquier excedente redondea hacia arriba (a favor de CFE)
        (0, 0),
        (-1.5, -1),    # ceil matematico: hacia +infinito, no "hacia arriba en valor absoluto"
    ],
)
def test_redondear_arriba_kw_es_ceil(valor, esperado):
    assert redondear_arriba_kw(valor) == esperado


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (10.001, 10.01),
        (10.00, 10.0),
        (10.0001, 10.01),
    ],
)
def test_redondear_arriba_mxn_es_ceil_a_centavos(valor, esperado):
    assert float(redondear_arriba_mxn(valor)) == esperado
