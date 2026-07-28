"""Reportes PDF del módulo Granja."""

from granja.reports.daily_pdf import generar_pdf_diario
from granja.reports.monthly_pdf import (
    generar_pdf_mensual,
    generar_pdf_mensual_energia,
    generar_pdf_mensual_ingresos,
)

__all__ = [
    "generar_pdf_diario",
    "generar_pdf_mensual",
    "generar_pdf_mensual_ingresos",
    "generar_pdf_mensual_energia",
]
