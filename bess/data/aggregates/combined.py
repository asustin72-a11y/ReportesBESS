"""Combinado por minuto de medidores."""

from __future__ import annotations

import os

from datetime import datetime

import pandas as pd

from bess.config.subestaciones import medidor_consumo_por_prefijo
from bess.cfe.periods import periodo_por_fecha_hora
from bess.config.esquema_tarifa import esquema_tarifa_prefijo, normalizar_esquema_tarifa
from bess.core.consumo import kwh_neto_consumo, usa_consumo_neto
from bess.core.dates import agregar_fecha_operativa
from bess.core.demand import demanda_rodante_15min_por_mes
from bess.core.kvarh import columnas_kvarh as _columnas_kvarh
from bess.data.ingest.readers import leer_sin_agrupar

from bess.core.console import log
print = log

# Ventana de la demanda rodante (bess.core.demand.demanda_rodante_15min_por_mes):
# 15 min / 5 min = 3 filas. Para que la primera fila nueva de una corrida
# incremental calcule el mismo rolling que una corrida completa, hacen falta
# las 2 filas previas como contexto (si pertenecen a otro mes operativo, el
# groupby por mes las separa solas y no contaminan el rolling del mes nuevo).
_VENTANA_DEMANDA_FILAS = 15 // 5
_CONTEXTO_FILAS = _VENTANA_DEMANDA_FILAS - 1


def _cursor_combinado(ruta_salida) -> "pd.Timestamp | None":
    """Última FECHA_HORA ya escrita en un COMBINADO_POR_MINUTO_*.csv
    existente, o None si no existe/está vacío/no se puede leer."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        fechas = pd.read_csv(ruta_salida, usecols=["FECHA_HORA"])["FECHA_HORA"]
    except (ValueError, KeyError, OSError):
        return None
    dt = pd.to_datetime(fechas, format="%d/%m/%Y %H:%M", errors="coerce").dropna()
    if dt.empty:
        return None
    return dt.max()


def _columnas_combinado(ruta_salida) -> list[str] | None:
    """Encabezado de un COMBINADO_POR_MINUTO_*.csv existente, o None si no
    existe o no se puede leer."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        return list(pd.read_csv(ruta_salida, nrows=0).columns)
    except (ValueError, OSError):
        return None


def _calcular_derivados(df_lote, prefijo, esquema, col_con, col_sin):
    """Agrega a `df_lote` las columnas derivadas (HORA, PERIODO, kW, kWh
    netos, mejora BESS y demanda rodante). `df_lote` puede ser el histórico
    completo (primera corrida) o una porción con contexto (corrida
    incremental) -- la función no distingue, solo necesita que las filas
    estén en orden cronológico."""
    horas = []
    for _, row in df_lote.iterrows():
        dt = datetime.strptime(row["FECHA_HORA"], "%d/%m/%Y %H:%M")
        hora = dt.hour
        if hora == 0:
            hora = 24
        horas.append(hora)
    df_lote["HORA"] = horas

    periodos = []
    for _, row in df_lote.iterrows():
        periodos.append(periodo_por_fecha_hora(row["FECHA_HORA"], esquema))
    df_lote["PERIODO"] = periodos

    df_lote["BESS_REC_kW"] = df_lote["KWH_REC_BESS"] * 12
    df_lote["BESS_ENT_kW"] = df_lote["KWH_ENT_BESS"] * 12

    if usa_consumo_neto(prefijo) and "KWH_NETO" not in df_lote.columns:
        col_rec = f"KWH_REC_{prefijo}"
        col_ent = f"KWH_ENT_{prefijo}"
        if col_rec in df_lote.columns and col_ent in df_lote.columns:
            df_lote["KWH_NETO"] = (
                pd.to_numeric(df_lote[col_rec], errors="coerce").fillna(0)
                - pd.to_numeric(df_lote[col_ent], errors="coerce").fillna(0)
            ).clip(lower=0)

    kwh_ion = kwh_neto_consumo(df_lote, prefijo)
    df_lote[col_con] = kwh_ion * 12
    df_lote[col_sin] = (
        kwh_ion
        - pd.to_numeric(df_lote["KWH_REC_BESS"], errors="coerce").fillna(0)
        + pd.to_numeric(df_lote["KWH_ENT_BESS"], errors="coerce").fillna(0)
    ) * 12

    df_lote["BESS_NETO_kWh"] = df_lote["KWH_REC_BESS"] - df_lote["KWH_ENT_BESS"]
    df_lote[f"{prefijo}_NETO_kWh"] = kwh_neto_consumo(df_lote, prefijo)
    df_lote[f"Mejora_BESS_{prefijo}_kWh"] = (
        df_lote[f"{prefijo}_NETO_kWh"] - df_lote["BESS_NETO_kWh"]
    )
    df_lote[f"Mejora_BESS_{prefijo}_kW"] = df_lote[f"Mejora_BESS_{prefijo}_kWh"] * 12

    df_lote = agregar_fecha_operativa(df_lote, col_fecha_hora="FECHA_HORA")
    mes_operativo = pd.to_datetime(df_lote["FECHA"], format="%d/%m/%Y").dt.to_period("M")
    for col in (col_con, col_sin):
        col_demanda = f"{col}_DEM_15min"
        df_lote[col_demanda] = demanda_rodante_15min_por_mes(df_lote[col], mes_operativo)

    return df_lote


