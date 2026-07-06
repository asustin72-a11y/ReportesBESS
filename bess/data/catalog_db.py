"""Catálogo de subestaciones y medidores en SQLite (fuente de verdad)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from bess.config.catalog import (
    ARCHIVO_MEDIDORES,
    ARCHIVO_SUBESTACIONES,
    ARCHIVO_TIPO_MEDIDOR,
    CAMPOS_MEDIDORES,
    CAMPOS_SUBESTACIONES,
    CAMPOS_TIPO_MEDIDOR,
    FORMATO_VALIDADO,
    _leer_csv,
)
from bess.config.paths import DIRECTORIO_TARIFAS, RUTA_BD_PERFILES

def _conectar() -> sqlite3.Connection:
    RUTA_BD_PERFILES.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RUTA_BD_PERFILES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

CATALOG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS catalog_tipo_medidor (
    tipo            INTEGER PRIMARY KEY,
    descripcion     TEXT NOT NULL,
    neteo           INTEGER NOT NULL DEFAULT 0,
    invertir        INTEGER NOT NULL DEFAULT 0,
    reactivos       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS catalog_subestaciones (
    numero          INTEGER PRIMARY KEY,
    nombre          TEXT NOT NULL UNIQUE,
    generacion      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS catalog_medidores (
    nombre              TEXT PRIMARY KEY,
    numero_serie        TEXT NOT NULL DEFAULT '',
    subestacion_numero  INTEGER NOT NULL
        REFERENCES catalog_subestaciones(numero),
    tipo_medidor        INTEGER NOT NULL
        REFERENCES catalog_tipo_medidor(tipo),
    descarga            TEXT NOT NULL,
    ip                  TEXT NOT NULL DEFAULT '',
    puerto              INTEGER NOT NULL DEFAULT 0,
    grupo_generacion    TEXT NOT NULL DEFAULT '',
    validado            TEXT
);
"""


def init_catalog_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(CATALOG_SCHEMA_SQL)


