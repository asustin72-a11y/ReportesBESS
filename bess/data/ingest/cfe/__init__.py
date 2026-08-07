"""Cliente de consulta de tarifas CFE (páginas públicas ASP.NET)."""

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
from bess.data.ingest.cfe.presets import (
    PRESETS,
    PRESETS_BESS_AUTO,
    consultar_preset,
)
from bess.data.ingest.cfe.tarifas_client import (
    ConsultaTarifaCFE,
    CfeTarifasError,
    ResultadoTarifaCFE,
    TablaTarifaCFE,
    consultar_geo_por_divisiones,
    consultar_tarifa_catalogo,
    consultar_tarifas_cfe,
    enumerar_geo_completo,
    explorar_opciones_geo,
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
