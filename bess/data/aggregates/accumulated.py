"""Acumulados por medidor."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.subestaciones import (
    medidor_consumo_por_prefijo,
    ruta_energia_dia_por_prefijo,
)
from bess.core.atomic_io import ruta_temporal_atomica
from bess.data.aggregates._incremental_dia import (
    columnas_dia,
    combinar_cola_diaria,
    cursor_dia,
)

from bess.core.console import log
print = log

# Fijo (no depende de los datos): permite comparar contra el encabezado de
# un ACUMULADOS_*.csv existente para decidir si el recálculo incremental
# aplica (ver _incremental_dia.py). El orden importa: es el orden en que
# el código original iba agregando columnas a df_acum_med.
COLUMNAS_ACUMULADO = [
    "FECHA",
    "BASE_REC_ACUM",
    "INTERMEDIO_REC_ACUM",
    "PUNTA_REC_ACUM",
    "BASE_ENT_ACUM",
    "INTERMEDIO_ENT_ACUM",
    "PUNTA_ENT_ACUM",
    "KVARH_ACUM",
    "BASE_DEM_CON_BESS_MAX",
    "BASE_DEM_CON_BESS_MAX_FECHA_HORA",
    "INTERMEDIO_DEM_CON_BESS_MAX",
    "INTERMEDIO_DEM_CON_BESS_MAX_FECHA_HORA",
    "PUNTA_DEM_CON_BESS_MAX",
    "PUNTA_DEM_CON_BESS_MAX_FECHA_HORA",
    "BASE_DEM_SIN_BESS_MAX",
    "BASE_DEM_SIN_BESS_MAX_FECHA_HORA",
    "INTERMEDIO_DEM_SIN_BESS_MAX",
    "INTERMEDIO_DEM_SIN_BESS_MAX_FECHA_HORA",
    "PUNTA_DEM_SIN_BESS_MAX",
    "PUNTA_DEM_SIN_BESS_MAX_FECHA_HORA",
]

_COLS_CUMSUM_REC = ("BASE_REC", "INTERMEDIO_REC", "PUNTA_REC")
_COLS_CUMSUM_ENT = ("BASE_ENT", "INTERMEDIO_ENT", "PUNTA_ENT")

_GRUPOS_DEMANDA = (
    ("BASE_DEM_CON_BESS", "INTERMEDIO_DEM_CON_BESS", "PUNTA_DEM_CON_BESS"),
    ("BASE_DEM_SIN_BESS", "INTERMEDIO_DEM_SIN_BESS", "PUNTA_DEM_SIN_BESS"),
)


def _cumsum_con_semilla(serie: pd.Series, meses: pd.Series, semilla: float) -> pd.Series:
    """cumsum por mes (como `df.groupby('MES')[col].cumsum()`), pero
    arrancando desde `semilla` en el primer mes de la serie en vez de 0 --
    pensado para heredar el acumulado del día anterior en una corrida
    incremental. `semilla=0` es equivalente a no tener semilla (sumar 0 no
    cambia el resultado), así que también cubre el caso de la primera
    corrida / sin contexto previo."""
    df_tmp = pd.DataFrame({"valor": serie.to_numpy(), "mes": meses.to_numpy()})
    if semilla:
        fila_semilla = pd.DataFrame({"valor": [semilla], "mes": [meses.iloc[0]]})
        df_tmp = pd.concat([fila_semilla, df_tmp], ignore_index=True)
        resultado = df_tmp.groupby("mes")["valor"].cumsum()
        return resultado.iloc[1:].reset_index(drop=True)
    return df_tmp.groupby("mes")["valor"].cumsum().reset_index(drop=True)


def _seed_desde_acumulado_previo(ruta_salida: str, cursor: "pd.Timestamp"):
    """Fila (Series) del ACUMULADOS_*.csv existente correspondiente al día
    anterior a `cursor`, si existe y es del mismo mes que `cursor` -- o
    None si no aplica (archivo nuevo, o `cursor` es el primer día de su
    mes, en cuyo caso no hay nada que heredar y se reinicia en 0)."""
    if not os.path.exists(ruta_salida):
        return None
    try:
        df_prev = pd.read_csv(ruta_salida)
    except (ValueError, OSError):
        return None
    if df_prev.empty or "FECHA" not in df_prev.columns:
        return None
    fecha_dt = pd.to_datetime(df_prev["FECHA"], format="%d/%m/%Y", errors="coerce")
    df_prev = df_prev.assign(_FECHA_DT=fecha_dt).sort_values("_FECHA_DT")
    anteriores = df_prev[df_prev["_FECHA_DT"] < cursor]
    if anteriores.empty:
        return None
    fila_prev = anteriores.iloc[-1]
    if fila_prev["_FECHA_DT"].to_period("M") != cursor.to_period("M"):
        return None
    return fila_prev


def generar_acumulados(prefijo):
    """Genera archivos acumulados por mes.

    Incremental: cumsum y máximo corrido son estado que se acumula día a
    día DENTRO de cada mes -- a diferencia de daily.py, aquí sí hay
    dependencia entre días consecutivos del mismo mes. Si el acumulado ya
    existe con cursor legible y columnas compatibles, se recalcula desde
    el último día ya escrito (por si seguía abierto) en adelante,
    heredando como semilla el cumsum/máximo del día anterior (si es del
    mismo mes; si el día ya escrito era el primero del mes, se reinicia en
    cero, igual que antes). La primera vez (o si cambia el formato de
    columnas) procesa completo, como antes.
    """
    print("\n" + "=" * 60)
    print(f"GENERANDO ARCHIVOS ACUMULADOS ({prefijo})")
    print("=" * 60)

    med = medidor_consumo_por_prefijo(prefijo)
    ruta_med_dia_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_med_dia_p or not ruta_med_dia_p.exists():
        print(f"ERROR: No se encuentra energía diaria para {prefijo}")
        return None
    ruta_med_dia = str(ruta_med_dia_p)
    if med:
        ruta_salida = str(med.ruta_acumulados())
        nombre_med_acum = med.ruta_acumulados().name
    else:
        nombre_med_acum = f"ACUMULADOS_{prefijo}.csv"
        ruta_salida = nombre_med_acum

    if not os.path.exists(ruta_med_dia):
        print(f"ERROR: No se encuentra {ruta_med_dia}")
        return None

    df_med_dia = pd.read_csv(ruta_med_dia)
    df_med_dia["FECHA_DT"] = pd.to_datetime(df_med_dia["FECHA"], format="%d/%m/%Y")
    df_med_dia = df_med_dia.sort_values("FECHA_DT").reset_index(drop=True)

    cursor = cursor_dia(ruta_salida)
    incremental = cursor is not None and columnas_dia(ruta_salida) == COLUMNAS_ACUMULADO
    seed = None

    if incremental:
        df_med_dia = df_med_dia[df_med_dia["FECHA_DT"] >= cursor].reset_index(drop=True)
        if df_med_dia.empty:
            print(f"  Sin días nuevos para {nombre_med_acum} (cursor {cursor.date()})")
            return pd.read_csv(ruta_salida)
        seed = _seed_desde_acumulado_previo(ruta_salida, cursor)

    df_med_dia["MES"] = df_med_dia["FECHA_DT"].dt.to_period("M")

    df_acum_med = pd.DataFrame()
    df_acum_med["FECHA"] = df_med_dia["FECHA"]

    for col in _COLS_CUMSUM_REC:
        seed_valor = float(seed[f"{col}_ACUM"]) if seed is not None else 0.0
        serie = df_med_dia[col] if col in df_med_dia.columns else pd.Series(0.0, index=df_med_dia.index)
        df_acum_med[f"{col}_ACUM"] = _cumsum_con_semilla(serie, df_med_dia["MES"], seed_valor)

    for col in _COLS_CUMSUM_ENT:
        seed_valor = float(seed[f"{col}_ACUM"]) if seed is not None else 0.0
        serie = df_med_dia[col] if col in df_med_dia.columns else pd.Series(0.0, index=df_med_dia.index)
        df_acum_med[f"{col}_ACUM"] = _cumsum_con_semilla(serie, df_med_dia["MES"], seed_valor)

    seed_kvarh = float(seed["KVARH_ACUM"]) if seed is not None else 0.0
    serie_kvarh = (
        df_med_dia["KVARH"] if "KVARH" in df_med_dia.columns else pd.Series(0.0, index=df_med_dia.index)
    )
    df_acum_med["KVARH_ACUM"] = _cumsum_con_semilla(serie_kvarh, df_med_dia["MES"], seed_kvarh)

    for cols_demanda in _GRUPOS_DEMANDA:
        for col_valor in cols_demanda:
            col_fh = f"{col_valor}_FECHA_HORA"
            if seed is not None:
                max_valor = float(seed.get(f"{col_valor}_MAX", 0) or 0)
                max_fh = seed.get(f"{col_valor}_MAX_FECHA_HORA", "") or ""
            else:
                max_valor = 0.0
                max_fh = ""
            mes_actual = None
            valores = []
            fechahoras = []

            for _, row in df_med_dia.iterrows():
                mes_row = row["MES"]
                if mes_actual is None:
                    mes_actual = mes_row
                elif mes_actual != mes_row:
                    max_valor = 0.0
                    max_fh = ""
                    mes_actual = mes_row

                valor_actual = row.get(col_valor, 0)
                fh_actual = row.get(col_fh, "")
                if pd.isna(valor_actual):
                    valor_actual = 0
                if pd.isna(fh_actual):
                    fh_actual = ""
                if valor_actual > max_valor:
                    max_valor = valor_actual
                    max_fh = fh_actual

                valores.append(max_valor)
                fechahoras.append(max_fh)

            df_acum_med[f"{col_valor}_MAX"] = valores
            df_acum_med[f"{col_valor}_MAX_FECHA_HORA"] = fechahoras

    df_acum_med = df_acum_med[COLUMNAS_ACUMULADO]

    if incremental:
        df_acum_med = combinar_cola_diaria(df_acum_med, ruta_salida, COLUMNAS_ACUMULADO)

    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    # Escritura atómica (bess.core.atomic_io): si algo interrumpe esta
    # escritura a medio camino, ruta_salida conserva su contenido anterior
    # en vez de quedar truncado.
    with ruta_temporal_atomica(ruta_salida) as ruta_temp:
        df_acum_med.to_csv(ruta_temp, index=False)
    print(f"OK {nombre_med_acum} - {len(df_acum_med)} dias (acumulado por mes)")

    return df_acum_med
