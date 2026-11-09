"""Avance de un día en los selectores de periodo."""

from datetime import date

from bess.ui.components import rango_desplazado


def test_dia_suelto_avanza_y_retrocede():
    dia = date(2026, 11, 3)
    minimo = date(2026, 11, 1)
    maximo = date(2026, 11, 5)
    assert rango_desplazado(dia, dia, 1, minimo, maximo) == (
        date(2026, 11, 4),
        date(2026, 11, 4),
    )
    assert rango_desplazado(dia, dia, -1, minimo, maximo) == (
        date(2026, 11, 2),
        date(2026, 11, 2),
    )


def test_rango_se_desliza_sin_cambiar_longitud():
    assert rango_desplazado(
        date(2026, 11, 1),
        date(2026, 11, 3),
        1,
        date(2026, 11, 1),
        date(2026, 11, 10),
    ) == (date(2026, 11, 2), date(2026, 11, 4))


def test_no_sale_de_los_datos():
    minimo = date(2026, 11, 1)
    maximo = date(2026, 11, 3)
    assert rango_desplazado(minimo, minimo, -1, minimo, maximo) is None
    assert rango_desplazado(maximo, maximo, 1, minimo, maximo) is None
    assert rango_desplazado(
        date(2026, 11, 2), date(2026, 11, 3), 1, minimo, maximo
    ) is None


def test_rango_invertido_no_se_mueve():
    assert rango_desplazado(
        date(2026, 11, 4),
        date(2026, 11, 2),
        1,
        date(2026, 11, 1),
        date(2026, 11, 10),
    ) is None
