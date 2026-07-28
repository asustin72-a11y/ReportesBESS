"""Asegura que los 21 MEGAs existan en el catálogo SQLite compartido."""

from __future__ import annotations

from bess.config.catalog import invalidar_cache_catalogo
from bess.config.paths import RUTA_BD_PERFILES
from bess.data.catalog_db import ensure_catalog_listo
from bess.data.ingest.ion import db

from granja.config import GRUPO_GENERACION
from granja.config.meters import MEGAS


def asegurar_megas_en_catalogo() -> int:
    """
    Inserta/actualiza Mega01–Mega21 en catalog_medidores y en medidores (FK perfil).
    Devuelve cuántos MEGAs quedaron registrados.
    Necesario si la BD ya existía antes de registrar Mega21 en el catálogo.
    """
    ensure_catalog_listo()
    db.init_db(RUTA_BD_PERFILES)
    insertados = 0
    with db.conectar_bd(RUTA_BD_PERFILES) as conn:
        # Subestación IUSA_2 = numero 2 en el catálogo actual
        row_sub = conn.execute(
            "SELECT numero FROM catalog_subestaciones WHERE nombre = 'IUSA_2'"
        ).fetchone()
        sub_num = int(row_sub["numero"]) if row_sub else 2

        for mega in MEGAS:
            conn.execute(
                """
                INSERT INTO catalog_medidores (
                    nombre, numero_serie, subestacion_numero, tipo_medidor,
                    descarga, ip, puerto, grupo_generacion, validado
                ) VALUES (?, ?, ?, 4, 'API', '0', 0, ?, NULL)
                ON CONFLICT(nombre) DO UPDATE SET
                    numero_serie = excluded.numero_serie,
                    subestacion_numero = excluded.subestacion_numero,
                    tipo_medidor = excluded.tipo_medidor,
                    descarga = excluded.descarga,
                    grupo_generacion = excluded.grupo_generacion
                """,
                (mega.nombre, mega.numero_serie, sub_num, GRUPO_GENERACION),
            )
            conn.execute(
                """
                INSERT INTO medidores
                    (id, nombre, tipo, ip, dr_modulo, intervalo_min, activo)
                VALUES (?, ?, 'GENERACION_MEGA', NULL, NULL, 5, 1)
                ON CONFLICT(id) DO UPDATE SET
                    nombre = excluded.nombre,
                    tipo = excluded.tipo,
                    intervalo_min = excluded.intervalo_min,
                    activo = excluded.activo
                """,
                (mega.nombre, f"{mega.nombre} · Subestación IUSA 2"),
            )
            insertados += 1
        conn.commit()
    invalidar_cache_catalogo()
    return insertados
