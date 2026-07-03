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
    if not txt.startswith(PREFIX):
        return None
    parts = txt.split("\t", 3)
    if len(parts) < 4:
        return None
    try:
        return int(parts[1]), int(parts[2]), parts[3]
    except ValueError:
        return None
