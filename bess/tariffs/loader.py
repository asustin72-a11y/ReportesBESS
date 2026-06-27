"""Carga de tarifas desde CSV."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.constants import ARCHIVO_TARIFAS, TIPOS_TARIFA
from bess.config.paths import DIRECTORIO_TARIFAS

_ALIASES_TARIFA = {
    'distribución': 'Distribucion',
    'transmisión': 'Transmision',
    'cargo fijo': 'CargoFijo',
    'servicios auxiliares': 'ServiciosAuxiliares',
}


def _tarifas_vacias() -> dict[str, dict[int, float]]:
    return {tipo: {mes: 0.0 for mes in range(1, 13)} for tipo in TIPOS_TARIFA}


def _normalizar_tipo(tipo: str) -> str:
    limpio = str(tipo).strip()
    return _ALIASES_TARIFA.get(limpio.lower(), limpio)


def cargar_tarifas() -> dict[str, dict[int, float]]:
    """Carga todas las tarifas del CSV (energía, MEM, capacidad, cargo fijo, etc.)."""
    ruta = os.path.join(DIRECTORIO_TARIFAS, ARCHIVO_TARIFAS)
    tarifas = _tarifas_vacias()
    if not os.path.exists(ruta):
        return tarifas

    try:
        df = pd.read_csv(ruta, encoding='utf-8-sig')
        df.columns = [str(c).strip() for c in df.columns]
        for _, row in df.iterrows():
            tipo = _normalizar_tipo(row.get('Tarifa', ''))
            if not tipo:
                continue
            tarifas.setdefault(tipo, {mes: 0.0 for mes in range(1, 13)})
            for mes in range(1, 13):
                tarifas[tipo][mes] = float(row.get(str(mes), 0) or 0)
        return tarifas
    except Exception:
        return _tarifas_vacias()
