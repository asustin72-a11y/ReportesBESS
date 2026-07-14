"""Pruebas de bess/cfe/periods.py: temporada, festivos y periodo horario CFE.

obtener_periodo_por_hora() decide si cada hora factura como Base,
Intermedio o Punta -- de ahi sale directo el costo de energia. Es logica
con muchas ramas anidadas (temporada x tipo de dia x hora), facil de
romper sin darse cuenta en un refactor futuro. Los valores esperados se
tomaron corriendo la implementacion real para el anio 2026 (no son
calculos "a mano"): esto fija el comportamiento actual como regresion.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from bess.cfe.periods import es_festivo, obtener_periodo_por_hora, obtener_temporada


@pytest.mark.parametrize(
    "fecha, temporada_esperada",
    [
        (datetime(2026, 1, 31), 4),   # ultimo dia de temporada 4 (invierno)
        (datetime(2026, 2, 1), 1),    # primer dia de temporada 1
        (datetime(2026, 3, 31), 1),   # sigue en temporada 1
        (datetime(2026, 4, 4), 1),    # sabado antes del primer domingo de abril: aun T1
        (datetime(2026, 4, 5), 2),    # primer domingo de abril 2026: arranca T2
        (datetime(2026, 4, 6), 2),
        (datetime(2026, 7, 31), 2),   # ultimo dia de julio: sigue T2
        (datetime(2026, 8, 1), 3),    # agosto: arranca T3
        (datetime(2026, 9, 30), 3),
        (datetime(2026, 10, 24), 3),  # sabado antes del ultimo domingo de octubre: aun T3
        (datetime(2026, 10, 25), 4),  # ultimo domingo de octubre 2026: arranca T4
        (datetime(2026, 12, 31), 4),
    ],
)
def test_obtener_temporada_fronteras(fecha, temporada_esperada):
    assert obtener_temporada(fecha) == temporada_esperada


@pytest.mark.parametrize(
    "fecha, es_fest",
    [
        (datetime(2026, 1, 1), True),
        (datetime(2026, 2, 5), True),
        (datetime(2026, 1, 2), False),
        (datetime(2026, 6, 15), False),
    ],
)
def test_es_festivo(fecha, es_fest):
    assert es_festivo(fecha) is es_fest


def test_periodo_lunes_temporada_verano():
    # 2026-06-01 es lunes, temporada 2 (verano, la de mas horas Punta)
    lunes = datetime(2026, 6, 1)
    assert lunes.weekday() == 0
    casos = {
        1: "Intermedio",  # hora 0 en temporada 2 entre semana: excepcion a Base
        2: "Base",
        6: "Base",
        7: "Intermedio",
        20: "Intermedio",
        21: "Punta",
        22: "Punta",
        24: "Intermedio",  # 24 se normaliza a hora 0
    }
    for hora_archivo, esperado in casos.items():
        assert obtener_periodo_por_hora(lunes, hora_archivo) == esperado, hora_archivo


def test_periodo_sabado_temporada_verano():
    sabado = datetime(2026, 6, 6)
    assert sabado.weekday() == 5
    casos = {
        1: "Intermedio",  # hora 0 sabado T2: Intermedio (unico caso especial)
        2: "Base",
        8: "Intermedio",
        21: "Intermedio",
    }
    for hora_archivo, esperado in casos.items():
        assert obtener_periodo_por_hora(sabado, hora_archivo) == esperado, hora_archivo


def test_periodo_domingo_temporada_invierno():
    domingo = datetime(2026, 1, 4)
    assert domingo.weekday() == 6
    casos = {
        1: "Base",
        19: "Intermedio",
        24: "Intermedio",
    }
    for hora_archivo, esperado in casos.items():
        assert obtener_periodo_por_hora(domingo, hora_archivo) == esperado, hora_archivo


def test_festivo_entre_semana_se_trata_como_domingo():
    # 2026-01-01 es jueves y festivo: debe usar la tabla de domingo/festivo,
    # no la de dia entre semana.
    festivo = datetime(2026, 1, 1)
    assert festivo.weekday() == 3
    assert es_festivo(festivo)
    normal_jueves = datetime(2026, 1, 8)  # mismo horario, sin festivo
    # A la misma hora, un jueves festivo y un jueves normal no deben
    # necesariamente coincidir -- lo que importa es que el festivo use
    # la rama de domingo/festivo, verificable comparando contra un domingo
    # real de la misma temporada.
    domingo_misma_temporada = datetime(2026, 1, 4)
    for hora in (1, 12, 20):
        assert obtener_periodo_por_hora(festivo, hora) == obtener_periodo_por_hora(
            domingo_misma_temporada, hora
        )
