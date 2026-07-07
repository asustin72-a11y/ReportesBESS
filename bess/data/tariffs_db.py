"""Tarifas mensuales en SQLite (fuente de verdad)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from bess.config.constants import ARCHIVO_TARIFAS, ARCHIVO_TARIFAS_GDMTH, TIPOS_TARIFA
from bess.config.esquema_tarifa import ESQUEMA_DEFAULT, ESQUEMA_GDMTH
from bess.config.paths import DIRECTORIO_TARIFAS, RUTA_BD_PERFILES

TARIFAS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS catalog_tarifas (
    esquema_id  TEXT NOT NULL DEFAULT 'DIST',
    tarifa      TEXT NOT NULL,
    mes         INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    valor       REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (esquema_id, tarifa, mes)
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
    _migrar_tarifas_esquema(conn)


def _migrar_tarifas_esquema(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(catalog_tarifas)")}
    if "esquema_id" in cols:
        return
    if not cols:
        return
    conn.execute(
        """
        CREATE TABLE catalog_tarifas_new (
            esquema_id  TEXT NOT NULL DEFAULT 'DIST',
            tarifa      TEXT NOT NULL,
            mes         INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
            valor       REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (esquema_id, tarifa, mes)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO catalog_tarifas_new (esquema_id, tarifa, mes, valor)
        SELECT 'DIST', tarifa, mes, valor FROM catalog_tarifas
        """
    )
    conn.execute("DROP TABLE catalog_tarifas")
    conn.execute("ALTER TABLE catalog_tarifas_new RENAME TO catalog_tarifas")


def _tarifas_vacias(conn: sqlite3.Connection, esquema_id: str = ESQUEMA_DEFAULT) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM catalog_tarifas WHERE esquema_id = ?",
        (esquema_id,),
    ).fetchone()
    return int(row["n"]) == 0


_ALIASES_TARIFA = {
    "distribución": "Distribucion",
    "transmisión": "Transmision",
    "cargo fijo": "CargoFijo",
    "fijo": "CargoFijo",
    "intermedia": "Intermedio",
    "servicios auxiliares": "ServiciosAuxiliares",
}


def _normalizar_tipo(tipo: str) -> str:
    limpio = str(tipo).strip()
    return _ALIASES_TARIFA.get(limpio.lower(), limpio)


def _plantilla_filas(esquema_id: str = ESQUEMA_DEFAULT) -> list[tuple[str, str, int, float]]:
    return [(esquema_id, tipo, mes, 0.0) for tipo in TIPOS_TARIFA for mes in range(1, 13)]


def _insertar_valores(
    conn: sqlite3.Connection,
    filas: list[tuple[str, str, int, float]],
    *,
    esquema_id: str | None = None,
) -> None:
    if esquema_id:
        conn.execute("DELETE FROM catalog_tarifas WHERE esquema_id = ?", (esquema_id,))
    else:
        conn.execute("DELETE FROM catalog_tarifas")
    conn.executemany(
        "INSERT INTO catalog_tarifas (esquema_id, tarifa, mes, valor) VALUES (?, ?, ?, ?)",
        filas,
    )


def _tarifas_son_placeholder(conn: sqlite3.Connection, esquema_id: str) -> bool:
    """True si el esquema solo tiene ceros (plantilla sin precios reales)."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM catalog_tarifas
        WHERE esquema_id = ? AND ABS(valor) > 1e-9
        """,
        (esquema_id,),
    ).fetchone()
    return int(row["n"]) == 0


def _asegurar_esquema_placeholder(conn: sqlite3.Connection, esquema_id: str) -> None:
    if not _tarifas_vacias(conn, esquema_id):
        return
    _insertar_valores(conn, _plantilla_filas(esquema_id), esquema_id=esquema_id)


def _asegurar_esquema_desde_csv(
    conn: sqlite3.Connection,
    esquema_id: str,
    archivo: str,
) -> None:
    ruta = DIRECTORIO_TARIFAS / archivo
    if not ruta.is_file():
        _asegurar_esquema_placeholder(conn, esquema_id)
        return
    if _tarifas_vacias(conn, esquema_id) or _tarifas_son_placeholder(conn, esquema_id):
        if not importar_tarifas_desde_csv(conn, esquema_id, archivo):
            _asegurar_esquema_placeholder(conn, esquema_id)


def importar_tarifas_desde_csv(
    conn: sqlite3.Connection,
    esquema_id: str = ESQUEMA_DEFAULT,
    archivo: str | None = None,
) -> bool:
    ruta = DIRECTORIO_TARIFAS / (archivo or ARCHIVO_TARIFAS)
    if not ruta.is_file():
        return False
    try:
        df = pd.read_csv(ruta, encoding="utf-8-sig")
        df.columns = [str(c).strip() for c in df.columns]
    except Exception:
        return False
    filas: list[tuple[str, str, int, float]] = []
    for _, row in df.iterrows():
        tipo = _normalizar_tipo(row.get("Tarifa", ""))
        if not tipo:
            continue
        for mes in range(1, 13):
            valor = float(row.get(str(mes), 0) or 0)
            filas.append((esquema_id, tipo, mes, valor))
    if not filas:
        return False
    _insertar_valores(conn, filas, esquema_id=esquema_id)
    return True


def ensure_tarifas_listo() -> None:
    with _conectar() as conn:
        init_tarifas_schema(conn)
        if _tarifas_vacias(conn, ESQUEMA_DEFAULT):
            if not importar_tarifas_desde_csv(conn, ESQUEMA_DEFAULT):
                _insertar_valores(conn, _plantilla_filas(ESQUEMA_DEFAULT), esquema_id=ESQUEMA_DEFAULT)
        _asegurar_esquema_desde_csv(conn, ESQUEMA_GDMTH, ARCHIVO_TARIFAS_GDMTH)
        conn.commit()


def leer_tarifas_dict(esquema_id: str = ESQUEMA_DEFAULT) -> dict[str, dict[int, float]]:
    """Formato usado por cargar_tarifas() y cálculos CFE."""
    esquema = (esquema_id or ESQUEMA_DEFAULT).strip().upper()
    ensure_tarifas_listo()
    tarifas: dict[str, dict[int, float]] = {
        tipo: {mes: 0.0 for mes in range(1, 13)} for tipo in TIPOS_TARIFA
    }
    with _conectar() as conn:
        for row in conn.execute(
            "SELECT tarifa, mes, valor FROM catalog_tarifas WHERE esquema_id = ?",
            (esquema,),
        ).fetchall():
            tipo = str(row["tarifa"])
            mes = int(row["mes"])
            tarifas.setdefault(tipo, {m: 0.0 for m in range(1, 13)})
            tarifas[tipo][mes] = float(row["valor"] or 0)
    return tarifas


def guardar_tarifas_dict(
    tarifas: dict[str, dict[int, float]],
    esquema_id: str = ESQUEMA_DEFAULT,
) -> None:
    esquema = (esquema_id or ESQUEMA_DEFAULT).strip().upper()
    filas: list[tuple[str, str, int, float]] = []
    for tipo in TIPOS_TARIFA:
        valores = tarifas.get(tipo, {})
        for mes in range(1, 13):
            filas.append((esquema, tipo, mes, float(valores.get(mes, 0) or 0)))
    with _conectar() as conn:
        init_tarifas_schema(conn)
        _insertar_valores(conn, filas, esquema_id=esquema)
        conn.commit()


def ruta_bd_tarifas() -> Path:
    return RUTA_BD_PERFILES
