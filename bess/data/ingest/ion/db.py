"""Base de datos SQLite para perfiles de carga."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bess.config.paths import RUTA_BD_PERFILES

RUTA_BD_DEFAULT = RUTA_BD_PERFILES
MEDIDOR_ION = 'ION'

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS medidores (
    id              TEXT PRIMARY KEY,
    nombre          TEXT NOT NULL,
    tipo            TEXT,
    ip              TEXT,
    dr_modulo       INTEGER,
    intervalo_min   INTEGER NOT NULL DEFAULT 5,
    activo          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS perfil_carga (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    medidor_id      TEXT NOT NULL REFERENCES medidores(id),
    fecha           TEXT NOT NULL,
    kwh_rec         REAL NOT NULL DEFAULT 0,
    kwh_ent         REAL NOT NULL DEFAULT 0,
    kvarh_q1        REAL NOT NULL DEFAULT 0,
    kvarh_q2        REAL NOT NULL DEFAULT 0,
    kvarh_q3        REAL NOT NULL DEFAULT 0,
    kvarh_q4        REAL NOT NULL DEFAULT 0,
    fuente          TEXT NOT NULL DEFAULT 'modbus',
    ingested_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (medidor_id, fecha)
);

CREATE TABLE IF NOT EXISTS sync_state (
    medidor_id      TEXT PRIMARY KEY REFERENCES medidores(id),
    ultima_fecha    TEXT,
    ultima_sync_ok  TEXT
);

CREATE TABLE IF NOT EXISTS sync_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    medidor_id          TEXT NOT NULL REFERENCES medidores(id),
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    desde               TEXT,
    hasta               TEXT,
    registros_leidos    INTEGER DEFAULT 0,
    registros_insertados INTEGER DEFAULT 0,
    registros_actualizados INTEGER DEFAULT 0,
    status              TEXT NOT NULL,
    error_message       TEXT
);

CREATE INDEX IF NOT EXISTS idx_perfil_medidor_fecha
    ON perfil_carga (medidor_id, fecha);
"""

MEDIDORES_INICIALES = (
    ('ION', 'Medidor ION 8650 planta', 'ION8650', '172.16.111.209', 1, 5),
    ('BESS', 'Medidor BESS', 'BESS', None, None, 5),
    ('BANCO', 'Medidor BANCO', 'BANCO', None, None, 5),
)


@dataclass
class ResultadoUpsert:
    insertados: int = 0
    actualizados: int = 0


