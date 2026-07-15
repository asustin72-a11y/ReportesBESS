"""Utilidades compartidas para recálculo incremental de agregados diarios.

Los reportes por día (ENERGIA_*_POR_DIA.csv, ENERGIA_BESS_*,
ENERGIA_Generacion_*) agrupan minuto a minuto por FECHA (+ PERIODO): cada
día es independiente de los demás -- a diferencia de la demanda rodante de
combined.py, aquí no hay ventana ni acumulado que cruce entre días dentro
de este mismo cálculo -- así que recalcular solo los días afectados por la
última sincronización y conservar los días ya cerrados produce exactamente
el mismo resultado que recalcular todo el histórico.

El único matiz es que el último día ya escrito puede seguir "abierto" (el
cron corre cada 15 min; un día no está completo hasta las 00:00 del día
siguiente): por eso el recálculo siempre incluye el último día ya escrito
en el reporte existente, no solo los días estrictamente nuevos.
"""

from __future__ import annotations

import os

import pandas as pd


def cursor_dia(ruta_salida) -> "pd.Timestamp | None":
    """Última FECHA (día, sin hora) ya escrita en un reporte diario
    existente, o None si no existe/está vacío/no se puede leer."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        fechas = pd.read_csv(ruta_salida, usecols=["FECHA"])["FECHA"]
    except (ValueError, KeyError, OSError):
        return None
    dt = pd.to_datetime(fechas, format="%d/%m/%Y", errors="coerce").dropna()
    if dt.empty:
        return None
    return dt.max()


def columnas_dia(ruta_salida) -> list[str] | None:
    """Encabezado de un reporte diario existente, o None si no existe o no
    se puede leer."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        return list(pd.read_csv(ruta_salida, nrows=0).columns)
    except (ValueError, OSError):
        return None


def combinar_cola_diaria(
    df_nuevo_tail: pd.DataFrame, ruta_salida: str, columnas: list[str]
) -> pd.DataFrame:
    """Combina `df_nuevo_tail` (recalculado desde el cursor en adelante,
    ya con las columnas finales) con los días más antiguos que ya estaban
    en `ruta_salida`, sin haber tenido que recalcular todo el histórico.

    `df_nuevo_tail` reemplaza cualquier día >= su primera FECHA que ya
    existiera en el archivo (el último día escrito se recalcula siempre,
    por si seguía abierto). Devuelve el DataFrame combinado y ordenado,
    listo para escribirse completo -- estos reportes son pequeños (una
    fila por día), así que la escritura sigue siendo completa; lo que se
    evita es recalcular la agregación minuto a minuto de todo el histórico.
    """
    if df_nuevo_tail.empty:
        if os.path.exists(ruta_salida):
            return pd.read_csv(ruta_salida)
        return df_nuevo_tail

    primera_fecha_nueva = pd.to_datetime(
        df_nuevo_tail["FECHA"].iloc[0], format="%d/%m/%Y"
    )

    if os.path.exists(ruta_salida):
        df_previo = pd.read_csv(ruta_salida)
        fechas_previas = pd.to_datetime(
            df_previo["FECHA"], format="%d/%m/%Y", errors="coerce"
        )
        df_previo = df_previo[fechas_previas < primera_fecha_nueva]
        df_final = pd.concat([df_previo, df_nuevo_tail], ignore_index=True)
    else:
        df_final = df_nuevo_tail

    fecha_dt = pd.to_datetime(df_final["FECHA"], format="%d/%m/%Y")
    df_final = df_final.assign(_FECHA_DT=fecha_dt)
    df_final = df_final.sort_values("_FECHA_DT").drop(columns=["_FECHA_DT"])
    return df_final[columnas].reset_index(drop=True)
