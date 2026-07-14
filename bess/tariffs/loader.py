"""Carga de tarifas desde SQLite."""

from __future__ import annotations

from functools import lru_cache

from bess.config.constants import TIPOS_TARIFA
from bess.config.esquema_tarifa import ESQUEMA_DEFAULT, normalizar_esquema_tarifa

_ALIASES_TARIFA = {
    "distribución": "Distribucion",
    "transmisión": "Transmision",
    "cargo fijo": "CargoFijo",
    "servicios auxiliares": "ServiciosAuxiliares",
}


def _tarifas_vacias() -> dict[str, dict[int, float]]:
    return {tipo: {mes: 0.0 for mes in range(1, 13)} for tipo in TIPOS_TARIFA}


@lru_cache(maxsize=8)
def cargar_tarifas(esquema_id: str = ESQUEMA_DEFAULT) -> dict[str, dict[int, float]]:
    """Carga tarifas del esquema (DIST, GDMTH, …)."""
    esquema = normalizar_esquema_tarifa(esquema_id)
    try:
        from bess.data.tariffs_db import leer_tarifas_dict

        return leer_tarifas_dict(esquema)
    except Exception:
        return _tarifas_vacias()


def invalidar_cache_tarifas() -> None:
    cargar_tarifas.cache_clear()
