#!/usr/bin/env python3
"""
Migra bess_perfiles.db: medidor_id legacy → Nombre del catálogo (Medidores.csv).

Mapeo:
  ION           → ION_Testigo_IUSA1
  BESS          → BESS_NORTE
  BANCO         → Banco_1
  ION_IUSA2     → ION_TESTIGO_IUSA2
  BESS_IUSA2    → BESS_SUR
  GRANJA_IUSA2  → Generacion_IUSA_2

Uso:
  python scripts/migrar_bd_perfiles.py              # migra in-place con respaldo
  python scripts/migrar_bd_perfiles.py --dry-run    # solo muestra conteos
  python scripts/migrar_bd_perfiles.py --bd ruta.db
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import RUTA_BD_PERFILES
from bess.data.ingest.ion import db
from bess.data.ingest.medidor_ids import LEGACY_A_NOMBRE, medidor_id_canonico


def _contar_por_medidor(conn: sqlite3.Connection) -> dict[str, int]:
    filas = conn.execute(
        "SELECT medidor_id, COUNT(*) AS n FROM perfil_carga GROUP BY medidor_id ORDER BY medidor_id"
    ).fetchall()
    return {row[0]: int(row[1]) for row in filas}


def _imprimir_conteos(conn: sqlite3.Connection, titulo: str) -> None:
    print(f"\n{titulo}")
    print("-" * 50)
    conteos = _contar_por_medidor(conn)
    if not conteos:
        print("  (sin registros en perfil_carga)")
        return
    for medidor_id, n in conteos.items():
        canon = medidor_id_canonico(medidor_id)
        marca = " -> " + canon if canon != medidor_id else ""
        print(f"  {medidor_id:<22} {n:>8}{marca}")


def _hay_legacy(conn: sqlite3.Connection) -> bool:
    placeholders = ",".join("?" * len(LEGACY_A_NOMBRE))
    row = conn.execute(
        f"SELECT COUNT(*) FROM perfil_carga WHERE medidor_id IN ({placeholders})",
        tuple(LEGACY_A_NOMBRE.keys()),
    ).fetchone()
    return bool(row and row[0])


def migrar_bd(ruta: Path, *, dry_run: bool = False) -> int:
    if not ruta.is_file():
        print(f"No existe la base de datos: {ruta}")
        return 1

    with sqlite3.connect(ruta) as conn:
        conn.row_factory = sqlite3.Row
        _imprimir_conteos(conn, f"Antes ({ruta.name})")

        if not _hay_legacy(conn):
            print("\nNo hay medidor_id legacy que migrar. Actualizando catálogo de medidores…")
            if not dry_run:
                db.init_db(ruta)
            print("Listo (sin cambios en perfil_carga).")
            return 0

        if dry_run:
            print("\n[dry-run] Se migrarían los IDs legacy listados arriba.")
            return 0

    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    respaldo = ruta.with_suffix(f".pre_migracion_{marca}.db")
    shutil.copy2(ruta, respaldo)
    print(f"\nRespaldo: {respaldo}")

    with db.conectar_bd(ruta) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        for legacy, nuevo in LEGACY_A_NOMBRE.items():
            conn.execute(
                """
                DELETE FROM perfil_carga
                WHERE medidor_id = ? AND fecha IN (
                    SELECT fecha FROM perfil_carga WHERE medidor_id = ?
                )
                """,
                (nuevo, legacy),
            )
            cur = conn.execute(
                "UPDATE perfil_carga SET medidor_id = ? WHERE medidor_id = ?",
                (nuevo, legacy),
            )
            if cur.rowcount:
                print(f"  perfil_carga: {legacy} -> {nuevo} ({cur.rowcount} filas)")

            row_nuevo = conn.execute(
                "SELECT ultima_fecha, ultima_sync_ok FROM sync_state WHERE medidor_id = ?",
                (nuevo,),
            ).fetchone()
            row_legacy = conn.execute(
                "SELECT ultima_fecha, ultima_sync_ok FROM sync_state WHERE medidor_id = ?",
                (legacy,),
            ).fetchone()
            if row_legacy and row_nuevo:
                if row_legacy[0] and (
                    not row_nuevo[0] or str(row_legacy[0]) > str(row_nuevo[0])
                ):
                    conn.execute(
                        """
                        UPDATE sync_state
                        SET ultima_fecha = ?, ultima_sync_ok = ?
                        WHERE medidor_id = ?
                        """,
                        (row_legacy[0], row_legacy[1], nuevo),
                    )
                conn.execute("DELETE FROM sync_state WHERE medidor_id = ?", (legacy,))
            elif row_legacy:
                conn.execute(
                    "UPDATE sync_state SET medidor_id = ? WHERE medidor_id = ?",
                    (nuevo, legacy),
                )
                print(f"  sync_state: {legacy} -> {nuevo}")

            cur = conn.execute(
                "UPDATE sync_log SET medidor_id = ? WHERE medidor_id = ?",
                (nuevo, legacy),
            )
            if cur.rowcount:
                print(f"  sync_log: {legacy} -> {nuevo} ({cur.rowcount} filas)")

        ids_legacy = tuple(LEGACY_A_NOMBRE.keys())
        placeholders = ",".join("?" * len(ids_legacy))
        conn.execute(
            f"DELETE FROM medidores WHERE id IN ({placeholders})",
            ids_legacy,
        )
        conn.execute("COMMIT")
        conn.execute("PRAGMA foreign_keys = ON")

    db.init_db(ruta)

    with sqlite3.connect(ruta) as conn:
        conn.row_factory = sqlite3.Row
        _imprimir_conteos(conn, f"Después ({ruta.name})")

    print("\nMigración completada.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrar medidor_id legacy en bess_perfiles.db")
    parser.add_argument("--bd", type=Path, default=RUTA_BD_PERFILES)
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar conteos, sin escribir")
    args = parser.parse_args(argv)
    return migrar_bd(args.bd, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
