"""Consolida medidores BESS individuales en BESS_{Subestacion}.csv."""

from __future__ import annotations

import os

import pandas as pd

from bess.config import rutas as rutas_mod
from bess.config.catalog import TIPO_BESS, obtener_catalogo
from bess.config.subestaciones import Subestacion
from bess.core.kvarh import columnas_kvarh
from bess.data.ingest.readers import leer_archivo_perfil
from bess.data.pipeline.clean import (
    anexar_archivo_limpio,
    columnas_archivo_limpio,
    cursor_archivo_limpio,
    generar_archivo_limpio,
)

_COLS_SUMA = ("KWH_REC", "KWH_ENT", "KVARH_Q1", "KVARH_Q2", "KVARH_Q3", "KVARH_Q4")


def _leer_procesado(ruta: str, nombre: str) -> pd.DataFrame | None:
    if not os.path.exists(ruta):
        return None
    return leer_archivo_perfil(ruta, nombre)


def _sumar_marcos(marcos: list[pd.DataFrame]) -> pd.DataFrame:
    base = marcos[0].copy()
    for extra in marcos[1:]:
        cols = [c for c in _COLS_SUMA if c in base.columns and c in extra.columns]
        merged = base.merge(extra, on="Fecha", how="outer", suffixes=("", "_x"))
        for col in cols:
            col_x = f"{col}_x"
            if col_x in merged.columns:
                merged[col] = merged[col].fillna(0) + merged[col_x].fillna(0)
                merged = merged.drop(columns=[col_x])
        base = merged
    return base.sort_values("Fecha").reset_index(drop=True)


def consolidar_bess_subestacion(sub: Subestacion, *, filtrado: bool = False) -> bool:
    """
    Suma perfiles BESS tipo 3 del catálogo → ArchivosProcesados/{sub}/BESS_{sub}.csv.
    Con un solo medidor BESS por subestación equivale a copiar/renombrar.

    Incremental: si ya existe un BESS_{sub}.csv con cursor legible (última
    Fecha ya escrita) y columnas compatibles, solo se suman y anexan las
    filas nuevas de cada medidor BESS, en vez de releer y reescribir todo
    el histórico en cada corrida. La primera vez (o si el formato de
    columnas no coincide) se recalcula y reescribe completo, igual que
    antes.
    """
    cat = obtener_catalogo()
    bess_meds = [m for m in cat.medidores_subestacion(sub.id) if m.tipo_medidor == TIPO_BESS]
    if not bess_meds:
        return False

    destino = str(sub.ruta_bess(filtrado=filtrado))
    cursor = cursor_archivo_limpio(destino)

    def _leer_marcos(filtro_cursor):
        marcos: list[pd.DataFrame] = []
        for m in bess_meds:
            ruta = rutas_mod.resolver_ruta_procesado(
                rutas_mod.ruta_procesado_medidor(m.nombre, sub.id, filtrado=filtrado)
            )
            df = _leer_procesado(str(ruta), ruta.name)
            if df is not None and not df.empty:
                if filtro_cursor is not None:
                    df = df[df["Fecha"] > filtro_cursor]
                if not df.empty:
                    marcos.append(df)

        if not marcos:
            ruta_agg = rutas_mod.resolver_ruta_procesado(
                rutas_mod.ruta_bess_subestacion(sub.id, filtrado=filtrado)
            )
            df = _leer_procesado(str(ruta_agg), ruta_agg.name)
            if df is not None and not df.empty:
                if filtro_cursor is not None:
                    df = df[df["Fecha"] > filtro_cursor]
                if not df.empty:
                    marcos.append(df)

        return marcos

    if cursor is not None:
        marcos = _leer_marcos(cursor)
        if not marcos:
            # Ya había un consolidado y no hay filas nuevas: no-op exitoso.
            return True
        base = _sumar_marcos(marcos)
        columnas_nuevas = ["Fecha", "KWH_REC", "KWH_ENT"] + columnas_kvarh(base)
        if columnas_archivo_limpio(destino) == columnas_nuevas:
            anexar_archivo_limpio(base, destino)
            return True
        # Formato de columnas distinto al existente: cae al modo completo
        # de abajo, releyendo todo sin el filtro de cursor.

    marcos = _leer_marcos(None)
    if not marcos:
        return False

    base = _sumar_marcos(marcos)
    generar_archivo_limpio(base, destino)
    return True
