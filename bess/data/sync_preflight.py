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
    if not estado:
        return []

    mensajes: list[str] = []
    for msg in estado.get("bloqueantes") or []:
        texto = str(msg).strip()
        if texto:
            mensajes.append(f"Sync automático bloqueado: {texto}")
    for msg in estado.get("advertencias") or []:
        texto = str(msg).strip()
        if texto:
            mensajes.append(texto)

    # Formato anterior (v5.6.4): solo "advertencias" bloqueaba todo
    if not mensajes and not estado.get("ok"):
        for msg in estado.get("advertencias") or []:
            texto = str(msg).strip()
            if texto:
                mensajes.append(texto)
    return mensajes
