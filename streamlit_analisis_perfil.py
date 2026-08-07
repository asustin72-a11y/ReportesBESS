"""Punto de entrada — Análisis de Perfil (app hermana IUSASOL).

Uso:
    streamlit run streamlit_analisis_perfil.py
"""
import sys
from pathlib import Path


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

# Repo root + paquete (imports estilo script del pipeline).
_ROOT = Path(__file__).resolve().parent
_PKG = _ROOT / "analisis_perfil"
for _p in (_ROOT, _PKG):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)

from analisis_perfil.ui.app import main

main()
