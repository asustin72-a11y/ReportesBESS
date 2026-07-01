"""Reportes de generación granja (solo columna de energía · sin otros medidores)."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.paths import DIRECTORIO_REPORTES
from bess.cfe.periods import obtener_periodo_por_fecha_hora
from bess.core.dates import agregar_fecha_operativa
from bess.core.console import log
from bess.data.ingest.readers import leer_sin_agrupar

print = log

_COLUMNAS_DIA_GRANJA = ("FECHA", "BASE_REC", "INTERMEDIO_REC", "PUNTA_REC")
_MAPA_PERIODO_DIA = {
    "Base": "BASE_REC",
    "Intermedio": "INTERMEDIO_REC",
    "Punta": "PUNTA_REC",
}


def _energia_por_dia_y_periodo(df_min: pd.DataFrame) -> pd.DataFrame:
    df_rec = df_min.groupby(["FECHA", "PERIODO"], as_index=False)["KWH_REC"].sum()
    df_dia = df_rec.pivot_table(
        index="FECHA",
        columns="PERIODO",
        values="KWH_REC",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    df_dia = df_dia.rename(columns=_MAPA_PERIODO_DIA)
    for col in _COLUMNAS_DIA_GRANJA[1:]:
        if col not in df_dia.columns:
            df_dia[col] = 0.0
    return df_dia[list(_COLUMNAS_DIA_GRANJA)].sort_values("FECHA").reset_index(drop=True)


def generar_reportes_granja(ruta_filtrado: str, prefijo: str = "GRANJA_IUSA2") -> dict[str, int]:
    """
    Genera a partir del CSV filtrado de granja:
      - COMBINADO_POR_MINUTO_{prefijo}.csv  (5 min · KWH_REC)
      - ENERGIA_{prefijo}_POR_DIA.csv
    """
    if not os.path.exists(ruta_filtrado):
        print(f"ERROR: No se encuentra {ruta_filtrado}")
        return {}

    print("\n" + "=" * 60)
    print(f"GENERANDO REPORTES GRANJA ({prefijo})")
    print("=" * 60)

    df_min = leer_sin_agrupar(ruta_filtrado)
    df_min = agregar_fecha_operativa(df_min, col_fecha_hora="FECHA_HORA")
    df_min["PERIODO"] = df_min["FECHA_HORA"].apply(obtener_periodo_por_fecha_hora)

    df_min_out = df_min[["FECHA", "FECHA_HORA", "KWH_REC"]].copy()
    nombre_min = f"COMBINADO_POR_MINUTO_{prefijo}.csv"
    ruta_min = os.path.join(DIRECTORIO_REPORTES, nombre_min)
    df_min_out.to_csv(ruta_min, index=False)
    print(f"OK {nombre_min} - {len(df_min_out)} registros")

    df_dia = _energia_por_dia_y_periodo(df_min)
    nombre_dia = f"ENERGIA_{prefijo}_POR_DIA.csv"
    ruta_dia = os.path.join(DIRECTORIO_REPORTES, nombre_dia)
    df_dia.to_csv(ruta_dia, index=False)
    print(f"OK {nombre_dia} - {len(df_dia)} días (desde COMBINADO_POR_MINUTO)")

    return {
        nombre_min: len(df_min_out),
        nombre_dia: len(df_dia),
    }