def conectar_bd(ruta: Path = RUTA_BD_DEFAULT) -> sqlite3.Connection:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db(ruta: Path = RUTA_BD_DEFAULT) -> Path:
    with conectar_bd(ruta) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executemany(
            """
            INSERT OR IGNORE INTO medidores
                (id, nombre, tipo, ip, dr_modulo, intervalo_min)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            MEDIDORES_INICIALES,
        )
        conn.commit()
    return ruta


def get_ultima_fecha(
    conn: sqlite3.Connection,
    medidor_id: str,
    zona: ZoneInfo | None = None,
) -> datetime | None:
    row = conn.execute(
        'SELECT ultima_fecha FROM sync_state WHERE medidor_id = ?',
        (medidor_id,),
    ).fetchone()
    if row and row['ultima_fecha']:
        return _parse_fecha_bd(row['ultima_fecha'], zona)

    row = conn.execute(
        'SELECT MAX(fecha) AS max_fecha FROM perfil_carga WHERE medidor_id = ?',
        (medidor_id,),
    ).fetchone()
    if row and row['max_fecha']:
        return _parse_fecha_bd(row['max_fecha'], zona)
    return None


def _parse_fecha_bd(texto: str, zona: ZoneInfo | None) -> datetime:
    dt = datetime.fromisoformat(texto)
    if dt.tzinfo is None and zona is not None:
        dt = dt.replace(tzinfo=zona)
    return dt


def upsert_registros(
    conn: sqlite3.Connection,
    medidor_id: str,
    registros: list[dict[str, Any]],
    fuente: str = 'modbus',
    respetar_fuente: str | None = None,
) -> ResultadoUpsert:
    resultado = ResultadoUpsert()
    if not registros:
        return resultado

    if respetar_fuente and fuente != respetar_fuente:
        fechas = [r['fecha'] for r in registros]
        protegidos = {
            row['fecha']
            for row in conn.execute(
                f"""
                SELECT fecha FROM perfil_carga
                WHERE medidor_id = ? AND fuente = ? AND fecha IN ({','.join('?' * len(fechas))})
                """,
                [medidor_id, respetar_fuente, *fechas],
            )
        }
        if protegidos:
            registros = [r for r in registros if r['fecha'] not in protegidos]
        if not registros:
            return resultado

    existentes = {
        row['fecha']
        for row in conn.execute(
            f"""
            SELECT fecha FROM perfil_carga
            WHERE medidor_id = ? AND fecha IN ({','.join('?' * len(registros))})
            """,
            [medidor_id, *[r['fecha'] for r in registros]],
        )
    }

    conn.executemany(
        """
        INSERT INTO perfil_carga (
            medidor_id, fecha, kwh_rec, kwh_ent,
            kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4, fuente
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(medidor_id, fecha) DO UPDATE SET
            kwh_rec = excluded.kwh_rec,
            kwh_ent = excluded.kwh_ent,
            kvarh_q1 = excluded.kvarh_q1,
            kvarh_q2 = excluded.kvarh_q2,
            kvarh_q3 = excluded.kvarh_q3,
            kvarh_q4 = excluded.kvarh_q4,
            fuente = excluded.fuente,
            ingested_at = datetime('now')
        """,
        [
            (
                medidor_id,
                r['fecha'],
                r['kwh_rec'],
                r['kwh_ent'],
                r['kvarh_q1'],
                r['kvarh_q2'],
                r['kvarh_q3'],
                r['kvarh_q4'],
                fuente,
            )
            for r in registros
        ],
    )

    for r in registros:
        if r['fecha'] in existentes:
            resultado.actualizados += 1
        else:
            resultado.insertados += 1

    return resultado


def actualizar_sync_state(
    conn: sqlite3.Connection,
    medidor_id: str,
    ultima_fecha: str,
) -> None:
    ahora = datetime.now().isoformat(timespec='seconds')
    conn.execute(
        """
        INSERT INTO sync_state (medidor_id, ultima_fecha, ultima_sync_ok)
        VALUES (?, ?, ?)
        ON CONFLICT(medidor_id) DO UPDATE SET
            ultima_fecha = excluded.ultima_fecha,
            ultima_sync_ok = excluded.ultima_sync_ok
        """,
        (medidor_id, ultima_fecha, ahora),
    )


def iniciar_sync_log(conn: sqlite3.Connection, medidor_id: str, desde: str, hasta: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO sync_log (medidor_id, started_at, desde, hasta, status)
        VALUES (?, datetime('now'), ?, ?, 'running')
        """,
        (medidor_id, desde, hasta),
    )
    return int(cur.lastrowid)


def cerrar_sync_log(
    conn: sqlite3.Connection,
    log_id: int,
    status: str,
    leidos: int,
    insertados: int,
    actualizados: int,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE sync_log SET
            finished_at = datetime('now'),
            status = ?,
            registros_leidos = ?,
            registros_insertados = ?,
            registros_actualizados = ?,
            error_message = ?
        WHERE id = ?
        """,
        (status, leidos, insertados, actualizados, error, log_id),
    )


def contar_registros(conn: sqlite3.Connection, medidor_id: str) -> int:
    row = conn.execute(
        'SELECT COUNT(*) AS total FROM perfil_carga WHERE medidor_id = ?',
        (medidor_id,),
    ).fetchone()
    return int(row['total']) if row else 0


def intercambiar_kwh_medidor(conn: sqlite3.Connection, medidor_id: str) -> int:
    """Intercambia kwh_rec y kwh_ent (corrección legacy)."""
    cur = conn.execute(
        """
        UPDATE perfil_carga
        SET kwh_rec = kwh_ent, kwh_ent = kwh_rec
        WHERE medidor_id = ?
        """,
        (medidor_id,),
    )
    return cur.rowcount


def vaciar_perfiles(ruta: Path = RUTA_BD_DEFAULT) -> int:
    """Elimina todos los registros de perfil y estado de sync (conserva catálogo medidores)."""
    init_db(ruta)
    with conectar_bd(ruta) as conn:
        cur = conn.execute('DELETE FROM perfil_carga')
        conn.execute('DELETE FROM sync_state')
        conn.commit()
        return cur.rowcount
