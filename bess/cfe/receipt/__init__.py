"""Recibo simulado CFE (HTML/PDF)."""

from bess.cfe.receipt.build import construir_datos_recibo_cfe
from bess.cfe.receipt.html import render_html_recibo_cfe, render_html_recibo_documento
from bess.cfe.receipt.pdf import generar_recibo_pdf_bytes, nombre_archivo_recibo
from bess.cfe.receipt.tables import construir_tabla_recibo_completo, construir_tabla_recibo_energia

__all__ = [
    "construir_datos_recibo_cfe",
    "construir_tabla_recibo_completo",
    "construir_tabla_recibo_energia",
    "generar_recibo_pdf_bytes",
    "nombre_archivo_recibo",
    "render_html_recibo_cfe",
    "render_html_recibo_documento",
]
