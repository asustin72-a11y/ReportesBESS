"""Usuarios de la aplicación en SQLite."""

from __future__ import annotations

import sqlite3

from bess.config.paths import RUTA_BD_PERFILES
from bess.config.users import ROLES_VALIDOS, cargar_usuarios_fuente_externa

USUARIOS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS catalog_usuarios (
    username        TEXT PRIMARY KEY,
    password_hash   TEXT NOT NULL,
    rol             TEXT NOT NULL,
    nombre          TEXT NOT NULL,
    activo          INTEGER NOT NULL DEFAULT 1
);
"""


def _conectar() -> sqlite3.Connection:
    RUTA_BD_PERFILES.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RUTA_BD_PERFILES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_usuarios_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(USUARIOS_SCHEMA_SQL)


def _usuarios_vacios(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS n FROM catalog_usuarios").fetchone()
    return int(row["n"]) == 0


def _insertar_desde_dict(conn: sqlite3.Connection, usuarios: dict[str, dict]) -> None:
    for username, data in usuarios.items():
        conn.execute(
            """
            INSERT INTO catalog_usuarios (username, password_hash, rol, nombre, activo)
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                username,
                data["password"],
                data["rol"],
                data.get("nombre", username),
            ),
        )


def ensure_usuarios_listo() -> None:
    """Crea tabla de usuarios y migra desde secrets/env la primera vez."""
    with _conectar() as conn:
        init_usuarios_schema(conn)
        if _usuarios_vacios(conn):
            externos = cargar_usuarios_fuente_externa()
            if externos:
                _insertar_desde_dict(conn, externos)
        conn.commit()


def leer_usuarios_dict(*, solo_activos: bool = True) -> dict[str, dict]:
    """Formato compatible con login: {user: {password, rol, nombre}}."""
    ensure_usuarios_listo()
    usuarios: dict[str, dict] = {}
    query = "SELECT username, password_hash, rol, nombre, activo FROM catalog_usuarios"
    if solo_activos:
        query += " WHERE activo = 1"
    with _conectar() as conn:
        for row in conn.execute(query).fetchall():
            usuarios[str(row["username"])] = {
                "password": row["password_hash"],
                "rol": row["rol"],
                "nombre": row["nombre"],
            }
    return usuarios


def leer_filas_usuarios() -> list[dict[str, str]]:
    ensure_usuarios_listo()
    filas: list[dict[str, str]] = []
    with _conectar() as conn:
        for row in conn.execute(
            "SELECT username, nombre, rol, activo FROM catalog_usuarios ORDER BY username"
        ).fetchall():
            filas.append({
                "Usuario": row["username"],
                "Nombre": row["nombre"],
                "Rol": row["rol"],
                "Activo": "1" if int(row["activo"]) else "0",
                "Nueva_contraseña": "",
            })
    return filas


def _hashes_actuales() -> dict[str, str]:
    with _conectar() as conn:
        return {
            str(row["username"]): row["password_hash"]
            for row in conn.execute(
                "SELECT username, password_hash FROM catalog_usuarios"
            ).fetchall()
        }


def guardar_filas_usuarios(filas: list[dict[str, str]]) -> None:
    hashes = _hashes_actuales()
    nuevos: list[tuple[str, str, str, str, int]] = []
    for fila in filas:
        username = (fila.get("Usuario") or "").strip()
        if not username:
            raise ValueError("Hay filas sin nombre de usuario.")
        nombre = (fila.get("Nombre") or "").strip() or username
        rol = (fila.get("Rol") or "").strip()
        activo = 1 if str(fila.get("Activo", "1")).strip() in ("1", "true", "True", "SI") else 0
        pwd_nueva = (fila.get("Nueva_contraseña") or "").strip()
        if rol not in ROLES_VALIDOS:
            raise ValueError(f'Usuario "{username}": rol "{rol}" no válido.')
        if username in hashes:
            pwd_hash = hashes[username]
            if pwd_nueva:
                from bess.config.users import hash_password

                pwd_hash = hash_password(pwd_nueva)
        else:
            if not pwd_nueva:
                raise ValueError(f'Usuario nuevo "{username}": indique Nueva_contraseña.')
            from bess.config.users import hash_password

            pwd_hash = hash_password(pwd_nueva)
        nuevos.append((username, pwd_hash, rol, nombre, activo))

    with _conectar() as conn:
        init_usuarios_schema(conn)
        conn.execute("DELETE FROM catalog_usuarios")
        conn.executemany(
            """
            INSERT INTO catalog_usuarios (username, password_hash, rol, nombre, activo)
            VALUES (?, ?, ?, ?, ?)
            """,
            nuevos,
        )
        conn.commit()


def invalidar_cache_usuarios() -> None:
    try:
        from bess.ui.auth import get_usuarios

        get_usuarios.clear()
    except Exception:
        pass
