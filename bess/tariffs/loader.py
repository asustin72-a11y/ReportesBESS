"""Carga de tarifas desde SQLite."""

from __future__ import annotations

from datetime import date, datetime
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


@lru_cache(maxsize=8)
def cargar_tarifas_historicas(
    esquema_id: str = ESQUEMA_DEFAULT,
) -> dict[str, dict[tuple[int, int], float]]:
    """Carga tarifas históricas año-mes del esquema."""
    esquema = normalizar_esquema_tarifa(esquema_id)
    try:
        from bess.data.tariffs_db import leer_tarifas_historicas_dict

        return leer_tarifas_historicas_dict(esquema)
    except Exception:
        return {tipo: {} for tipo in TIPOS_TARIFA}


def tarifa_por_fecha(
    tarifa: str,
    fecha: date | datetime,
    esquema_id: str = ESQUEMA_DEFAULT,
) -> float:
    """
    Devuelve la tarifa exacta del año-mes si existe; si no, cae al esquema
    mensual legacy por número de mes.
    """
    fecha_d = fecha.date() if isinstance(fecha, datetime) else fecha
    hist = cargar_tarifas_historicas(esquema_id)
    valor = hist.get(tarifa, {}).get((fecha_d.year, fecha_d.month))
    if valor is not None:
        return float(valor)
    tarifas = cargar_tarifas(esquema_id)
    return float(tarifas.get(tarifa, {}).get(fecha_d.month, 0.0) or 0.0)


def invalidar_cache_tarifas() -> None:
    cargar_tarifas.cache_clear()
    cargar_tarifas_historicas.cache_clear()
