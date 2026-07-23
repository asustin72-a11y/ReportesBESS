"""Eventos de progreso en stderr para la UI Streamlit (sin dependencia de Streamlit)."""

from __future__ import annotations

import os
import sys

PREFIX = "BESS_UI_PROGRESS\t"


def ui_progress_habilitado() -> bool:
    return os.environ.get("BESS_UI_PROGRESS") == "1"


def emit_ui_progress(step: int, total: int, label: str) -> None:
    print(f"{PREFIX}{step}\t{total}\t{label}", file=sys.stderr, flush=True)


def parse_ui_progress(line: str) -> tuple[int, int, str] | None:
    txt = (line or "").strip()
    # Acepta tabuladores o espacios (Windows / consolas a veces normalizan \t).
    if not txt.startswith("BESS_UI_PROGRESS"):
        return None
    resto = txt[len("BESS_UI_PROGRESS") :].lstrip(" \t")
    parts = resto.split(None, 2)  # step total label…
    if len(parts) < 2:
        return None
    try:
        step = int(parts[0])
        total = int(parts[1])
    except ValueError:
        return None
    label = parts[2] if len(parts) > 2 else ""
    return step, total, label


def es_linea_progreso_ui(line: str) -> bool:
    """True si la línea es (o empieza como) evento de progreso de la UI."""
    return (line or "").strip().startswith("BESS_UI_PROGRESS")
