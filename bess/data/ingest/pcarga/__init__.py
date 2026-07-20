"""Ingesta / utilidades pcarga (Ethernet + Wine en servidor)."""

from bess.data.ingest.pcarga.descarga import (
    ResultadoDescargaPCarga,
    convertir_pcarga_a_import,
    descargar_pcarga_medidor,
    wh_a_kwh,
)
from bess.data.ingest.pcarga.fallback import (
    ResultadoFallbackLote,
    ResultadoFallbackMedidor,
    ejecutar_fallback_pcarga_iusa12,
)

__all__ = [
    "ResultadoDescargaPCarga",
    "ResultadoFallbackLote",
    "ResultadoFallbackMedidor",
    "convertir_pcarga_a_import",
    "descargar_pcarga_medidor",
    "ejecutar_fallback_pcarga_iusa12",
    "wh_a_kwh",
]
