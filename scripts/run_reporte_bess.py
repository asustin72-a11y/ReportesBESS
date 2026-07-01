"""Genera reportes CSV en proceso aislado (evita caché de módulos en Streamlit)."""

from __future__ import annotations

import json
import os
import sys
import traceback

_MARKER = "__BESS_REPORTE_JSON__"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    try:
        from bess.data.orchestrator import reporte_bess

        ok, mensajes = reporte_bess()
        payload = {"ok": ok, "mensajes": mensajes}
    except Exception as exc:
        payload = {
            "ok": False,
            "mensajes": {"_error": str(exc)},
            "traceback": traceback.format_exc(),
        }
    print(_MARKER + json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
