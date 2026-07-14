#!/usr/bin/env python3
"""Elimina todos los registros ION_IUSA2 de la BD."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import RUTA_BD_PERFILES
from bess.data.ingest.ion.db import MEDIDOR_ION_IUSA2

mid = MEDIDOR_ION_IUSA2
with sqlite3.connect(RUTA_BD_PERFILES) as conn:
    antes = conn.execute(
        "SELECT COUNT(*) FROM perfil_carga WHERE medidor_id=?", (mid,)
    ).fetchone()[0]
    rango = conn.execute(
        "SELECT MIN(fecha), MAX(fecha) FROM perfil_carga WHERE medidor_id=?",
        (mid,),
    ).fetchone()
    fuentes = conn.execute(
        "SELECT fuente, COUNT(*) FROM perfil_carga WHERE medidor_id=? GROUP BY fuente",
        (mid,),
    ).fetchall()
    conn.execute("DELETE FROM perfil_carga WHERE medidor_id=?", (mid,))
    conn.execute("DELETE FROM sync_state WHERE medidor_id=?", (mid,))
    conn.commit()
    despues = conn.execute(
        "SELECT COUNT(*) FROM perfil_carga WHERE medidor_id=?", (mid,)
    ).fetchone()[0]
    sync = conn.execute(
        "SELECT COUNT(*) FROM sync_state WHERE medidor_id=?", (mid,)
    ).fetchone()[0]

print(f"BD: {RUTA_BD_PERFILES}")
print(f"ION_IUSA2 antes: {antes} registros  rango={rango}  fuentes={dict(fuentes)}")
print(f"ION_IUSA2 despues: {despues} registros")
print(f"sync_state ION_IUSA2: {sync} filas")
print("Listo para importar respaldo con:")
print("  python scripts/importar_ion_iusa2.py <archivo.csv>")
