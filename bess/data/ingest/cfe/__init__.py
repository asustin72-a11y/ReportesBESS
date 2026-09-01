"""Cliente de consulta de tarifas CFE (páginas públicas ASP.NET)."""

from __future__ import annotations

from typing import Any

from bess.data.ingest.cfe.catalog import (
    CATEGORIAS,
    FamiliaForm,
    INICIOS_VERANO,
    TARIFAS_CFE,
    TarifaCFEDef,
    catalogo_dict,
    tarifa_por_codigo,
    tarifas_por_categoria,
)

__all__ = [
    "CATEGORIAS",
    "ConsultaTarifaCFE",
    "CfeTarifasError",
    "FamiliaForm",
    "INICIOS_VERANO",
    "PRESETS",
    "PRESETS_BESS_AUTO",
    "ResultadoTarifaCFE",
    "TablaTarifaCFE",
    "TARIFAS_CFE",
    "TarifaCFEDef",
    "catalogo_dict",
    "consultar_geo_por_divisiones",
    "consultar_preset",
    "consultar_tarifa_catalogo",
    "consultar_tarifas_cfe",
    "enumerar_geo_completo",
    "explorar_opciones_geo",
    "tarifa_por_codigo",
    "tarifas_por_categoria",
]

_LAZY_PRESETS = {
    "PRESETS": "PRESETS",
    "PRESETS_BESS_AUTO": "PRESETS_BESS_AUTO",
    "consultar_preset": "consultar_preset",
}
_LAZY_CLIENT = {
    "ConsultaTarifaCFE": "ConsultaTarifaCFE",
    "CfeTarifasError": "CfeTarifasError",
    "ResultadoTarifaCFE": "ResultadoTarifaCFE",
    "TablaTarifaCFE": "TablaTarifaCFE",
    "consultar_geo_por_divisiones": "consultar_geo_por_divisiones",
    "consultar_tarifa_catalogo": "consultar_tarifa_catalogo",
    "consultar_tarifas_cfe": "consultar_tarifas_cfe",
    "enumerar_geo_completo": "enumerar_geo_completo",
    "explorar_opciones_geo": "explorar_opciones_geo",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_PRESETS:
        from bess.data.ingest.cfe import presets as _presets

        return getattr(_presets, _LAZY_PRESETS[name])
    if name in _LAZY_CLIENT:
        from bess.data.ingest.cfe import tarifas_client as _client

        return getattr(_client, _LAZY_CLIENT[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
