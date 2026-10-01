"""Pruebas de bess/cfe/periods.py: temporada, festivos y periodo horario CFE.

obtener_periodo_por_hora() decide si cada hora factura como Base,
Intermedio o Punta -- de ahi sale directo el costo de energia. Es logica
con muchas ramas anidadas (temporada x tipo de dia x hora), facil de
romper sin darse cuenta en un refactor futuro. Los valores esperados se
tomaron corriendo la implementacion real para el anio 2026 (no son
calculos "a mano"): esto fija el comportamiento actual como regresion.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from bess.cfe.periods import (
    es_festivo,
    fecha_y_hora_archivo,
    obtener_periodo_por_hora,
    obtener_temporada,
    periodo_por_fecha_hora,
)
from bess.cfe.periods_gdmth import obtener_periodo_gdmth_por_hora


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
        24: "Intermedio",  # hora_archivo 24 = hora 23, no la hora 0
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


def test_cierre_de_dia_no_toma_el_festivo_siguiente():
    """15/09/2026 es martes (temporada 3). 22:00–24:00 es Intermedio.
    El 16 es festivo: si las 23:05 se clasifican con esa fecha, salen Base."""
    assert periodo_por_fecha_hora("15/09/2026 23:00", "DIST") == "Intermedio"
    assert periodo_por_fecha_hora("15/09/2026 23:05", "DIST") == "Intermedio"
    assert periodo_por_fecha_hora("15/09/2026 23:55", "DIST") == "Intermedio"
    # 00:00 cierra la hora 23 del 15, no abre el festivo.
    assert periodo_por_fecha_hora("16/09/2026 00:00", "DIST") == "Intermedio"
    assert periodo_por_fecha_hora("16/09/2026 00:05", "DIST") == "Base"


def test_sabado_23h_no_hereda_el_domingo():
    # 12/09/2026 sábado, temporada 3: después de las 07:00 todo es Intermedio.
    assert periodo_por_fecha_hora("12/09/2026 23:05", "DIST") == "Intermedio"
    assert periodo_por_fecha_hora("13/09/2026 00:00", "DIST") == "Intermedio"
    # Domingo temporada 3: la hora 23 vuelve a Base.
    assert periodo_por_fecha_hora("13/09/2026 23:05", "DIST") == "Base"


def test_hora_archivo_24_es_la_hora_23():
    """En invierno entre semana la hora 0 es Base y la 23 es Intermedio.
    Si 24 se tratara como hora 0, las 23:05 saldrían Base."""
    jueves = datetime(2026, 1, 8)
    assert jueves.weekday() == 3
    assert obtener_periodo_por_hora(jueves, 1) == "Base"
    assert obtener_periodo_por_hora(jueves, 24) == "Intermedio"


def _dueno(dt: datetime) -> tuple[datetime, int]:
    """Día y hora de reloj (0–23) que cierra la marca. Independiente del código."""
    if dt.hour == 0 and dt.minute == 0:
        return dt - timedelta(days=1), 23
    if dt.minute == 0:
        return dt, dt.hour - 1
    return dt, dt.hour


@pytest.mark.parametrize(
    "dia",
    [
        datetime(2026, 9, 15),   # martes, víspera del festivo 16
        datetime(2026, 9, 16),   # festivo
        datetime(2026, 9, 12),   # sábado
        datetime(2026, 9, 13),   # domingo
        datetime(2026, 6, 1),    # lunes, temporada 2
        datetime(2026, 1, 8),    # jueves, temporada 4
        datetime(2026, 1, 3),    # sábado, temporada 4
        datetime(2026, 1, 4),    # domingo, temporada 4
        datetime(2026, 4, 4),    # sábado antes del cambio de abril
        datetime(2026, 4, 5),    # primer domingo de abril
        datetime(2026, 10, 24),  # sábado antes del cambio de octubre
        datetime(2026, 10, 25),  # último domingo de octubre
        datetime(2026, 12, 31),  # víspera de año
        datetime(2026, 2, 5),    # festivo
    ],
)
def test_cada_marca_usa_la_hora_que_cierra(dia):
    """Ninguna marca de 5 min puede tomar el calendario del día siguiente."""
    for hora in range(24):
        for minuto in range(0, 60, 5):
            marca = dia.replace(hour=hora, minute=minuto)
            texto = marca.strftime("%d/%m/%Y %H:%M")
            dueno, hora_reloj = _dueno(marca)
            assert periodo_por_fecha_hora(texto, "DIST") == obtener_periodo_por_hora(
                dueno, hora_reloj + 1
            ), texto
            assert periodo_por_fecha_hora(texto, "GDMTH") == obtener_periodo_gdmth_por_hora(
                dueno, hora_reloj
            ), texto


def test_la_marca_no_cambia_de_fecha_al_cerrar_el_dia():
    fecha, hora = fecha_y_hora_archivo("15/09/2026 23:05")
    assert (fecha.year, fecha.month, fecha.day, hora) == (2026, 9, 15, 24)
    fecha, hora = fecha_y_hora_archivo("16/09/2026 00:00")
    assert (fecha.year, fecha.month, fecha.day, hora) == (2026, 9, 15, 24)
    fecha, hora = fecha_y_hora_archivo("16/09/2026 00:05")
    assert (fecha.year, fecha.month, fecha.day, hora) == (2026, 9, 16, 1)
    fecha, hora = fecha_y_hora_archivo("01/01/2026 00:00")
    assert (fecha.year, fecha.month, fecha.day, hora) == (2025, 12, 31, 24)


def test_analisis_perfil_cierra_el_dia_igual():
    import importlib.util
    from pathlib import Path

    ruta = Path(__file__).resolve().parents[1] / "analisis_perfil" / "marca_horaria.py"
    spec = importlib.util.spec_from_file_location("marca_horaria", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    for texto in (
        "15/09/2026 23:05",
        "16/09/2026 00:00",
        "16/09/2026 00:05",
        "24/10/2026 23:55",
        "25/10/2026 00:00",
        "01/01/2026 00:00",
    ):
        dt = datetime.strptime(texto, "%d/%m/%Y %H:%M")
        fecha_bess, hora_archivo = fecha_y_hora_archivo(texto)
        fecha_ap, hora_reloj = modulo.fecha_y_hora_cfe(dt)
        assert fecha_ap == fecha_bess.date(), texto
        assert hora_reloj == hora_archivo - 1, texto
