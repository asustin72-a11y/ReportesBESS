"""Generación de archivos limpios desde perfiles."""

from __future__ import annotations

import csv
import os

import pandas as pd

from bess.config.paths import DIRECTORIO_PROCESADOS
from bess.core.dates import normalizar_fecha
from bess.core.kvarh import columnas_kvarh as _columnas_kvarh

from bess.core.console import log
print = log

# El origen (ArchivosProcesados) puede traer, en corridas sucesivas,
# valores actualizados para fechas ya escritas aqui en una corrida
# anterior -- la actualizacion se origina en verify.py, que ahora
# reverifica una ventana de los ultimos dias en cada corrida en vez de
# solo anexar filas estrictamente nuevas (ver bess/data/pipeline/verify.py
# y, un nivel mas atras, bess/data/ingest/ion/export_csv.py). Si aqui solo
# se anexara lo estrictamente posterior al cursor, esas actualizaciones
# nunca se propagarian. MARGEN_REEXPORTAR_DIAS es el mismo margen que usan
# esos dos modulos, para que la ventana recalculada siempre alcance a
# cubrir cualquier actualizacion que ellos hayan hecho.
MARGEN_REEXPORTAR_DIAS = 1


def leer_previas_a_ventana(ruta_salida, inicio_ventana) -> "list[list[str]] | None":
    """Filas crudas (via csv.reader, SIN reparsear los valores numericos)
    ya escritas en `ruta_salida` (por generar_archivo_limpio) con Fecha
    anterior a `inicio_ventana` -- se preservan tal cual estaban al
    recalcular una ventana incremental.

    Deliberadamente NO se devuelve un DataFrame: reparsear una columna
    numerica ya escrita (p.ej. "193.33090209960932") y volver a
    serializarla via pandas puede producir una representacion de texto
    ligeramente distinta para el mismo float64 (p.ej.
    "193.3309020996093") -- un cambio de bytes sin sentido en datos que ya
    estaban cerrados. Igual que export_csv.py, se preservan las filas
    crudas y solo se reparsea la ventana que realmente se recalcula.

    Devuelve None si el archivo no existe o no tiene una columna Fecha
    legible en la primera posicion; quien llama debe caer al modo
    completo en ese caso.
    """
    if not os.path.exists(ruta_salida):
        return None
    try:
        with open(ruta_salida, 'r', newline='', encoding='utf-8-sig') as f:
            lector = csv.reader(f)
            encabezado = next(lector, None)
            if not encabezado or encabezado[0] != 'Fecha':
                return None
            filas = [fila for fila in lector if fila]
    except OSError:
        return None
    if not filas:
        return []
    # dayfirst=True: normalizar_fecha() escribe DD/MM/YYYY, ambiguo para
    # pandas sin esta bandera cuando el dia es <= 12 (p.ej. 01/02/2026).
    fechas = pd.to_datetime([fila[0] for fila in filas], errors='coerce', dayfirst=True)
    return [
        fila for fila, fecha in zip(filas, fechas)
        if pd.notna(fecha) and fecha < inicio_ventana
    ]


def escribir_ventana_archivo_limpio(filas_previas, df_ventana, ruta_salida):
    """Escribe `ruta_salida` completo: `filas_previas` (crudas, preservadas
    tal cual via leer_previas_a_ventana) + `df_ventana` (la ventana
    recalculada, formateada igual que generar_archivo_limpio) -- reemplaza
    lo que hubiera en el archivo para las fechas de la ventana, sin tocar
    el formato de lo anterior.

    Quien llama debe garantizar que `df_ventana` tiene las mismas columnas
    que el archivo existente (mismo chequeo que ya hace generar/anexar
    contra columnas_archivo_limpio) -- aqui no se revalida.
    """
    columnas = ['Fecha', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df_ventana)
    df_limpio = df_ventana[columnas].copy()
    df_limpio['Fecha'] = df_limpio['Fecha'].apply(normalizar_fecha)
    # Sin newline='' aqui (a diferencia de la lectura): con newline=None
    # (el default), Python traduce cada '\n' escrito al separador de
    # linea del sistema (os.linesep) -- exactamente lo mismo que hace
    # pandas.to_csv() internamente (usado en generar_archivo_limpio y
    # anexar_archivo_limpio, y el que escribio originalmente el archivo
    # existente). Con newline='' el '\n' se escribiria literal sin
    # traducir, y en Windows (donde corre este pipeline en produccion,
    # os.linesep='\r\n') eso desalinearia el fin de linea de la ventana
    # reescrita contra el resto del archivo.
    with open(ruta_salida, 'w', encoding='utf-8-sig') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(columnas)
        for fila in filas_previas:
            writer.writerow(fila)
        for row in df_limpio.itertuples(index=False):
            writer.writerow(row)
    print(
        f"✅ Ventana recalculada guardada: {ruta_salida} "
        f"({len(filas_previas)} preservada(s) + {len(df_limpio)} en ventana)"
    )
    return df_limpio


def generar_archivo_limpio(df, ruta_salida):
    """Genera un archivo CSV limpio (conserva kVArh por cuadrante si existen)."""
    columnas = ['Fecha', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df)
    df_limpio = df[columnas].copy()
    df_limpio['Fecha'] = df_limpio['Fecha'].apply(normalizar_fecha)
    df_limpio.to_csv(ruta_salida, index=False, encoding='utf-8-sig')
    print(f"✅ Archivo generado: {ruta_salida} ({len(df_limpio)} registros)")
    return df_limpio


def anexar_archivo_limpio(df, ruta_salida):
    """Agrega filas nuevas al final de un CSV ya escrito por generar_archivo_limpio,
    sin reescribir lo que ya había (mismas columnas del archivo existente).

    Pensado para pasos incrementales (cursor sobre la última Fecha ya
    escrita): quien llama ya filtró `df` a solo las filas nuevas.
    """
    columnas = ['Fecha', 'KWH_REC', 'KWH_ENT'] + _columnas_kvarh(df)
    df_limpio = df[columnas].copy()
    df_limpio['Fecha'] = df_limpio['Fecha'].apply(normalizar_fecha)
    df_limpio.to_csv(ruta_salida, index=False, header=False, mode='a', encoding='utf-8-sig')
    print(f"✅ {len(df_limpio)} registro(s) nuevo(s) anexado(s) a: {ruta_salida}")
    return df_limpio


def columnas_archivo_limpio(ruta_salida) -> list[str] | None:
    """Encabezado de un CSV ya generado, o None si no existe o no se puede leer."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        return list(pd.read_csv(ruta_salida, nrows=0, encoding='utf-8-sig').columns)
    except (ValueError, OSError):
        return None


def cursor_archivo_limpio(ruta_salida) -> "pd.Timestamp | None":
    """Última Fecha ya escrita en un CSV generado por generar_archivo_limpio,
    o None si no existe/está vacío/no tiene una columna Fecha legible."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        fechas = pd.read_csv(
            ruta_salida, usecols=['Fecha'], encoding='utf-8-sig'
        )['Fecha']
    except (ValueError, KeyError, OSError):
        return None
    # dayfirst=True: normalizar_fecha() escribe DD/MM/YYYY, ambiguo para
    # pandas sin esta bandera cuando el dia es <= 12 (p.ej. 01/02/2026).
    fechas = pd.to_datetime(fechas, errors='coerce', dayfirst=True).dropna()
    if fechas.empty:
        return None
    return fechas.max()
