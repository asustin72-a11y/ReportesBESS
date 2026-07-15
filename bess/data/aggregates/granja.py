"""Reportes de generación granja (solo columna de energía · sin otros medidores)."""

from __future__ import annotations

import os

import pandas as pd

from bess.config import rutas as rutas_mod
from bess.cfe.periods import periodo_por_fecha_hora
from bess.config.esquema_tarifa import normalizar_esquema_tarifa
from bess.core.dates import agregar_fecha_operativa
from bess.core.console import log
from bess.data.aggregates._incremental_dia import (
    columnas_dia,
    combinar_cola_diaria,
    cursor_dia,
)
from bess.data.aggregates.combined import _columnas_combinado, _cursor_combinado
from bess.data.ingest.readers import leer_sin_agrupar

print = log

_COLUMNAS_DIA_GRANJA = ["FECHA", "BASE_REC", "INTERMEDIO_REC", "PUNTA_REC"]
_COLUMNAS_MIN_GRANJA = ["FECHA", "FECHA_HORA", "KWH_REC"]
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
    # Ordenar por fecha real (no lexicográfico): "FECHA" es texto DD/MM/YYYY,
    # y un sort_values("FECHA") de texto intercala meses/años incorrectamente
    # (p.ej. "01/03/2026" < "05/02/2026" como cadenas). Esto ya era un bug
    # preexistente en el orden de salida; ahora además combinar_cola_diaria
    # depende de que la primera fila del tail sea realmente la más antigua.
    orden = pd.to_datetime(df_dia["FECHA"], format="%d/%m/%Y").argsort(kind="stable")
    return df_dia.iloc[orden][_COLUMNAS_DIA_GRANJA].reset_index(drop=True)


def _escribir_combinado_minuto(df_min_out: pd.DataFrame, ruta_min: str) -> int:
    """Escribe COMBINADO_POR_MINUTO_{prefijo}.csv de granja/cogeneración de
    forma incremental: a diferencia de combined.py (Fase 5.1) no hay
    columnas derivadas ni demanda rodante aquí -- es un passthrough de
    FECHA/FECHA_HORA/KWH_REC -- así que un cursor simple sobre la última
    FECHA_HORA ya escrita alcanza (sin filas de contexto). Devuelve la
    cantidad de filas nuevas escritas."""
    cursor = _cursor_combinado(ruta_min)
    if cursor is not None and _columnas_combinado(ruta_min) == _COLUMNAS_MIN_GRANJA:
        fecha_hora_dt = pd.to_datetime(df_min_out["FECHA_HORA"], format="%d/%m/%Y %H:%M")
        nuevas = df_min_out[fecha_hora_dt > cursor]
        if nuevas.empty:
            return 0
        os.makedirs(os.path.dirname(ruta_min), exist_ok=True)
        nuevas.to_csv(ruta_min, index=False, header=False, mode="a")
        return len(nuevas)

    os.makedirs(os.path.dirname(ruta_min), exist_ok=True)
    df_min_out.to_csv(ruta_min, index=False)
    return len(df_min_out)


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

    Ambos son incrementales: el combinado por minuto anexa solo lo nuevo
    (cursor sobre FECHA_HORA); el diario recalcula solo el último día ya
    escrito (por si seguía abierto) más los días nuevos, igual que
    daily.py/bess_daily.py. La primera vez (o si cambia el formato de
    columnas) procesa completo, como antes.
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
    filas_nuevas_min = _escribir_combinado_minuto(df_min_out, ruta_min)
    print(f"OK {nombre_min} - {filas_nuevas_min} registro(s) nuevo(s)")

    nombre_dia = f"ENERGIA_Generacion_{subestacion}_POR_DIA.csv"
    ruta_dia = str(rutas_mod.ruta_reporte(subestacion, nombre_dia))
    cursor = cursor_dia(ruta_dia)
    incremental = cursor is not None and columnas_dia(ruta_dia) == _COLUMNAS_DIA_GRANJA

    df_min_dia = df_min
    if incremental:
        fecha_dt = pd.to_datetime(df_min["FECHA"], format="%d/%m/%Y")
        df_min_dia = df_min[fecha_dt >= cursor]

    if incremental and df_min_dia.empty:
        print(f"  Sin días nuevos para {nombre_dia} (cursor {cursor.date()})")
        df_dia = pd.read_csv(ruta_dia)
    else:
        df_dia = _energia_por_dia_y_periodo(df_min_dia, columna_kwh)
        if incremental:
            df_dia = combinar_cola_diaria(df_dia, ruta_dia, _COLUMNAS_DIA_GRANJA)
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
