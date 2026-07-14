#!/usr/bin/env python3
"""CLI: exportar SQLite → CSV ArchivosFuente."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.data.ingest.ion.export_csv import main

if __name__ == '__main__':
    raise SystemExit(main())
