#!/usr/bin/env python3
"""Exporta / importa perfiles MEGA (+ sync + tarifas hist DIST) entre SQLite.

Uso típico (evitar sync completa de 21 MEGAs en el servidor):

  # En el PC con la BD ya poblada (Suite local):
  python scripts/transferir_megas_sqlite.py export -o data/megas_transfer.db

  # Copiar al servidor:
  #   scp data/megas_transfer.db bess@SERVIDOR:~/ReportesBESS/data/

  # En el servidor (o docker exec):
  python scripts/transferir_megas_sqlite.py import -i data/megas_transfer.db

Por defecto origen/destino = data/bess_perfiles.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import RUTA_BD_PERFILES

COLS_PERFIL = (
    "medidor_id, fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4, "
    "fuente, ingested_at"
)


def _exportar(origen: Path, salida: Path) -> None:
    if not origen.is_file():
        raise SystemExit(f"No existe origen: {origen}")
    if salida.exists():
        salida.unlink()

    src = sqlite3.connect(origen)
    out = sqlite3.connect(salida)
    t0 = time.time()
    try:
        n = src.execute(
            "SELECT COUNT(*) FROM perfil_carga WHERE medidor_id LIKE 'Mega%'"
        ).fetchone()[0]
        print(f"Exportando {n:,} filas MEGA…")

        out.execute("ATTACH DATABASE ? AS origen", (str(origen),))
        # Esquema mínimo
        out.executescript(
            """
            CREATE TABLE perfil_carga (
                id INTEGER PRIMARY KEY,
                medidor_id TEXT NOT NULL,
                fecha TEXT NOT NULL,
                kwh_rec REAL, kwh_ent REAL,
                kvarh_q1 REAL, kvarh_q2 REAL, kvarh_q3 REAL, kvarh_q4 REAL,
                fuente TEXT, ingested_at TEXT
            );
            CREATE TABLE sync_state (
                medidor_id TEXT PRIMARY KEY,
                ultima_fecha TEXT,
                ultima_sync_ok TEXT
            );
            CREATE TABLE catalog_medidores (
                nombre TEXT PRIMARY KEY,
                numero_serie TEXT,
                subestacion_numero INTEGER,
                tipo_medidor INTEGER,
                descarga TEXT,
                ip TEXT,
                puerto INTEGER,
                grupo_generacion TEXT,
                validado INTEGER
            );
            CREATE TABLE medidores (
                id TEXT PRIMARY KEY,
                nombre TEXT,
                tipo TEXT,
                ip TEXT,
                dr_modulo INTEGER,
                intervalo_min INTEGER,
                activo INTEGER
            );
            CREATE TABLE catalog_tarifas_hist (
                esquema_id TEXT NOT NULL,
                tarifa TEXT NOT NULL,
                anio INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                valor REAL NOT NULL,
                PRIMARY KEY (esquema_id, tarifa, anio, mes)
            );
            """
        )
        out.execute(
            f"""
            INSERT INTO perfil_carga ({COLS_PERFIL})
            SELECT {COLS_PERFIL}
            FROM origen.perfil_carga
            WHERE medidor_id LIKE 'Mega%'
            """
        )
        out.execute(
            """
            INSERT INTO sync_state (medidor_id, ultima_fecha, ultima_sync_ok)
            SELECT medidor_id, ultima_fecha, ultima_sync_ok
            FROM origen.sync_state
            WHERE medidor_id LIKE 'Mega%'
            """
        )
        out.execute(
            """
            INSERT INTO catalog_medidores
            SELECT * FROM origen.catalog_medidores WHERE nombre LIKE 'Mega%'
            """
        )
        out.execute(
            """
            INSERT INTO medidores
            SELECT * FROM origen.medidores
            WHERE id LIKE 'Mega%' OR nombre LIKE 'Mega%'
            """
        )
        # Tarifas históricas DIST (si existen en origen)
        try:
            out.execute(
                """
                INSERT INTO catalog_tarifas_hist
                SELECT * FROM origen.catalog_tarifas_hist WHERE esquema_id = 'DIST'
                """
            )
        except sqlite3.OperationalError as exc:
            print(f"Aviso tarifas hist: {exc}")

        out.commit()
        out.execute("DETACH DATABASE origen")
        print(f"OK export → {salida} ({time.time() - t0:.1f}s)")
    finally:
        src.close()
        out.close()


def _importar(destino: Path, entrada: Path) -> None:
    if not destino.is_file():
        raise SystemExit(f"No existe destino: {destino}")
    if not entrada.is_file():
        raise SystemExit(f"No existe paquete: {entrada}")

    dst = sqlite3.connect(destino)
    t0 = time.time()
    try:
        dst.execute("PRAGMA journal_mode=WAL")
        dst.execute("PRAGMA synchronous=OFF")
        print("Reemplazando MEGAs en destino…")
        dst.execute("DELETE FROM perfil_carga WHERE medidor_id LIKE 'Mega%'")
        dst.execute("DELETE FROM sync_state WHERE medidor_id LIKE 'Mega%'")
        dst.commit()

        dst.execute("ATTACH DATABASE ? AS pack", (str(entrada),))
        dst.execute(
            f"""
            INSERT INTO perfil_carga ({COLS_PERFIL})
            SELECT {COLS_PERFIL} FROM pack.perfil_carga
            """
        )
        dst.execute(
            """
            INSERT OR REPLACE INTO sync_state (medidor_id, ultima_fecha, ultima_sync_ok)
            SELECT medidor_id, ultima_fecha, ultima_sync_ok FROM pack.sync_state
            """
        )
        dst.execute(
            """
            INSERT OR REPLACE INTO catalog_medidores
            SELECT * FROM pack.catalog_medidores
            """
        )
        dst.execute(
            """
            INSERT OR IGNORE INTO medidores
            SELECT * FROM pack.medidores
            """
        )
        n_hist = dst.execute(
            "SELECT COUNT(*) FROM pack.catalog_tarifas_hist WHERE esquema_id='DIST'"
        ).fetchone()[0]
        if n_hist:
            # Asegurar tabla hist en destino
            dst.executescript(
                """
                CREATE TABLE IF NOT EXISTS catalog_tarifas_hist (
                    esquema_id  TEXT NOT NULL DEFAULT 'DIST',
                    tarifa      TEXT NOT NULL,
                    anio        INTEGER NOT NULL CHECK (anio BETWEEN 2000 AND 2100),
                    mes         INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
                    valor       REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (esquema_id, tarifa, anio, mes)
                );
                """
            )
            dst.execute(
                "DELETE FROM catalog_tarifas_hist WHERE esquema_id = 'DIST'"
            )
            dst.execute(
                """
                INSERT INTO catalog_tarifas_hist
                SELECT * FROM pack.catalog_tarifas_hist WHERE esquema_id = 'DIST'
                """
            )
            print(f"Tarifas hist DIST: {n_hist} filas")

        n = dst.execute(
            "SELECT COUNT(*) FROM perfil_carga WHERE medidor_id LIKE 'Mega%'"
        ).fetchone()[0]
        dst.commit()
        dst.execute("DETACH DATABASE pack")
        print(f"OK import → {n:,} filas MEGA ({time.time() - t0:.1f}s)")
    finally:
        dst.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Transferir MEGAs entre SQLite")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export", help="Crear paquete megas_transfer.db")
    pe.add_argument("-f", "--from", dest="origen", type=Path, default=RUTA_BD_PERFILES)
    pe.add_argument("-o", "--out", type=Path, default=ROOT / "data" / "megas_transfer.db")

    pi = sub.add_parser("import", help="Fusionar paquete en BD destino")
    pi.add_argument("-i", "--in", dest="entrada", type=Path, required=True)
    pi.add_argument("-t", "--to", dest="destino", type=Path, default=RUTA_BD_PERFILES)

    args = p.parse_args()
    if args.cmd == "export":
        _exportar(args.origen, args.out)
    else:
        _importar(args.destino, args.entrada)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
