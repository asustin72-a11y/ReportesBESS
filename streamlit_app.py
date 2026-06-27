"""Punto de entrada para Streamlit Community Cloud."""
import sys


def _configurar_salida_consola():
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, OSError, ValueError, TypeError):
            pass


_configurar_salida_consola()

# UI modular (bess/ui): gráficas con descarga PNG, sync, recibo, etc.
# app_plotly.py queda como respaldo legacy; no usar como entry point.
from bess.ui.app import main

main()
