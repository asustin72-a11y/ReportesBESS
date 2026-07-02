"""Operaciones de mantenimiento sobre bess_perfiles.db (sin pipeline CSV)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bess.config.paths import RUTA_BD_PERFILES
from bess.data.ingest.ion import db
from bess.data.ingest.ion.export_csv import exportar, exportar_todos
from bess.data.ingest.ion.import_csv import MEDIDORES_IMPORTABLES, importar_csv

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class ResumenMedidor:
    medidor_id: str
    registros: int
    fecha_min: str | None
    fecha_max: str | None
    ultima_sync: str | None
    ultima_sync_ok: str | None


def ruta_bd() -> Path:
    return RUTA_BD_PERFILES


def lista_medidores_catalogo() -> list[str]:
    return [fila[0] for fila in db.MEDIDORES_CATALOGO]


def _fmt_fecha_hora(valor: date | datetime, fin_dia: bool = False) -> str:
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    hora = "23:59:59" if fin_dia else "00:00:00"
    return f"{valor.isoformat()} {hora}"


def resumen_medidores() -> list[ResumenMedidor]:
    if not RUTA_BD_PERFILES.is_file():
        return []
    with db.conectar_bd() as conn:
        filas = conn.execute(
            """
            SELECT
                m.id AS medidor_id,
                COUNT(p.id) AS registros,
                MIN(p.fecha) AS fecha_min,
                MAX(p.fecha) AS fecha_max,
                s.ultima_fecha,
                s.ultima_sync_ok
            FROM medidores m
            LEFT JOIN perfil_carga p ON p.medidor_id = m.id
            LEFT JOIN sync_state s ON s.medidor_id = m.id
            GROUP BY m.id
            ORDER BY m.id
            """
        ).fetchall()
    return [
        ResumenMedidor(
            medidor_id=row["medidor_id"],
            registros=int(row["registros"] or 0),
            fecha_min=row["fecha_min"],
            fecha_max=row["fecha_max"],
            ultima_sync=row["ultima_fecha"],
            ultima_sync_ok=row["ultima_sync_ok"],
        )
        for row in filas
    ]


def ultimos_sync_log(limite: int = 15) -> list[dict]:
    if not RUTA_BD_PERFILES.is_file():
        return []
    with db.conectar_bd() as conn:
        filas = conn.execute(
            """
            SELECT medidor_id, started_at, finished_at, desde, hasta,
                   registros_insertados, registros_actualizados, status, error_message
            FROM sync_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
    return [dict(row) for row in filas]


def preview_borrar_rango(
    medidor_id: str,
    desde: date | datetime,
    hasta: date | datetime | None = None,
) -> dict:
    desde_txt = _fmt_fecha_hora(desde)
    hasta_txt = _fmt_fecha_hora(hasta, fin_dia=True) if hasta else None

    query = """
        SELECT COUNT(*) AS n, MIN(fecha) AS mn, MAX(fecha) AS mx
        FROM perfil_carga
        WHERE medidor_id = ? AND fecha >= ?
    """
    params: list = [medidor_id, desde_txt]
    if hasta_txt:
        query += " AND fecha <= ?"
        params.append(hasta_txt)

    with db.conectar_bd() as conn:
        pendiente = conn.execute(query, params).fetchone()

    return {
        "medidor": medidor_id,
        "desde": desde_txt,
        "hasta": hasta_txt,
        "eliminar": int(pendiente["n"] or 0),
        "rango": (pendiente["mn"], pendiente["mx"]),
    }


