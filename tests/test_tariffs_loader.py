"""Pruebas de bess/tariffs/loader.py: carga de tarifas y su cache.

cargar_tarifas() atrapa CUALQUIER excepcion al leer la base de tarifas y
regresa tarifas en cero en silencio (bess/tariffs/loader.py linea ~30).
Es una decision de diseno discutible -- un reporte con tarifas en $0 no
se distingue de uno con tarifas reales de $0 -- pero mientras siga asi,
esta prueba fija el comportamiento actual: confirma que la caida es
segura (no truena la app) y que el resultado tiene la forma correcta.
"""

from __future__ import annotations

import bess.data.tariffs_db as tariffs_db
from bess.config.constants import TIPOS_TARIFA
from bess.tariffs.loader import _tarifas_vacias, cargar_tarifas, invalidar_cache_tarifas


def test_tarifas_vacias_tiene_todos_los_tipos_en_cero():
    vacias = _tarifas_vacias()
    assert sorted(vacias.keys()) == sorted(TIPOS_TARIFA)
    for tipo in TIPOS_TARIFA:
        assert vacias[tipo] == {mes: 0.0 for mes in range(1, 13)}


def test_cargar_tarifas_cae_a_vacias_si_falla_la_bd(monkeypatch):
    def _explota(esquema):
        raise RuntimeError("BD no disponible (simulado)")

    monkeypatch.setattr(tariffs_db, "leer_tarifas_dict", _explota)
    invalidar_cache_tarifas()
    try:
        resultado = cargar_tarifas("DIST")
    finally:
        invalidar_cache_tarifas()

    assert resultado == _tarifas_vacias()


def test_invalidar_cache_fuerza_una_nueva_lectura(monkeypatch):
    llamadas = []

    def _fake(esquema):
        llamadas.append(esquema)
        return {"Base": {mes: 1.0 for mes in range(1, 13)}}

    monkeypatch.setattr(tariffs_db, "leer_tarifas_dict", _fake)
    invalidar_cache_tarifas()
    try:
        cargar_tarifas("DIST")
        cargar_tarifas("DIST")  # mismo esquema: debe salir del cache, no llamar de nuevo
        assert len(llamadas) == 1

        invalidar_cache_tarifas()
        cargar_tarifas("DIST")  # tras invalidar, debe volver a llamar a la BD
        assert len(llamadas) == 2
    finally:
        invalidar_cache_tarifas()
