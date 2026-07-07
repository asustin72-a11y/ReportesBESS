"""Reportes de generación granja (solo columna de energía · sin otros medidores)."""

from __future__ import annotations

import os

import pandas as pd

from bess.config import rutas as rutas_mod
from bess.cfe.periods import periodo_por_fecha_hora
from bess.config.esquema_tarifa import normalizar_esquema_tarifa
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


def _energia_por_dia_y_periodo(df_min: pd.DataFrame, columna_kwh: str = "KWH_REC") -> pd.DataFrame:
    df_rec = df_min.groupby(["FECHA", "PERIODO"], as_index=False)[columna_kwh].sum()
    df_dia = df_rec.pivot_table(
        index="FECHA",
        columns="PERIODO",
        values=columna_kwh,
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    df_dia = df_dia.rename(columns=_MAPA_PERIODO_DIA)
    for col in _COLUMNAS_DIA_GRANJA[1:]:
        if col not in df_dia.columns:
            df_dia[col] = 0.0
    return df_dia[list(_COLUMNAS_DIA_GRANJA)].sort_values("FECHA").reset_index(drop=True)


def generar_reportes_generacion(
    ruta_filtrado: str,
    subestacion: str,
    prefijo: str,
    *,
    columna_kwh: str = "KWH_REC",
    esquema_tarifa_id: str | None = None,
) -> dict[str, int]:
    """
    Genera a partir del CSV filtrado de generación/cogeneración:
      - COMBINADO_POR_MINUTO_{prefijo}.csv en ArchivosReporte/{sub}/
      - ENERGIA_Generacion_{sub}_POR_DIA.csv
    """
    if not os.path.exists(ruta_filtrado):
        print(f"ERROR: No se encuentra {ruta_filtrado}")
        return {}

    print("\n" + "=" * 60)
    print(f"GENERANDO REPORTES GENERACIÓN ({prefijo} · {subestacion})")
    print("=" * 60)

    esquema = normalizar_esquema_tarifa(esquema_tarifa_id)
    df_min = leer_sin_agrupar(ruta_filtrado)
    df_min = agregar_fecha_operativa(df_min, col_fecha_hora="FECHA_HORA")
    df_min["PERIODO"] = df_min["FECHA_HORA"].apply(
        lambda fh: periodo_por_fecha_hora(fh, esquema)
    )

    if columna_kwh not in df_min.columns:
        print(f"ERROR: falta columna {columna_kwh} en {ruta_filtrado}")
        return {}

    df_min_out = df_min[["FECHA", "FECHA_HORA", columna_kwh]].copy()
    df_min_out = df_min_out.rename(columns={columna_kwh: "KWH_REC"})
    nombre_min = f"COMBINADO_POR_MINUTO_{prefijo}.csv"
    ruta_min = str(rutas_mod.ruta_reporte(subestacion, nombre_min))
    os.makedirs(os.path.dirname(ruta_min), exist_ok=True)
    df_min_out.to_csv(ruta_min, index=False)
    print(f"OK {nombre_min} - {len(df_min_out)} registros")

    df_dia = _energia_por_dia_y_periodo(df_min, columna_kwh)
    nombre_dia = f"ENERGIA_Generacion_{subestacion}_POR_DIA.csv"
    ruta_dia = str(rutas_mod.ruta_reporte(subestacion, nombre_dia))
    df_dia.to_csv(ruta_dia, index=False)
    print(f"OK {nombre_dia} - {len(df_dia)} días")

    return {
        nombre_min: len(df_min_out),
        nombre_dia: len(df_dia),
    }


def generar_reportes_granja(ruta_filtrado: str, subestacion: str, prefijo: str | None = None) -> dict[str, int]:
    """Compatibilidad: granja IUSA 2 (KWH_REC)."""
    prefijo = prefijo or rutas_mod.nombre_generacion_subestacion(subestacion).replace(".csv", "")
    return generar_reportes_generacion(
        ruta_filtrado, subestacion, prefijo, columna_kwh="KWH_REC"
    )
