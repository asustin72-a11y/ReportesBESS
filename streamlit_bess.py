"""Punto de entrada solo BESS (sin portal de Suite).

Útil para desarrollo o si se necesita el reporteador BESS aislado.
Producción: use streamlit_app.py (Suite IUSASOL).
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

from bess.ui.app import main

main()
