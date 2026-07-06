"""Carga de tarifas desde SQLite."""

from __future__ import annotations

from functools import lru_cache

from bess.config.constants import TIPOS_TARIFA

_ALIASES_TARIFA = {
    "distribución": "Distribucion",
    "transmisión": "Transmision",
    "cargo fijo": "CargoFijo",
    "servicios auxiliares": "ServiciosAuxiliares",
}


def _tarifas_vacias() -> dict[str, dict[int, float]]:
    return {tipo: {mes: 0.0 for mes in range(1, 13)} for tipo in TIPOS_TARIFA}


def _normalizar_tipo(tipo: str) -> str:
    limpio = str(tipo).strip()
    return _ALIASES_TARIFA.get(limpio.lower(), limpio)


@lru_cache(maxsize=1)
def cargar_tarifas() -> dict[str, dict[int, float]]:
    """Carga todas las tarifas desde la BD (energía, MEM, capacidad, cargo fijo, etc.)."""
    try:
        from bess.data.tariffs_db import leer_tarifas_dict

        return leer_tarifas_dict()
    except Exception:
        return _tarifas_vacias()


def invalidar_cache_tarifas() -> None:
    cargar_tarifas.cache_clear()
