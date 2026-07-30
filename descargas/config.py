"""Constantes del módulo de descarga."""

from __future__ import annotations

from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Mexico_City")

# Aviso UI: Granja = 1 request HTTP por día × medidor
AVISO_GRANJA_REQUESTS = 200

SECCIONES = (
    ("clientes", "Clientes (ISOL)"),
    ("granja", "Granja (Farm)"),
    ("porteo", "Porteo"),
)
