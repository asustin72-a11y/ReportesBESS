"""Ingesta / utilidades pcarga (Ethernet + Wine en servidor)."""

from bess.data.ingest.pcarga.descarga import (
    ResultadoDescargaPCarga,
    convertir_pcarga_a_import,
    descargar_pcarga_medidor,
    wh_a_kwh,
)

__all__ = [
    "ResultadoDescargaPCarga",
    "convertir_pcarga_a_import",
    "descargar_pcarga_medidor",
    "wh_a_kwh",
]
