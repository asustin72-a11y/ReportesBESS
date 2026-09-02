"""Almacén SQLite de reportes derivados (ArchivosReporte → BD).

Fuente de verdad de UI/PDF (Fase 7). Cada archivo de reporte se modela como
una *serie* (`combinado:…`, `energia_dia:…`, …) con filas JSON que
preservan los nombres de columna del CSV.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd

from bess.config.paths import DIRECTORIO_REPORTES, RUTA_BD_PERFILES

SCHEMA_REPORTES_SQL = """
CREATE TABLE IF NOT EXISTS reporte_serie_meta (
    serie_id       TEXT PRIMARY KEY,
    tipo           TEXT NOT NULL,
    medidor_id     TEXT,
    subestacion_id TEXT,
    columnas_json  TEXT NOT NULL,
    clave_col      TEXT NOT NULL,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reporte_serie_fila (
    serie_id   TEXT NOT NULL REFERENCES reporte_serie_meta(serie_id) ON DELETE CASCADE,
    clave      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    PRIMARY KEY (serie_id, clave)
);

CREATE INDEX IF NOT EXISTS idx_reporte_fila_serie
    ON reporte_serie_fila (serie_id);
"""

_TIPOS_CLAVE = {
    "combinado": "FECHA_HORA",
    "energia_dia": "FECHA",
    "acumulados": "FECHA",
    "bess_dia": "FECHA",
    "generacion_dia": "FECHA",
}


def _conectar(ruta: Path | None = None) -> sqlite3.Connection:
    path = ruta or RUTA_BD_PERFILES
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_reportes_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_REPORTES_SQL)


def ensure_reportes_listo(ruta: Path | None = None) -> None:
    with _conectar(ruta) as conn:
        init_reportes_schema(conn)
        conn.commit()


def escribir_csv_habilitado() -> bool:
    return os.environ.get("BESS_REPORTES_ESCRIBIR_CSV", "1").strip() != "0"


def fallback_csv_habilitado() -> bool:
    """Por defecto sin fallback (Fase 7.3). `BESS_REPORTES_FALLBACK_CSV=1` lo reactiva."""
    if os.environ.get("BESS_REPORTES_SOLO_BD", "").strip() == "1":
        return False
    return os.environ.get("BESS_REPORTES_FALLBACK_CSV", "0").strip() == "1"


def tipo_y_stem_desde_nombre(nombre: str) -> tuple[str, str] | None:
    """Infiera tipo de reporte y stem a partir del nombre de archivo CSV."""
    n = Path(nombre).name
    if not n.lower().endswith(".csv"):
        return None
    if n.startswith("COMBINADO_POR_MINUTO_"):
        return "combinado", n[len("COMBINADO_POR_MINUTO_") : -4]
    if n.startswith("ENERGIA_BESS_") and n.endswith("_POR_DIA.csv"):
        return "bess_dia", n[len("ENERGIA_BESS_") : -len("_POR_DIA.csv")]
    if n.startswith("ENERGIA_Generacion_") and n.endswith("_POR_DIA.csv"):
        return "generacion_dia", n[len("ENERGIA_Generacion_") : -len("_POR_DIA.csv")]
    if n.startswith("ENERGIA_") and n.endswith("_POR_DIA.csv"):
        return "energia_dia", n[len("ENERGIA_") : -len("_POR_DIA.csv")]
    if n.startswith("ACUMULADOS_"):
        return "acumulados", n[len("ACUMULADOS_") : -4]
    return None


def serie_id_desde_nombre(nombre: str) -> str | None:
    tipado = tipo_y_stem_desde_nombre(nombre)
    if not tipado:
        return None
    tipo, stem = tipado
    return f"{tipo}:{stem}"


def serie_id_desde_ruta(ruta: str | Path) -> str | None:
    return serie_id_desde_nombre(Path(ruta).name)


def clave_col_para_tipo(tipo: str) -> str:
    return _TIPOS_CLAVE.get(tipo, "FECHA")


def serie_existe(serie_id: str, ruta_bd: Path | None = None) -> bool:
    ensure_reportes_listo(ruta_bd)
    with _conectar(ruta_bd) as conn:
        row = conn.execute(
            "SELECT 1 FROM reporte_serie_meta WHERE serie_id = ?",
            (serie_id,),
        ).fetchone()
        return row is not None


def serie_tiene_filas(serie_id: str, ruta_bd: Path | None = None) -> bool:
    ensure_reportes_listo(ruta_bd)
    with _conectar(ruta_bd) as conn:
        row = conn.execute(
            "SELECT 1 FROM reporte_serie_fila WHERE serie_id = ? LIMIT 1",
            (serie_id,),
        ).fetchone()
        return row is not None


def _payload_cell(valor) -> object:
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(valor, "item"):
        try:
            return valor.item()
        except (ValueError, AttributeError):
            pass
    return valor


def reemplazar_serie(
    serie_id: str,
    df: pd.DataFrame,
    *,
    tipo: str,
    clave_col: str,
    medidor_id: str | None = None,
    subestacion_id: str | None = None,
    ruta_bd: Path | None = None,
) -> int:
    """Reemplaza por completo el contenido de una serie con el DataFrame dado."""
    if df is None or df.empty:
        ensure_reportes_listo(ruta_bd)
        with _conectar(ruta_bd) as conn:
            conn.execute("DELETE FROM reporte_serie_fila WHERE serie_id = ?", (serie_id,))
            conn.execute(
                """
                INSERT INTO reporte_serie_meta
                    (serie_id, tipo, medidor_id, subestacion_id, columnas_json, clave_col, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(serie_id) DO UPDATE SET
                    tipo = excluded.tipo,
                    medidor_id = excluded.medidor_id,
                    subestacion_id = excluded.subestacion_id,
                    columnas_json = excluded.columnas_json,
                    clave_col = excluded.clave_col,
                    updated_at = datetime('now')
                """,
                (
                    serie_id,
                    tipo,
                    medidor_id,
                    subestacion_id,
                    json.dumps(list(df.columns) if df is not None else [], ensure_ascii=False),
                    clave_col,
                ),
            )
            conn.commit()
        return 0

    if clave_col not in df.columns:
        raise ValueError(f"Falta columna clave {clave_col!r} en serie {serie_id}")

    columnas = [str(c) for c in df.columns]
    filas: list[tuple[str, str, str]] = []
    for _, row in df.iterrows():
        clave = str(row[clave_col]).strip()
        if not clave or clave.lower() == "nan":
            continue
        payload = {col: _payload_cell(row[col]) for col in columnas}
        filas.append((serie_id, clave, json.dumps(payload, ensure_ascii=False)))

    ensure_reportes_listo(ruta_bd)
    with _conectar(ruta_bd) as conn:
        conn.execute(
            """
            INSERT INTO reporte_serie_meta
                (serie_id, tipo, medidor_id, subestacion_id, columnas_json, clave_col, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(serie_id) DO UPDATE SET
                tipo = excluded.tipo,
                medidor_id = excluded.medidor_id,
                subestacion_id = excluded.subestacion_id,
                columnas_json = excluded.columnas_json,
                clave_col = excluded.clave_col,
                updated_at = datetime('now')
            """,
            (
                serie_id,
                tipo,
                medidor_id,
                subestacion_id,
                json.dumps(columnas, ensure_ascii=False),
                clave_col,
            ),
        )
        conn.execute("DELETE FROM reporte_serie_fila WHERE serie_id = ?", (serie_id,))
        conn.executemany(
            """
            INSERT INTO reporte_serie_fila (serie_id, clave, payload)
            VALUES (?, ?, ?)
            """,
            filas,
        )
        conn.commit()
    return len(filas)


def leer_dataframe(serie_id: str, ruta_bd: Path | None = None) -> pd.DataFrame | None:
    """Devuelve DataFrame de la serie o None si no existe / sin filas."""
    ensure_reportes_listo(ruta_bd)
    with _conectar(ruta_bd) as conn:
        meta = conn.execute(
            "SELECT columnas_json, clave_col FROM reporte_serie_meta WHERE serie_id = ?",
            (serie_id,),
        ).fetchone()
        if meta is None:
            return None
        rows = conn.execute(
            """
            SELECT clave, payload FROM reporte_serie_fila
            WHERE serie_id = ?
            ORDER BY clave
            """,
            (serie_id,),
        ).fetchall()
    if not rows:
        columnas = json.loads(meta["columnas_json"] or "[]")
        return pd.DataFrame(columns=columnas)

    columnas = json.loads(meta["columnas_json"] or "[]")
    registros = []
    for row in rows:
        payload = json.loads(row["payload"])
        registros.append(payload)
    df = pd.DataFrame.from_records(registros)
    # Orden de columnas del CSV original
    orden = [c for c in columnas if c in df.columns]
    extras = [c for c in df.columns if c not in orden]
    return df[orden + extras] if orden or extras else df


def sincronizar_desde_csv(
    ruta: str | Path,
    *,
    medidor_id: str | None = None,
    subestacion_id: str | None = None,
    ruta_bd: Path | None = None,
) -> int:
    """Lee un CSV de ArchivosReporte y reemplaza la serie correspondiente en BD."""
    path = Path(ruta)
    tipado = tipo_y_stem_desde_nombre(path.name)
    if not tipado:
        raise ValueError(f"Nombre de reporte no reconocido: {path.name}")
    tipo, _stem = tipado
    serie_id = f"{tipo}:{_stem}"
    clave_col = clave_col_para_tipo(tipo)
    if not path.is_file():
        reemplazar_serie(
            serie_id,
            pd.DataFrame(),
            tipo=tipo,
            clave_col=clave_col,
            medidor_id=medidor_id,
            subestacion_id=subestacion_id,
            ruta_bd=ruta_bd,
        )
        return 0
    df = pd.read_csv(path)
    if subestacion_id is None:
        # data/ArchivosReporte/{Sub}/archivo.csv
        try:
            subestacion_id = path.parent.name
        except Exception:
            subestacion_id = None
    return reemplazar_serie(
        serie_id,
        df,
        tipo=tipo,
        clave_col=clave_col,
        medidor_id=medidor_id,
        subestacion_id=subestacion_id,
        ruta_bd=ruta_bd,
    )


def persistir_reporte_escrito(
    ruta: str | Path,
    df: pd.DataFrame | None = None,
    *,
    medidor_id: str | None = None,
    subestacion_id: str | None = None,
    ruta_bd: Path | None = None,
) -> int:
    """Tras escribir (o en lugar de) el CSV: actualiza BD.

    Si ``df`` es None, relee el CSV de ``ruta``.
    """
    path = Path(ruta)
    tipado = tipo_y_stem_desde_nombre(path.name)
    if not tipado:
        return 0
    tipo, stem = tipado
    serie_id = f"{tipo}:{stem}"
    clave_col = clave_col_para_tipo(tipo)
    if df is None:
        return sincronizar_desde_csv(
            path,
            medidor_id=medidor_id,
            subestacion_id=subestacion_id,
            ruta_bd=ruta_bd,
        )
    if subestacion_id is None and path.parent.name:
        subestacion_id = path.parent.name
    return reemplazar_serie(
        serie_id,
        df,
        tipo=tipo,
        clave_col=clave_col,
        medidor_id=medidor_id,
        subestacion_id=subestacion_id,
        ruta_bd=ruta_bd,
    )


def guardar_dataframe_reporte(
    ruta: str | Path,
    df: pd.DataFrame,
    *,
    medidor_id: str | None = None,
    subestacion_id: str | None = None,
    ruta_bd: Path | None = None,
) -> int:
    """Persiste el DataFrame en BD y, si está habilitado, escribe el CSV.

    Orden: BD primero (fallo = excepción); CSV opcional vía
    ``BESS_REPORTES_ESCRIBIR_CSV`` (default 1).
    """
    from bess.core.atomic_io import ruta_temporal_atomica

    path = Path(ruta)
    n = persistir_reporte_escrito(
        path,
        df,
        medidor_id=medidor_id,
        subestacion_id=subestacion_id,
        ruta_bd=ruta_bd,
    )
    if escribir_csv_habilitado():
        path.parent.mkdir(parents=True, exist_ok=True)
        with ruta_temporal_atomica(path) as ruta_temp:
            df.to_csv(ruta_temp, index=False)
    return n


def reporte_existe(ruta: str | Path, *, ruta_bd: Path | None = None) -> bool:
    """True si hay filas en BD para la serie o existe el CSV en disco."""
    path = Path(ruta)
    serie_id = serie_id_desde_ruta(path)
    if serie_id and serie_tiene_filas(serie_id, ruta_bd=ruta_bd):
        return True
    return path.is_file()


def columnas_reporte(
    ruta: str | Path,
    *,
    ruta_bd: Path | None = None,
) -> list[str] | None:
    """Nombres de columna del reporte (cabecera CSV si existe; si no, meta BD)."""
    path = Path(ruta)
    # Preferir CSV cuando existe: el pipeline incremental preserva bytes
    # de filas cerradas leyendo el archivo; la meta BD puede quedar
    # desfasada respecto a un CSV recién escrito en otro directorio de prueba.
    if path.is_file():
        try:
            return list(pd.read_csv(path, nrows=0).columns)
        except (ValueError, OSError):
            pass
    serie_id = serie_id_desde_ruta(path)
    if serie_id:
        ensure_reportes_listo(ruta_bd)
        with _conectar(ruta_bd) as conn:
            meta = conn.execute(
                "SELECT columnas_json FROM reporte_serie_meta WHERE serie_id = ?",
                (serie_id,),
            ).fetchone()
        if meta is not None:
            return list(json.loads(meta["columnas_json"] or "[]"))
    return None


def clave_cache_reporte(ruta: str | Path, *, ruta_bd: Path | None = None) -> str:
    """Clave de invalidación de caché (mtime CSV o updated_at + filas en BD)."""
    path = Path(ruta)
    serie_id = serie_id_desde_ruta(path)
    partes: list[str] = []
    if path.is_file():
        st = path.stat()
        partes.append(f"f:{st.st_mtime}:{st.st_size}")
    if serie_id:
        ensure_reportes_listo(ruta_bd)
        with _conectar(ruta_bd) as conn:
            meta = conn.execute(
                "SELECT updated_at FROM reporte_serie_meta WHERE serie_id = ?",
                (serie_id,),
            ).fetchone()
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM reporte_serie_fila WHERE serie_id = ?",
                (serie_id,),
            ).fetchone()
        if meta is not None:
            partes.append(f"db:{meta['updated_at']}:{n['n'] if n else 0}")
    return "|".join(partes) if partes else "empty"


def cargar_reporte(
    ruta: str | Path,
    *,
    ruta_bd: Path | None = None,
) -> pd.DataFrame:
    """Carga un reporte: BD si hay filas; si no, CSV según política de fallback.

    - Con filas en BD → siempre BD.
    - Sin filas: CSV si ``BESS_REPORTES_FALLBACK_CSV=1`` **o** la serie aún
      no tiene meta (instalación sin migrar).
    """
    path = Path(ruta)
    serie_id = serie_id_desde_ruta(path)
    if serie_id and serie_tiene_filas(serie_id, ruta_bd=ruta_bd):
        df = leer_dataframe(serie_id, ruta_bd=ruta_bd)
        if df is not None:
            return df
    if not path.is_file():
        return pd.DataFrame()
    if not serie_id:
        return pd.read_csv(path)
    if fallback_csv_habilitado() or not serie_existe(serie_id, ruta_bd=ruta_bd):
        return pd.read_csv(path)
    return pd.DataFrame()


def importar_directorio_reportes(
    base: Path | None = None,
    *,
    ruta_bd: Path | None = None,
) -> dict[str, int]:
    """Importa todos los CSV reconocidos bajo ArchivosReporte/."""
    root = base or DIRECTORIO_REPORTES
    contadores: dict[str, int] = {}
    if not root.is_dir():
        return contadores
    for csv_path in sorted(root.rglob("*.csv")):
        if tipo_y_stem_desde_nombre(csv_path.name) is None:
            continue
        try:
            n = sincronizar_desde_csv(csv_path, ruta_bd=ruta_bd)
            contadores[str(csv_path.relative_to(root))] = n
        except Exception as exc:
            contadores[str(csv_path)] = -1
            print(f"WARN report_store import {csv_path}: {exc}")
    return contadores
