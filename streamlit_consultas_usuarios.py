"""Punto de entrada Streamlit — módulo Consultas Usuarios (IUSASOL).

Independiente de BESS:

    streamlit run streamlit_consultas_usuarios.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from consultas_usuarios.ui.app import main as app_main

    app_main()


if __name__ == '__main__':
    main()
