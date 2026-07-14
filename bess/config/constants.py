"""Constantes de negocio compartidas."""

from bess import __version__ as VERSION
from bess.config.subestaciones import (
    etiqueta_medidor_consumo,
    medidor_consumo_por_prefijo,
    subestacion_por_prefijo,
)

ARCHIVO_TARIFAS = "Tarifas_2026.csv"
ARCHIVO_TARIFAS_GDMTH = "Tarifas_GDMTH_2026.csv"
UI_BUILD = "2026-07-08"

TIPOS_TARIFA = [
    "Base",
    "Intermedio",
    "Punta",
    "Capacidad",
    "CargoFijo",
    "Suministro",
    "Distribucion",
    "ServiciosAuxiliares",
    "Transmision",
    "CENACE",
]


def etiqueta_medidor(codigo: str) -> str:
    """Etiqueta visible del medidor de consumo o subestación."""
    med = medidor_consumo_por_prefijo(codigo)
    if med:
        return med.etiqueta
    sub = subestacion_por_prefijo(codigo)
    if sub:
        return sub.nombre
    return etiqueta_medidor_consumo(codigo) if codigo else codigo


def slug_medidor(codigo: str) -> str:
    """Nombre corto para archivos descargables (sin espacios)."""
    med = medidor_consumo_por_prefijo(codigo)
    if med:
        return med.nombre.replace(" ", "_")
    sub = subestacion_por_prefijo(codigo)
    if sub:
        return sub.id
    return (codigo or "").replace(" ", "_")