#!/usr/bin/env python3
"""Punto de entrada para descargar_ion.exe (PyInstaller)."""

from __future__ import annotations

import sys
import types
from pathlib import Path


def _bootstrap_for_frozen() -> None:
    """
    En el exe, bess.data.__init__ importa pandas/streamlit.
    Registramos stubs de paquete para cargar solo ion/descargar y modbus.
    """
    if not getattr(sys, "frozen", False):
        return

    base = Path(sys._MEIPASS)
    data_dir = base / "bess" / "data"
    ingest_dir = data_dir / "ingest"
    ion_dir = ingest_dir / "ion"

    for name, path in (
        ("bess.data", data_dir),
        ("bess.data.ingest", ingest_dir),
        ("bess.data.ingest.ion", ion_dir),
    ):
        if name in sys.modules:
            continue
        mod = types.ModuleType(name)
        mod.__path__ = [str(path)]
        sys.modules[name] = mod


_bootstrap_for_frozen()

from bess.data.ingest.ion.descargar import main

if __name__ == "__main__":
    raise SystemExit(main())
