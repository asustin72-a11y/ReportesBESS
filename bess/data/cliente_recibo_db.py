"""Datos fiscales / de servicio CFE por subestación (recibo simulado)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from bess.config.paths import RUTA_BD_PERFILES

CLIENTE_RECIBO_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS catalog_cliente_recibo (
    subestacion_nombre    TEXT PRIMARY KEY,
    razon_social          TEXT NOT NULL DEFAULT '',
    direccion             TEXT NOT NULL DEFAULT '',
    no_servicio           TEXT NOT NULL DEFAULT '',
    cuenta                TEXT NOT NULL DEFAULT '',
    rmu                   TEXT NOT NULL DEFAULT '',
    tarifa_etiqueta       TEXT NOT NULL DEFAULT '',
    multiplicador         TEXT NOT NULL DEFAULT '',
    no_hilos              TEXT NOT NULL DEFAULT '3',
    no_medidor            TEXT NOT NULL DEFAULT '',
    carga_conectada_kw    INTEGER,
    demanda_contratada_kw INTEGER
);
"""

CAMPOS_CLIENTE_RECIBO = (
    "Subestacion",
    "Razon_social",
    "Direccion",
    "No_servicio",
    "Cuenta",
    "RMU",
    "Tarifa",
    "Multiplicador",
    "No_hilos",
    "No_medidor",
    "Carga_conectada_kW",
    "Demanda_contratada_kW",
)

_SEP_DIRECCION = "|"

# Valores iniciales al crear filas (migración / subestaciones nuevas).
_SEED_POR_SUBESTACION: dict[str, dict[str, object]] = {
    "IUSA_1": {
        "razon_social": "INDUSTRIAS UNIDAS SA DE CV",
        "direccion": _SEP_DIRECCION.join(
            (
                "CARR PANAMERICANA MEXICO QUERE",
                "JOCOTITLAN C FZA",
                "C.P.50700",
                "JOCOTITLAN,MEX.",
            )
        ),
        "no_servicio": "306140811981",
        "cuenta": "84DG41H108350020",
        "rmu": "50700 14-07-31 IUN -390731 001 CFE",
        "tarifa_etiqueta": "DIST",
        "multiplicador": "44000",
        "no_hilos": "3",
        "no_medidor": "764DXX",
        "carga_conectada_kw": 31000,
        "demanda_contratada_kw": 31000,
    },
    "IUSA_2": {
        "razon_social": "INDUSTRIAS UNIDAS SA DE CV",
        "direccion": _SEP_DIRECCION.join(
            (
                "CARR PANAMERICANA MEXICO QUERE",
                "JOCOTITLAN C FZA",
                "C.P.50700",
                "JOCOTITLAN,MEX.",
            )
        ),
        "no_servicio": "",
        "cuenta": "",
        "rmu": "",
        "tarifa_etiqueta": "DIST",
        "multiplicador": "",
        "no_hilos": "3",
        "no_medidor": "ION IUSA 2",
        "carga_conectada_kw": None,
        "demanda_contratada_kw": None,
    },
    "IUSA_ARAGON": {
        "razon_social": "INDUSTRIAS UNIDAS SA DE CV",
        "direccion": _SEP_DIRECCION.join(
            (
                "ORIENTE 171 N 398",
                "PELICANO CP 07460 Y SAN JUAN DE ARAGON",
                "GRANJAS MODERNAS",
                "C.P.07460",
                "GUSTAVO A MADERO,D.F.",
            )
        ),
        "no_servicio": "575680900011",
        "cuenta": "82DL10D010050010",
        "rmu": "07460 68-09-17 IUN3-90731 001 CFE",
        "tarifa_etiqueta": "GDMTH",
        "multiplicador": "1200",
        "no_hilos": "3",
        "no_medidor": "MY500G",
        "carga_conectada_kw": 3823,
        "demanda_contratada_kw": 3560,
    },
}


def _conectar() -> sqlite3.Connection:
    RUTA_BD_PERFILES.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RUTA_BD_PERFILES)
    conn.row_factory = sqlite3.Row
    return conn


def init_cliente_recibo_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(CLIENTE_RECIBO_SCHEMA_SQL)


def _plantilla_vacia(nombre_sub: str) -> dict[str, object]:
    return {
        "subestacion_nombre": nombre_sub,
        "razon_social": "",
        "direccion": "",
        "no_servicio": "",
        "cuenta": "",
        "rmu": "",
        "tarifa_etiqueta": "",
        "multiplicador": "",
        "no_hilos": "3",
        "no_medidor": "",
        "carga_conectada_kw": None,
        "demanda_contratada_kw": None,
    }


