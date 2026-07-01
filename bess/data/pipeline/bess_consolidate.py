"""Consolida medidores BESS individuales en BESS_{Subestacion}.csv."""

from __future__ import annotations

import os

import pandas as pd

from bess.config import rutas as rutas_mod
from bess.config.catalog import TIPO_BESS, obtener_catalogo
from bess.config.subestaciones import Subestacion
from bess.data.ingest.readers import leer_archivo_perfil
from bess.data.pipeline.clean import generar_archivo_limpio

_COLS_SUMA = ("KWH_REC", "KWH_ENT", "KVARH_Q1", "KVARH_Q2", "KVARH_Q3", "KVARH_Q4")


def _leer_procesado(ruta: str, nombre: str) -> pd.DataFrame | None:
    if not os.path.exists(ruta):
        return None
    return leer_archivo_perfil(ruta, nombre)


def consolidar_bess_subestacion(sub: Subestacion, *, filtrado: bool = False) -> bool:
    """
    Suma perfiles BESS tipo 3 del catálogo → ArchivosProcesados/{sub}/BESS_{sub}.csv.
    Con un solo medidor BESS por subestación equivale a copiar/renombrar.
    """
    cat = obtener_catalogo()
    bess_meds = [m for m in cat.medidores_subestacion(sub.id) if m.tipo_medidor == TIPO_BESS]
    if not bess_meds:
        return False

    marcos: list[pd.DataFrame] = []
    for m in bess_meds:
        ruta = rutas_mod.resolver_ruta_procesado(
            rutas_mod.ruta_procesado_medidor(m.nombre, sub.id, filtrado=filtrado)
        )
        df = _leer_procesado(str(ruta), ruta.name)
        if df is not None and not df.empty:
            marcos.append(df)

    if not marcos:
        ruta_agg = rutas_mod.resolver_ruta_procesado(
            rutas_mod.ruta_bess_subestacion(sub.id, filtrado=filtrado)
        )
        df = _leer_procesado(str(ruta_agg), ruta_agg.name)
        if df is not None and not df.empty:
            marcos.append(df)

    if not marcos:
        return False

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

    base = base.sort_values("Fecha").reset_index(drop=True)
    destino = str(sub.ruta_bess(filtrado=filtrado))
    generar_archivo_limpio(base, destino)
    return True
