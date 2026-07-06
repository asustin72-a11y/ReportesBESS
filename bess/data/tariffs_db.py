"""Tarifas mensuales en SQLite (fuente de verdad)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from bess.config.constants import ARCHIVO_TARIFAS, TIPOS_TARIFA
from bess.config.paths import DIRECTORIO_TARIFAS, RUTA_BD_PERFILES

TARIFAS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS catalog_tarifas (
    tarifa  TEXT NOT NULL,
    mes     INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    valor   REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (tarifa, mes)
);
"""


def _conectar() -> sqlite3.Connection:
    RUTA_BD_PERFILES.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RUTA_BD_PERFILES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_tarifas_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(TARIFAS_SCHEMA_SQL)


def _tarifas_vacias(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS n FROM catalog_tarifas").fetchone()
    return int(row["n"]) == 0


_ALIASES_TARIFA = {
    "distribución": "Distribucion",
    "transmisión": "Transmision",
    "cargo fijo": "CargoFijo",
    "servicios auxiliares": "ServiciosAuxiliares",
}


def _normalizar_tipo(tipo: str) -> str:
    limpio = str(tipo).strip()
    return _ALIASES_TARIFA.get(limpio.lower(), limpio)


def _plantilla_filas() -> list[tuple[str, int, float]]:
    return [(tipo, mes, 0.0) for tipo in TIPOS_TARIFA for mes in range(1, 13)]


def _insertar_valores(
    conn: sqlite3.Connection,
    filas: list[tuple[str, int, float]],
) -> None:
    conn.execute("DELETE FROM catalog_tarifas")
    conn.executemany(
        "INSERT INTO catalog_tarifas (tarifa, mes, valor) VALUES (?, ?, ?)",
        filas,
    )


def importar_tarifas_desde_csv(conn: sqlite3.Connection) -> bool:
    ruta = DIRECTORIO_TARIFAS / ARCHIVO_TARIFAS
    if not ruta.is_file():
        return False
    try:
        df = pd.read_csv(ruta, encoding="utf-8-sig")
        df.columns = [str(c).strip() for c in df.columns]
    except Exception:
        return False
    filas: list[tuple[str, int, float]] = []
    for _, row in df.iterrows():
        tipo = _normalizar_tipo(row.get("Tarifa", ""))
        if not tipo:
            continue
        for mes in range(1, 13):
            valor = float(row.get(str(mes), 0) or 0)
            filas.append((tipo, mes, valor))
    if not filas:
        return False
    _insertar_valores(conn, filas)
    return True


def ensure_tarifas_listo() -> None:
    with _conectar() as conn:
        init_tarifas_schema(conn)
        if _tarifas_vacias(conn):
            if not importar_tarifas_desde_csv(conn):
                _insertar_valores(conn, _plantilla_filas())
        conn.commit()


def leer_tarifas_dict() -> dict[str, dict[int, float]]:
    """Formato usado por cargar_tarifas() y cálculos CFE."""
    ensure_tarifas_listo()
    tarifas: dict[str, dict[int, float]] = {
        tipo: {mes: 0.0 for mes in range(1, 13)} for tipo in TIPOS_TARIFA
    }
    with _conectar() as conn:
        for row in conn.execute("SELECT tarifa, mes, valor FROM catalog_tarifas").fetchall():
            tipo = str(row["tarifa"])
            mes = int(row["mes"])
            tarifas.setdefault(tipo, {m: 0.0 for m in range(1, 13)})
            tarifas[tipo][mes] = float(row["valor"] or 0)
    return tarifas


def guardar_tarifas_dict(tarifas: dict[str, dict[int, float]]) -> None:
    filas: list[tuple[str, int, float]] = []
    for tipo in TIPOS_TARIFA:
        valores = tarifas.get(tipo, {})
        for mes in range(1, 13):
            filas.append((tipo, mes, float(valores.get(mes, 0) or 0)))
    with _conectar() as conn:
        init_tarifas_schema(conn)
        _insertar_valores(conn, filas)
        conn.commit()


def ruta_bd_tarifas() -> Path:
    return RUTA_BD_PERFILES