def _insertar_fila(conn: sqlite3.Connection, fila: dict[str, object]) -> None:
    conn.execute(
        """
        INSERT INTO catalog_cliente_recibo (
            subestacion_nombre, razon_social, direccion, no_servicio, cuenta, rmu,
            tarifa_etiqueta, multiplicador, no_hilos, no_medidor,
            carga_conectada_kw, demanda_contratada_kw
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fila["subestacion_nombre"],
            fila.get("razon_social", ""),
            fila.get("direccion", ""),
            fila.get("no_servicio", ""),
            fila.get("cuenta", ""),
            fila.get("rmu", ""),
            fila.get("tarifa_etiqueta", ""),
            fila.get("multiplicador", ""),
            fila.get("no_hilos", "3"),
            fila.get("no_medidor", ""),
            fila.get("carga_conectada_kw"),
            fila.get("demanda_contratada_kw"),
        ),
    )


def _asegurar_filas_subestaciones(conn: sqlite3.Connection) -> None:
    nombres = [
        row["nombre"]
        for row in conn.execute(
            "SELECT nombre FROM catalog_subestaciones ORDER BY numero"
        ).fetchall()
    ]
    existentes = {
        row["subestacion_nombre"]
        for row in conn.execute(
            "SELECT subestacion_nombre FROM catalog_cliente_recibo"
        ).fetchall()
    }
    for nombre in nombres:
        if nombre in existentes:
            continue
        base = _SEED_POR_SUBESTACION.get(nombre, _plantilla_vacia(nombre))
        if "subestacion_nombre" not in base:
            base = {**base, "subestacion_nombre": nombre}
        _insertar_fila(conn, base)


def ensure_cliente_recibo_listo() -> None:
    from bess.data.catalog_db import ensure_catalog_listo

    ensure_catalog_listo()
    with _conectar() as conn:
        init_cliente_recibo_schema(conn)
        _asegurar_filas_subestaciones(conn)
        conn.commit()


def leer_filas_cliente_recibo() -> list[dict[str, str]]:
    ensure_cliente_recibo_listo()
    with _conectar() as conn:
        filas: list[dict[str, str]] = []
        for row in conn.execute(
            """
            SELECT
                s.nombre AS subestacion_nombre,
                c.razon_social,
                c.direccion,
                c.no_servicio,
                c.cuenta,
                c.rmu,
                c.tarifa_etiqueta,
                c.multiplicador,
                c.no_hilos,
                c.no_medidor,
                c.carga_conectada_kw,
                c.demanda_contratada_kw
            FROM catalog_subestaciones s
            LEFT JOIN catalog_cliente_recibo c
                ON c.subestacion_nombre = s.nombre
            ORDER BY s.numero
            """
        ).fetchall():
            nombre = row["subestacion_nombre"]
            tiene_datos = row["razon_social"] is not None
            filas.append(_row_a_fila_csv(row if tiene_datos else None, nombre))
    return filas


def _row_a_fila_csv(row: sqlite3.Row | None, nombre_sub: str) -> dict[str, str]:
    if row is None or not row["subestacion_nombre"]:
        vacio = _plantilla_vacia(nombre_sub)
        return {
            "Subestacion": nombre_sub,
            "Razon_social": str(vacio["razon_social"]),
            "Direccion": _direccion_a_texto(str(vacio["direccion"])),
            "No_servicio": str(vacio["no_servicio"]),
            "Cuenta": str(vacio["cuenta"]),
            "RMU": str(vacio["rmu"]),
            "Tarifa": str(vacio["tarifa_etiqueta"]),
            "Multiplicador": str(vacio["multiplicador"]),
            "No_hilos": str(vacio["no_hilos"]),
            "No_medidor": str(vacio["no_medidor"]),
            "Carga_conectada_kW": _entero_a_texto(vacio["carga_conectada_kw"]),
            "Demanda_contratada_kW": _entero_a_texto(vacio["demanda_contratada_kw"]),
        }
    return {
        "Subestacion": nombre_sub,
        "Razon_social": row["razon_social"] or "",
        "Direccion": _direccion_a_texto(row["direccion"] or ""),
        "No_servicio": row["no_servicio"] or "",
        "Cuenta": row["cuenta"] or "",
        "RMU": row["rmu"] or "",
        "Tarifa": row["tarifa_etiqueta"] or "",
        "Multiplicador": row["multiplicador"] or "",
        "No_hilos": row["no_hilos"] or "3",
        "No_medidor": row["no_medidor"] or "",
        "Carga_conectada_kW": _entero_a_texto(row["carga_conectada_kw"]),
        "Demanda_contratada_kW": _entero_a_texto(row["demanda_contratada_kw"]),
    }


def leer_cliente_recibo_subestacion(nombre_sub: str) -> dict[str, object] | None:
    ensure_cliente_recibo_listo()
    clave = (nombre_sub or "").strip()
    if not clave:
        return None
    with _conectar() as conn:
        row = conn.execute(
            "SELECT * FROM catalog_cliente_recibo WHERE subestacion_nombre = ?",
            (clave,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def guardar_filas_cliente_recibo(filas: list[dict[str, str]]) -> None:
    ensure_cliente_recibo_listo()
    with _conectar() as conn:
        init_cliente_recibo_schema(conn)
        for fila in filas:
            nombre = str(fila.get("Subestacion", "")).strip()
            if not nombre:
                continue
            datos = _fila_csv_a_db(fila, nombre)
            conn.execute(
                """
                INSERT INTO catalog_cliente_recibo (
                    subestacion_nombre, razon_social, direccion, no_servicio, cuenta, rmu,
                    tarifa_etiqueta, multiplicador, no_hilos, no_medidor,
                    carga_conectada_kw, demanda_contratada_kw
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(subestacion_nombre) DO UPDATE SET
                    razon_social = excluded.razon_social,
                    direccion = excluded.direccion,
                    no_servicio = excluded.no_servicio,
                    cuenta = excluded.cuenta,
                    rmu = excluded.rmu,
                    tarifa_etiqueta = excluded.tarifa_etiqueta,
                    multiplicador = excluded.multiplicador,
                    no_hilos = excluded.no_hilos,
                    no_medidor = excluded.no_medidor,
                    carga_conectada_kw = excluded.carga_conectada_kw,
                    demanda_contratada_kw = excluded.demanda_contratada_kw
                """,
                (
                    datos["subestacion_nombre"],
                    datos["razon_social"],
                    datos["direccion"],
                    datos["no_servicio"],
                    datos["cuenta"],
                    datos["rmu"],
                    datos["tarifa_etiqueta"],
                    datos["multiplicador"],
                    datos["no_hilos"],
                    datos["no_medidor"],
                    datos["carga_conectada_kw"],
                    datos["demanda_contratada_kw"],
                ),
            )
        conn.commit()


def _fila_csv_a_db(fila: dict[str, str], nombre_sub: str) -> dict[str, object]:
    return {
        "subestacion_nombre": nombre_sub,
        "razon_social": str(fila.get("Razon_social", "")).strip(),
        "direccion": _texto_a_direccion(str(fila.get("Direccion", ""))),
        "no_servicio": str(fila.get("No_servicio", "")).strip(),
        "cuenta": str(fila.get("Cuenta", "")).strip(),
        "rmu": str(fila.get("RMU", "")).strip(),
        "tarifa_etiqueta": str(fila.get("Tarifa", "")).strip().upper(),
        "multiplicador": str(fila.get("Multiplicador", "")).strip(),
        "no_hilos": str(fila.get("No_hilos", "3")).strip() or "3",
        "no_medidor": str(fila.get("No_medidor", "")).strip(),
        "carga_conectada_kw": _texto_a_entero(fila.get("Carga_conectada_kW")),
        "demanda_contratada_kw": _texto_a_entero(fila.get("Demanda_contratada_kW")),
    }


def _direccion_a_texto(almacenado: str) -> str:
    if not almacenado:
        return ""
    if _SEP_DIRECCION in almacenado:
        return "\n".join(p.strip() for p in almacenado.split(_SEP_DIRECCION) if p.strip())
    return almacenado.replace(_SEP_DIRECCION, "\n")


def _texto_a_direccion(texto: str) -> str:
    lineas = [ln.strip() for ln in texto.replace("\r", "").split("\n") if ln.strip()]
    return _SEP_DIRECCION.join(lineas)


def _entero_a_texto(valor: object) -> str:
    if valor is None or valor == "":
        return ""
    try:
        return str(int(valor))
    except (TypeError, ValueError):
        return ""


def _texto_a_entero(valor: object) -> int | None:
    texto = str(valor or "").strip()
    if not texto or texto.lower() in ("nan", "none", "—", "-"):
        return None
    try:
        return int(float(texto))
    except ValueError:
        return None


def direccion_como_tupla(almacenado: str) -> tuple[str, ...]:
    texto = _direccion_a_texto(almacenado)
    if not texto:
        return ("—",)
    return tuple(ln.strip() for ln in texto.split("\n") if ln.strip())


def ruta_bd_cliente_recibo() -> Path:
    return RUTA_BD_PERFILES
