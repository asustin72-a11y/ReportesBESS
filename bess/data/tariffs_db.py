"""Tarifas mensuales en SQLite (fuente de verdad)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from bess.config.constants import ARCHIVO_TARIFAS, ARCHIVO_TARIFAS_GDMTH, TIPOS_TARIFA, archivo_tarifas_csv
from bess.config.esquema_tarifa import (
    ESQUEMA_DEFAULT,
    ESQUEMA_GDMTH,
    ESQUEMA_PDBT,
    ESQUEMA_T1,
    ESQUEMAS_CATALOGO,
)
from bess.config.paths import DIRECTORIO_TARIFAS, RUTA_BD_PERFILES

TARIFAS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS catalog_tarifas (
    esquema_id  TEXT NOT NULL DEFAULT 'DIST',
    tarifa      TEXT NOT NULL,
    mes         INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    valor       REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (esquema_id, tarifa, mes)
);

CREATE TABLE IF NOT EXISTS catalog_tarifas_hist (
    esquema_id  TEXT NOT NULL DEFAULT 'DIST',
    tarifa      TEXT NOT NULL,
    anio        INTEGER NOT NULL CHECK (anio BETWEEN 2000 AND 2100),
    mes         INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    valor       REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (esquema_id, tarifa, anio, mes)
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
        from datetime import date

        anio = date.today().year
        for esquema in (ESQUEMA_PDBT, ESQUEMA_T1):
            _asegurar_esquema_desde_csv(
                conn, esquema, archivo_tarifas_csv(anio, esquema=esquema)
            )
        conn.commit()


def _es_cero_tarifa(valor: float | int | None) -> bool:
    return abs(float(valor or 0)) <= 1e-9


def _matriz_vacia() -> dict[str, dict[int, float]]:
    return {tipo: {mes: 0.0 for mes in range(1, 13)} for tipo in TIPOS_TARIFA}


def fusionar_preferir_positivo(
    *matrices: dict[str, dict[int, float]] | None,
) -> dict[str, dict[int, float]]:
    """Une matrices mes a mes: un cero nunca pisa un valor ya cargado (>0)."""
    out = _matriz_vacia()
    for matriz in matrices:
        if not matriz:
            continue
        for tipo, valores in matriz.items():
            out.setdefault(tipo, {m: 0.0 for m in range(1, 13)})
            for mes, valor in valores.items():
                mes_i = int(mes)
                nuevo = float(valor or 0)
                if _es_cero_tarifa(nuevo):
                    continue
                out[tipo][mes_i] = nuevo
    return out


def _matriz_desde_csv(esquema_id: str, anio: int) -> dict[str, dict[int, float]] | None:
    ruta = DIRECTORIO_TARIFAS / archivo_tarifas_csv(anio, esquema=esquema_id)
    if not ruta.is_file():
        return None
    try:
        df = pd.read_csv(ruta, encoding="utf-8-sig")
        df.columns = [str(c).strip() for c in df.columns]
    except Exception:
        return None
    tarifas = _matriz_vacia()
    for _, row in df.iterrows():
        tipo = _normalizar_tipo(row.get("Tarifa", ""))
        if not tipo:
            continue
        tarifas.setdefault(tipo, {m: 0.0 for m in range(1, 13)})
        for mes in range(1, 13):
            tarifas[tipo][mes] = float(row.get(str(mes), 0) or 0)
    return tarifas


def _leer_tarifas_bd(esquema: str) -> dict[str, dict[int, float]]:
    ensure_tarifas_listo()
    tarifas = _matriz_vacia()
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


def leer_tarifas_dict(
    esquema_id: str = ESQUEMA_DEFAULT,
    anio: int | None = None,
) -> dict[str, dict[int, float]]:
    """Formato usado por cargar_tarifas() y cálculos CFE.

    Si se indica ``anio``, fusiona CSV anual ∪ ``catalog_tarifas`` sin que un
    cero pise un valor ya cargado. Sin ``anio``, lee solo la BD.
    """
    esquema = (esquema_id or ESQUEMA_DEFAULT).strip().upper()
    if esquema not in ESQUEMAS_CATALOGO:
        esquema = ESQUEMA_DEFAULT
    bd = _leer_tarifas_bd(esquema)
    if anio is None:
        return bd
    return fusionar_preferir_positivo(_matriz_desde_csv(esquema, int(anio)), bd)


def leer_matriz_para_sync(
    esquema_id: str,
    anio: int,
) -> dict[str, dict[int, float]]:
    """Base para merge CFE: CSV ∪ BD, protegiendo valores > 0."""
    return leer_tarifas_dict(esquema_id, anio)


def guardar_tarifas_dict(
    tarifas: dict[str, dict[int, float]],
    esquema_id: str = ESQUEMA_DEFAULT,
    anio: int | None = None,
    *,
    preservar_positivos: bool = False,
) -> None:
    """Persiste la matriz en catalog_tarifas (snapshot actual; ``anio`` se ignora en BD).

    Si ``preservar_positivos`` es True (sync CFE), un cero entrante no pisa
    un valor ya guardado > 0.
    """
    del anio  # API compatible con scripts anuales; BD es sin año.
    esquema = (esquema_id or ESQUEMA_DEFAULT).strip().upper()
    if esquema not in ESQUEMAS_CATALOGO:
        esquema = ESQUEMA_DEFAULT
    matriz = tarifas
    if preservar_positivos:
        matriz = fusionar_preferir_positivo(_leer_tarifas_bd(esquema), tarifas)
    filas: list[tuple[str, str, int, float]] = []
    for tipo in TIPOS_TARIFA:
        valores = matriz.get(tipo, {})
        for mes in range(1, 13):
            filas.append((esquema, tipo, mes, float(valores.get(mes, 0) or 0)))
    with _conectar() as conn:
        init_tarifas_schema(conn)
        _insertar_valores(conn, filas, esquema_id=esquema)
        conn.commit()


def upsert_tarifas_hist_mes(
    tarifas: dict[str, dict[int, float]],
    esquema_id: str,
    anio: int,
    mes: int,
) -> None:
    """Escribe un mes en catalog_tarifas_hist; un cero no borra un valor previo >0."""
    esquema = (esquema_id or ESQUEMA_DEFAULT).strip().upper()
    if esquema not in ESQUEMAS_CATALOGO:
        esquema = ESQUEMA_DEFAULT
    anio_i = int(anio)
    mes_i = int(mes)
    if not 1 <= mes_i <= 12:
        raise ValueError(f"Mes inválido: {mes}")
    with _conectar() as conn:
        init_tarifas_schema(conn)
        prev = {
            str(row["tarifa"]): float(row["valor"] or 0)
            for row in conn.execute(
                """
                SELECT tarifa, valor FROM catalog_tarifas_hist
                WHERE esquema_id = ? AND anio = ? AND mes = ?
                """,
                (esquema, anio_i, mes_i),
            ).fetchall()
        }
        filas: list[tuple[str, str, int, int, float]] = []
        for tipo in TIPOS_TARIFA:
            nuevo = float(tarifas.get(tipo, {}).get(mes_i, 0) or 0)
            actual = float(prev.get(tipo, 0) or 0)
            if _es_cero_tarifa(nuevo) and not _es_cero_tarifa(actual):
                valor = actual
            else:
                valor = nuevo
            filas.append((esquema, tipo, anio_i, mes_i, valor))
        conn.execute(
            """
            DELETE FROM catalog_tarifas_hist
            WHERE esquema_id = ? AND anio = ? AND mes = ?
            """,
            (esquema, anio_i, mes_i),
        )
        conn.executemany(
            """
            INSERT INTO catalog_tarifas_hist (esquema_id, tarifa, anio, mes, valor)
            VALUES (?, ?, ?, ?, ?)
            """,
            filas,
        )
        conn.commit()


def importar_tarifas_historicas_dist_desde_xlsx(
    ruta_xlsx: str | Path,
    esquema_id: str = ESQUEMA_DEFAULT,
) -> tuple[bool, str]:
    """Importa TDIST histórico (columnas Mes, Base, Intermedio, Punta, Capacidad)."""
    ruta = Path(ruta_xlsx)
    if not ruta.is_file():
        return False, f"No existe el archivo: {ruta}"

    try:
        df = pd.read_excel(ruta)
    except Exception as exc:
        return False, f"No se pudo leer Excel: {exc}"

    df.columns = [str(c).strip() for c in df.columns]
    if "Mes" not in df.columns:
        return False, "Falta la columna Mes."

    renames = {"Intermedio ": "Intermedio"}
    df = df.rename(columns=renames)
    requeridas = ["Mes", "Base", "Intermedio", "Punta"]
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        return False, f"Faltan columnas: {', '.join(faltantes)}"

    df["Mes"] = pd.to_datetime(df["Mes"], errors="coerce")
    df = df[df["Mes"].notna()].copy()
    if df.empty:
        return False, "No hay filas válidas con Mes."

    filas: list[tuple[str, str, int, int, float]] = []
    tipos_presentes = [t for t in ("Base", "Intermedio", "Punta", "Capacidad") if t in df.columns]
    for _, row in df.iterrows():
        fecha = row["Mes"]
        anio = int(fecha.year)
        mes = int(fecha.month)
        for tipo in tipos_presentes:
            valor = float(pd.to_numeric(row.get(tipo, 0), errors="coerce") or 0.0)
            filas.append((esquema_id.upper(), tipo, anio, mes, valor))

    with _conectar() as conn:
        init_tarifas_schema(conn)
        conn.execute("DELETE FROM catalog_tarifas_hist WHERE esquema_id = ?", (esquema_id.upper(),))
        conn.executemany(
            """
            INSERT INTO catalog_tarifas_hist (esquema_id, tarifa, anio, mes, valor)
            VALUES (?, ?, ?, ?, ?)
            """,
            filas,
        )
        conn.commit()
    return True, f"{len(filas)} tarifa(s) históricas importadas"


def leer_tarifas_historicas_dict(
    esquema_id: str = ESQUEMA_DEFAULT,
) -> dict[str, dict[tuple[int, int], float]]:
    """Formato: {tipo: {(anio, mes): valor}}."""
    esquema = (esquema_id or ESQUEMA_DEFAULT).strip().upper()
    ensure_tarifas_listo()
    tarifas: dict[str, dict[tuple[int, int], float]] = {tipo: {} for tipo in TIPOS_TARIFA}
    with _conectar() as conn:
        for row in conn.execute(
            """
            SELECT tarifa, anio, mes, valor
            FROM catalog_tarifas_hist
            WHERE esquema_id = ?
            """,
            (esquema,),
        ).fetchall():
            tipo = str(row["tarifa"])
            tarifas.setdefault(tipo, {})
            tarifas[tipo][(int(row["anio"]), int(row["mes"]))] = float(row["valor"] or 0)
    return tarifas


def ruta_bd_tarifas() -> Path:
    return RUTA_BD_PERFILES
