"""Configuración compartida de pytest.

Shim de compatibilidad: el proyecto corre en Python 3.12 (ver Dockerfile),
donde `tomllib` es de la librería estándar. Si la suite se ejecuta en un
entorno con Python < 3.11 (p.ej. 3.10), `tomllib` no existe todavía y
`bess.data.ingest.iusasol.config` (que sí lo requiere en producción) falla
al importarse. Este shim solo actúa cuando falta `tomllib`; en Python 3.12
no hace nada.
"""

from __future__ import annotations

import sys

try:
    import tomllib  # noqa: F401
except ModuleNotFoundError:
    import tomli

    sys.modules['tomllib'] = tomli
