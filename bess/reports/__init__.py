"""Reportes exportables (PDF, etc.)."""

from bess.reports.accumulated_pdf import generar_reporte_acumulado_pdf
from bess.reports.daily_pdf import generar_reporte_pdf

__all__ = ["generar_reporte_pdf", "generar_reporte_acumulado_pdf"]
