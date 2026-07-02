"""Estado del preflight de reloj (host) para la barra lateral."""

from __future__ import annotations

import json
from pathlib import Path

from bess.config.paths import DIRECTORIO_BASE

RUTA_ESTADO = DIRECTORIO_BASE / "sync_preflight.json"


def leer_estado_preflight() -> dict | None:
    if not RUTA_ESTADO.is_file():
        return None
    try:
        return json.loads(RUTA_ESTADO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def advertencias_sidebar() -> list[str]:
    estado = leer_estado_preflight()
    if not estado or estado.get("ok"):
        return []
    return [str(a) for a in estado.get("advertencias") or [] if str(a).strip()]