def generar_combinado_por_minuto(ruta_bess, ruta_medidor, prefijo, esquema_tarifa_id=None):
    """Genera COMBINADO_POR_MINUTO.csv con resolución de 5 minutos.

    Incremental: si el archivo de salida ya existe con cursor legible
    (última FECHA_HORA escrita) y columnas compatibles, solo se calculan y
    anexan las columnas derivadas (HORA, PERIODO, kW, demanda rodante...)
    para las filas nuevas, en vez de recalcular y reescribir todo el
    histórico en cada corrida. Para la demanda rodante (rolling de 3 filas,
    reinicio mensual) se incluyen también las filas de contexto necesarias
    (ver _CONTEXTO_FILAS) antes de la primera fila nueva. La primera vez (o
    si cambia el formato de columnas) procesa completo, como antes.

    El DataFrame devuelto siempre es el resultado del merge BESS×medidor
    completo (para que quien llama pueda verificar `len(...) == 0` igual
    que antes, incluso en una corrida incremental sin filas nuevas); en modo
    incremental no trae las columnas derivadas del histórico ya escrito,
    solo las de la lectura fuente -- ese contrato ya era el único que usa
    `bess.data.orchestrator.procesar_grupo`.
    """
    print("\n" + "=" * 60)
    print(f"GENERANDO COMBINADO_POR_MINUTO_{prefijo}.csv")
    print("=" * 60)

    df_bess = leer_sin_agrupar(ruta_bess)
    df_medidor = leer_sin_agrupar(ruta_medidor, prefijo_consumo=prefijo)

    col_rec = f"KWH_REC_{prefijo}"
    col_ent = f"KWH_ENT_{prefijo}"
    if "KWH_REC" not in df_medidor.columns and col_rec in df_medidor.columns:
        df_medidor = df_medidor.copy()
        df_medidor["KWH_REC"] = df_medidor[col_rec]
    if "KWH_ENT" not in df_medidor.columns and col_ent in df_medidor.columns:
        df_medidor = df_medidor.copy()
        df_medidor["KWH_ENT"] = df_medidor[col_ent]

    if usa_consumo_neto(prefijo):
        print(f"  {prefijo}: energía y demanda con KWH_NETO (max(0, REC-ENT))")

    print(f"  BESS: {len(df_bess)} registros")
    print(f"  {prefijo}: {len(df_medidor)} registros")

    cols_ion = ["FECHA_HORA", "KWH_REC", "KWH_ENT"]
    if usa_consumo_neto(prefijo) and "KWH_NETO" in df_medidor.columns:
        cols_ion.append("KWH_NETO")
    for col in _columnas_kvarh(df_medidor):
        if col not in cols_ion:
            cols_ion.append(col)
    df_ion = df_medidor[cols_ion].rename(
        columns={
            "KWH_REC": f"KWH_REC_{prefijo}",
            "KWH_ENT": f"KWH_ENT_{prefijo}",
        }
    )

    df_combinado = pd.merge(
        df_bess[["FECHA_HORA", "KWH_REC", "KWH_ENT"]].rename(
            columns={"KWH_REC": "KWH_REC_BESS", "KWH_ENT": "KWH_ENT_BESS"}
        ),
        df_ion,
        on="FECHA_HORA",
        how="inner",
    )

    print(f"  Registros combinados: {len(df_combinado)}")

    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        print(f"ERROR: medidor de consumo desconocido: {prefijo}")
        return None
    ruta_salida = str(med.ruta_combinado())
    nombre_archivo = med.ruta_combinado().name

    if len(df_combinado) == 0:
        print(f"⚠️ Sin registros combinados para {prefijo}")
        return df_combinado

    col_con = f"IUSA_CON_BESS_{prefijo}_kW"
    col_sin = f"IUSA_SIN_BESS_{prefijo}_kW"

    columnas_export = [
        "FECHA",
        "FECHA_HORA",
        "PERIODO",
        "KWH_REC_BESS",
        "KWH_ENT_BESS",
        "BESS_REC_kW",
        "BESS_ENT_kW",
        f"KWH_REC_{prefijo}",
        f"KWH_ENT_{prefijo}",
    ]
    if usa_consumo_neto(prefijo) and "KWH_NETO" in df_combinado.columns:
        columnas_export.append("KWH_NETO")
    for col in _columnas_kvarh(df_combinado):
        if col not in columnas_export:
            columnas_export.append(col)
    columnas_export.extend([
        col_con,
        f"{col_con}_DEM_15min",
        f"{col_sin}_DEM_15min",
    ])

    esquema = normalizar_esquema_tarifa(esquema_tarifa_id or esquema_tarifa_prefijo(prefijo))

    df_combinado["_DT"] = pd.to_datetime(df_combinado["FECHA_HORA"], format="%d/%m/%Y %H:%M")

    cursor = _cursor_combinado(ruta_salida)
    incremental = cursor is not None and _columnas_combinado(ruta_salida) == columnas_export

    if incremental:
        idx_nuevos = df_combinado.index[df_combinado["_DT"] > cursor]
        if len(idx_nuevos) == 0:
            print(f"  Sin filas nuevas para {nombre_archivo} (cursor {cursor})")
            return df_combinado.drop(columns=["_DT"])

        primer_nuevo = int(idx_nuevos.min())
        inicio_lote = max(0, primer_nuevo - _CONTEXTO_FILAS)
        df_lote = df_combinado.iloc[inicio_lote:].copy()

        print("\n--- Calculando demanda rodante incremental (rolling 15 min) ---")
        df_lote = _calcular_derivados(df_lote, prefijo, esquema, col_con, col_sin)
        df_nuevas = df_lote[df_lote["_DT"] > cursor]

        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        df_nuevas[columnas_export].to_csv(ruta_salida, index=False, header=False, mode="a")
        print(f"OK {nombre_archivo} - {len(df_nuevas)} registro(s) nuevo(s) anexado(s)")
        return df_combinado.drop(columns=["_DT"])

    print("\n--- Calculando demanda rodante (rolling 15 min, reinicio mensual) ---")
    df_procesado = _calcular_derivados(
        df_combinado.drop(columns=["_DT"]), prefijo, esquema, col_con, col_sin
    )

    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    df_procesado[columnas_export].to_csv(ruta_salida, index=False)

    print(f"OK {nombre_archivo} - {len(df_procesado)} registros")
    return df_procesado