def _catalog_vacio(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS n FROM catalog_subestaciones").fetchone()
    return int(row["n"]) == 0


def _leer_filas_csv(directorio: Path) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    return (
        _leer_csv(directorio / ARCHIVO_TIPO_MEDIDOR),
        _leer_csv(directorio / ARCHIVO_SUBESTACIONES),
        _leer_csv(directorio / ARCHIVO_MEDIDORES),
    )


def _insertar_filas_en_bd(
    conn: sqlite3.Connection,
    filas_tipos: list[dict[str, str]],
    filas_subestaciones: list[dict[str, str]],
    filas_medidores: list[dict[str, str]],
) -> None:
    conn.execute("DELETE FROM catalog_medidores")
    conn.execute("DELETE FROM catalog_subestaciones")
    conn.execute("DELETE FROM catalog_tipo_medidor")

    for fila in filas_tipos:
        conn.execute(
            """
            INSERT INTO catalog_tipo_medidor (tipo, descripcion, neteo, invertir, reactivos)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(fila["Tipo"]),
                fila.get("Descripcion", ""),
                int(fila.get("Neteo") or 0),
                int(fila.get("Invertir") or 0),
                int(fila.get("Reactivos") or 0),
            ),
        )

    for fila in filas_subestaciones:
        conn.execute(
            """
            INSERT INTO catalog_subestaciones (numero, nombre, generacion)
            VALUES (?, ?, ?)
            """,
            (
                int(fila["Numero"]),
                fila.get("Nombre", ""),
                int(fila.get("Generacion") or 0),
            ),
        )

    for fila in filas_medidores:
        validado = (fila.get("Validado") or "").strip() or None
        conn.execute(
            """
            INSERT INTO catalog_medidores (
                nombre, numero_serie, subestacion_numero, tipo_medidor,
                descarga, ip, puerto, grupo_generacion, validado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fila.get("Nombre", ""),
                fila.get("Numero_Serie", ""),
                int(fila["Subestacion"]),
                int(fila["Tipo_Medidor"]),
                fila.get("Descarga", ""),
                fila.get("IP", ""),
                int(fila.get("Puerto") or 0),
                fila.get("Grupo_Generacion", ""),
                validado,
            ),
        )


def importar_catalogo_desde_csv(
    conn: sqlite3.Connection,
    directorio: Path | None = None,
) -> bool:
    """Importa CSV → BD si existen archivos. Devuelve True si importó."""
    base = Path(directorio or DIRECTORIO_TARIFAS)
    rutas = (
        base / ARCHIVO_TIPO_MEDIDOR,
        base / ARCHIVO_SUBESTACIONES,
        base / ARCHIVO_MEDIDORES,
    )
    if not all(r.is_file() for r in rutas):
        return False
    filas_tipos, filas_subs, filas_meds = _leer_filas_csv(base)
    _insertar_filas_en_bd(conn, filas_tipos, filas_subs, filas_meds)
    return True


def ensure_catalog_listo(directorio: Path | None = None) -> None:
    """Crea tablas de catálogo y migra desde CSV la primera vez si están vacías."""
    with _conectar() as conn:
        init_catalog_schema(conn)
        if _catalog_vacio(conn):
            importar_catalogo_desde_csv(conn, directorio)
        conn.commit()


def leer_filas_catalogo_bd() -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Lee tipos, subestaciones y medidores desde SQLite (formato dict compatible con catalog.py)."""
    ensure_catalog_listo()
    with _conectar() as conn:
        tipos = [
            {
                "Tipo": str(row["tipo"]),
                "Descripcion": row["descripcion"],
                "Neteo": str(row["neteo"]),
                "Invertir": str(row["invertir"]),
                "Reactivos": str(row["reactivos"]),
            }
            for row in conn.execute(
                "SELECT * FROM catalog_tipo_medidor ORDER BY tipo"
            ).fetchall()
        ]
        subs = [
            {
                "Numero": str(row["numero"]),
                "Nombre": row["nombre"],
                "Generacion": str(row["generacion"]),
            }
            for row in conn.execute(
                "SELECT * FROM catalog_subestaciones ORDER BY numero"
            ).fetchall()
        ]
        meds = [
            {
                "Nombre": row["nombre"],
                "Numero_Serie": row["numero_serie"] or "",
                "Subestacion": str(row["subestacion_numero"]),
                "Tipo_Medidor": str(row["tipo_medidor"]),
                "Descarga": row["descarga"],
                "IP": row["ip"] or "",
                "Puerto": str(row["puerto"]),
                "Grupo_Generacion": row["grupo_generacion"] or "",
                "Validado": row["validado"] or "",
            }
            for row in conn.execute(
                "SELECT * FROM catalog_medidores ORDER BY nombre"
            ).fetchall()
        ]
    return tipos, subs, meds


def guardar_filas_catalogo_bd(
    filas_tipos: list[dict[str, str]],
    filas_subestaciones: list[dict[str, str]],
    filas_medidores: list[dict[str, str]],
) -> None:
    """Persiste el catálogo en SQLite (tablas catalog_*)."""
    with _conectar() as conn:
        init_catalog_schema(conn)
        _insertar_filas_en_bd(conn, filas_tipos, filas_subestaciones, filas_medidores)
        conn.commit()


def marcar_medidores_validados_bd(
    nombres: list[str],
    cuando: datetime | None = None,
) -> list[str]:
    if not nombres:
        return []
    cuando = cuando or datetime.now()
    texto = cuando.strftime(FORMATO_VALIDADO)
    pendientes = {n.strip() for n in nombres if n.strip()}
    marcados: list[str] = []
    with _conectar() as conn:
        init_catalog_schema(conn)
        for nombre in pendientes:
            cur = conn.execute(
                "UPDATE catalog_medidores SET validado = ? WHERE nombre = ?",
                (texto, nombre),
            )
            if cur.rowcount:
                marcados.append(nombre)
        conn.commit()
    return marcados


def limpiar_validado_bd() -> int:
    """Vacía validado en todos los medidores del catálogo."""
    with _conectar() as conn:
        init_catalog_schema(conn)
        cur = conn.execute(
            "UPDATE catalog_medidores SET validado = NULL WHERE validado IS NOT NULL AND validado != ''"
        )
        n = cur.rowcount
        conn.commit()
    return n


def ruta_bd_catalogo() -> Path:
    return RUTA_BD_PERFILES
