"""Ingesta de perfiles de granja (API Farm · MEGA)."""

from bess.data.ingest.granja.import_csv import importar_mega_total
from bess.data.ingest.granja.sync_db import sincronizar_granja_iusa2

__all__ = ["importar_mega_total", "sincronizar_granja_iusa2"]