def ejecutar_borrar_rango(
    medidor_id: str,
    desde: date | datetime,
    hasta: date | datetime | None = None,
) -> dict:
    preview = preview_borrar_rango(medidor_id, desde, hasta)
    if preview["eliminar"] == 0:
        return {**preview, "ejecutado": False}

    desde_txt = preview["desde"]
    hasta_txt = preview["hasta"]

    delete_sql = "DELETE FROM perfil_carga WHERE medidor_id = ? AND fecha >= ?"
    params: list = [medidor_id, desde_txt]
    if hasta_txt:
        delete_sql += " AND fecha <= ?"
        params.append(hasta_txt)

    with db.conectar_bd() as conn:
        conn.execute(delete_sql, params)
        row = conn.execute(
            "SELECT MAX(fecha) AS mx, COUNT(*) AS n FROM perfil_carga WHERE medidor_id = ?",
            (medidor_id,),
        ).fetchone()
        if row and row["mx"]:
            db.actualizar_sync_state(conn, medidor_id, row["mx"])
        else:
            conn.execute("DELETE FROM sync_state WHERE medidor_id = ?", (medidor_id,))
        conn.commit()
        restantes = int(row["n"] or 0)

    return {**preview, "ejecutado": True, "registros_restantes": restantes}


def importar_desde_bytes(
    contenido: bytes,
    nombre_archivo: str,
    medidor_id: str,
    *,
    solo_faltantes: bool = False,
    sin_filtro_dia: bool = False,
) -> tuple[int, str]:
    suffix = Path(nombre_archivo).suffix or ".csv"
    with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as tmp:
        tmp.write(contenido)
        ruta_tmp = Path(tmp.name)

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            codigo = importar_csv(
                ruta_tmp,
                RUTA_BD_PERFILES,
                medidor_id,
                solo_faltantes=solo_faltantes,
                sin_filtro_dia=sin_filtro_dia,
            )
        return codigo, buf.getvalue()
    finally:
        ruta_tmp.unlink(missing_ok=True)


def exportar_medidor_a_bytes(
    medidor_id: str,
    *,
    desde: date | None = None,
    hasta: date | None = None,
) -> tuple[bool, bytes | None, str]:
    desde_txt = desde.isoformat() if desde else None
    hasta_txt = hasta.isoformat() if hasta else None

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as tmp:
        ruta_tmp = Path(tmp.name)

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            codigo = exportar(
                RUTA_BD_PERFILES,
                medidor_id,
                ruta_tmp,
                desde_txt,
                hasta_txt,
                quiet=True,
            )
        if codigo != 0:
            return False, None, buf.getvalue() or "Sin registros para exportar."
        return True, ruta_tmp.read_bytes(), buf.getvalue()
    finally:
        ruta_tmp.unlink(missing_ok=True)


def exportar_todos_a_fuente(
    *,
    desde: date | None = None,
    hasta: date | None = None,
) -> tuple[int, str]:
    desde_txt = desde.isoformat() if desde else None
    hasta_txt = hasta.isoformat() if hasta else None
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        codigo = exportar_todos(RUTA_BD_PERFILES, desde_txt, hasta_txt, quiet=False)
    return codigo, buf.getvalue()


def inicializar_bd() -> None:
    db.init_db(RUTA_BD_PERFILES)


def vaciar_perfiles_bd() -> int:
    return db.vaciar_perfiles(RUTA_BD_PERFILES)


def migrar_ids_legacy(*, dry_run: bool = True) -> tuple[int, str]:
    spec = importlib.util.spec_from_file_location(
        "migrar_bd_perfiles",
        ROOT / "scripts" / "migrar_bd_perfiles.py",
    )
    if spec is None or spec.loader is None:
        return 1, "No se pudo cargar scripts/migrar_bd_perfiles.py"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        codigo = mod.migrar_bd(RUTA_BD_PERFILES, dry_run=dry_run)
    return codigo, buf.getvalue()


def purgar_desde_fecha(medidor_id: str, corte: str, *, ejecutar: bool) -> dict:
    """Wrapper del script purgar_api_desde (borra desde fecha inclusive hasta el final)."""
    spec = importlib.util.spec_from_file_location(
        "purgar_api_desde",
        ROOT / "scripts" / "purgar_api_desde.py",
    )
    if spec is None or spec.loader is None:
        return {"error": "No se pudo cargar purgar_api_desde.py"}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.purgar(medidor_id, corte, ejecutar=ejecutar)
