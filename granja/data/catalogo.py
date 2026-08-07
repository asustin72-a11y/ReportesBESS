"""Asegura que los 21 MEGAs existan en el catálogo SQLite compartido."""

from __future__ import annotations

from bess.config.catalog import invalidar_cache_catalogo
from bess.config.paths import RUTA_BD_PERFILES
from bess.data.catalog_db import ensure_catalog_listo
from bess.data.ingest.ion import db

from granja.config import GRUPO_GENERACION
from granja.config.meters import MEGAS

_SESSION_FLAG = "_granja_megas_catalogo_ok"


def asegurar_megas_en_catalogo(*, forzar: bool = False) -> int:
    """
    Inserta/actualiza Mega01–Mega21 en catalog_medidores y en medidores (FK perfil).
    Devuelve cuántos MEGAs quedaron registrados.

    Por defecto corre una sola vez por sesión Streamlit (barato en re-renders /
    cambios de módulo). Use forzar=True tras migraciones de catálogo.
    """
    import streamlit as st

    if not forzar and st.session_state.get(_SESSION_FLAG):
        return int(st.session_state.get("_granja_megas_catalogo_n") or len(MEGAS))

    ensure_catalog_listo()
    db.init_db(RUTA_BD_PERFILES)
    insertados = 0
    hubo_cambio = False
    with db.conectar_bd(RUTA_BD_PERFILES) as conn:
        # Subestación IUSA_2 = numero 2 en el catálogo actual
        row_sub = conn.execute(
            "SELECT numero FROM catalog_subestaciones WHERE nombre = 'IUSA_2'"
        ).fetchone()
        sub_num = int(row_sub["numero"]) if row_sub else 2

        for mega in MEGAS:
            prev = conn.execute(
                "SELECT numero_serie FROM catalog_medidores WHERE nombre = ?",
                (mega.nombre,),
            ).fetchone()
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
            if prev is None or str(prev["numero_serie"]) != str(mega.numero_serie):
                hubo_cambio = True
        conn.commit()
    if hubo_cambio:
        invalidar_cache_catalogo()
    st.session_state[_SESSION_FLAG] = True
    st.session_state["_granja_megas_catalogo_n"] = insertados
    return insertados
