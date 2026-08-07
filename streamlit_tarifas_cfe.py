"""Punto de entrada — Consultar Tarifa (app hermana IUSASOL).

Uso:
    streamlit run streamlit_tarifas_cfe.py
    streamlit run streamlit_tarifas_cfe.py --server.port 8503
"""
import sys


def _configurar_salida_consola():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError, TypeError):
            pass


_configurar_salida_consola()

from tarifas_cfe.ui.app import main

main()
