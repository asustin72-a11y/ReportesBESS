"""Agregados diarios con demandas."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.paths import DIRECTORIO_REPORTES
from bess.core.consumo import kwh_neto_consumo
from bess.cfe.periods import obtener_periodo_por_fecha_hora
from bess.core.kvarh import (
    columnas_kvarh as _columnas_kvarh,
    kvarh_total as _kvarh_total,
    normalizar_columnas_kvarh as _normalizar_columnas_kvarh,
)
from bess.core.dates import agregar_fecha_operativa
from bess.core.console import log

print = log

_MAPA_PERIODO_REC = {
    "Base": "BASE_REC",
    "Intermedio": "INTERMEDIO_REC",
    "Punta": "PUNTA_REC",
}
_MAPA_PERIODO_ENT = {
    "Base": "BASE_ENT",
    "Intermedio": "INTERMEDIO_ENT",
    "Punta": "PUNTA_ENT",
}
_MAPA_PERIODO_SIN_BESS = {
    "Base": "BASE_REC_SIN_BESS",
    "Intermedio": "INTERMEDIO_REC_SIN_BESS",
    "Punta": "PUNTA_REC_SIN_BESS",
}


def _pivot_por_periodo(
    df: pd.DataFrame,
    value_col: str,
    rename_map: dict[str, str],
) -> pd.DataFrame:
    piv = df.pivot_table(
        index="FECHA",
        columns="PERIODO",
        values=value_col,
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    piv = piv.rename(columns=rename_map)
    for col in rename_map.values():
        if col not in piv.columns:
            piv[col] = 0.0
    return piv


def _preparar_minuto(ruta_minuto: str, prefijo: str) -> pd.DataFrame | None:
    df = pd.read_csv(ruta_minuto)
    if "FECHA_HORA" not in df.columns:
        print(f"ERROR: Falta FECHA_HORA en {os.path.basename(ruta_minuto)}")
        return None

    if "PERIODO" not in df.columns:
        df["PERIODO"] = df["FECHA_HORA"].apply(obtener_periodo_por_fecha_hora)
    if "FECHA" not in df.columns:
        df = agregar_fecha_operativa(df, col_fecha_hora="FECHA_HORA")

    col_ent = f"KWH_ENT_{prefijo}"
    if col_ent not in df.columns:
        print(f"ERROR: Falta columna {col_ent} en {os.path.basename(ruta_minuto)}")
        return None

    for col in ("KWH_REC_BESS", "KWH_ENT_BESS"):
        if col not in df.columns:
            print(f"ERROR: Falta columna {col} en {os.path.basename(ruta_minuto)}")
            return None

    return df


def generar_diarios_con_demandas(prefijo):
    """Genera archivos diarios con demandas máximas."""
    print("\n" + "=" * 60)
    print(f"GENERANDO ARCHIVOS DIARIOS ({prefijo}) CON DEMANDAS MAXIMAS")
    print("=" * 60)

    ruta_minuto = os.path.join(DIRECTORIO_REPORTES, f"COMBINADO_POR_MINUTO_{prefijo}.csv")
    if not os.path.exists(ruta_minuto):
        print(f"ERROR: Falta COMBINADO_POR_MINUTO_{prefijo}.csv")
        return None

    df_minuto = _preparar_minuto(ruta_minuto, prefijo)
    if df_minuto is None:
        return None

    print(f"  Energía y sin BESS desde COMBINADO_POR_MINUTO_{prefijo}.csv (5 min)")

    col_ent = f"KWH_ENT_{prefijo}"
    df_ent = df_minuto.groupby(["FECHA", "PERIODO"], as_index=False)[col_ent].sum()
    df_med_ent_pivot = _pivot_por_periodo(df_ent, col_ent, _MAPA_PERIODO_ENT)

    df_minuto = df_minuto.copy()
    df_minuto["_KWH_CONSUMO"] = kwh_neto_consumo(df_minuto, prefijo)
    df_rec = df_minuto.groupby(["FECHA", "PERIODO"], as_index=False)["_KWH_CONSUMO"].sum()
    df_med_rec_pivot = _pivot_por_periodo(df_rec, "_KWH_CONSUMO", _MAPA_PERIODO_REC)

    df_med_diario = df_med_ent_pivot.merge(df_med_rec_pivot, on="FECHA", how="outer").fillna(0)

    df_minuto["KWH_SIN_BESS"] = (
        df_minuto["_KWH_CONSUMO"]
        - pd.to_numeric(df_minuto["KWH_REC_BESS"], errors="coerce").fillna(0)
        + pd.to_numeric(df_minuto["KWH_ENT_BESS"], errors="coerce").fillna(0)
    )
    df_sin = df_minuto.groupby(["FECHA", "PERIODO"], as_index=False)["KWH_SIN_BESS"].sum()
    df_sin_pivot = _pivot_por_periodo(df_sin, "KWH_SIN_BESS", _MAPA_PERIODO_SIN_BESS)
    df_med_diario = df_med_diario.merge(df_sin_pivot, on="FECHA", how="left").fillna(0)

    # Demandas máximas (rolling 15 min en combinado por minuto)
    col_con_dem = f"IUSA_CON_BESS_{prefijo}_kW_DEM_15min"
    col_sin_dem = f"IUSA_SIN_BESS_{prefijo}_kW_DEM_15min"

    idx_con_max = df_minuto.groupby(["FECHA", "PERIODO"])[col_con_dem].idxmax()
    df_con_max = df_minuto.loc[
        idx_con_max,
        ["FECHA", "PERIODO", col_con_dem, "FECHA_HORA"],
    ].reset_index(drop=True)

    df_con_max_kw = df_con_max.pivot_table(
        index="FECHA", columns="PERIODO", values=col_con_dem, aggfunc="max", fill_value=0
    ).reset_index()
    df_con_max_kw = df_con_max_kw.rename(
        columns={
            "Base": "BASE_DEM_CON_BESS",
            "Intermedio": "INTERMEDIO_DEM_CON_BESS",
            "Punta": "PUNTA_DEM_CON_BESS",
        }
    )

    df_con_max_fh = df_con_max.pivot_table(
        index="FECHA", columns="PERIODO", values="FECHA_HORA", aggfunc="first", fill_value=""
    ).reset_index()
    df_con_max_fh = df_con_max_fh.rename(
        columns={
            "Base": "BASE_DEM_CON_BESS_FECHA_HORA",
            "Intermedio": "INTERMEDIO_DEM_CON_BESS_FECHA_HORA",
            "Punta": "PUNTA_DEM_CON_BESS_FECHA_HORA",
        }
    )

    idx_sin_max = df_minuto.groupby(["FECHA", "PERIODO"])[col_sin_dem].idxmax()
    df_sin_max = df_minuto.loc[
        idx_sin_max,
        ["FECHA", "PERIODO", col_sin_dem, "FECHA_HORA"],
    ].reset_index(drop=True)

    df_sin_max_kw = df_sin_max.pivot_table(
        index="FECHA", columns="PERIODO", values=col_sin_dem, aggfunc="max", fill_value=0
    ).reset_index()
    df_sin_max_kw = df_sin_max_kw.rename(
        columns={
            "Base": "BASE_DEM_SIN_BESS",
            "Intermedio": "INTERMEDIO_DEM_SIN_BESS",
            "Punta": "PUNTA_DEM_SIN_BESS",
        }
    )

    df_sin_max_fh = df_sin_max.pivot_table(
        index="FECHA", columns="PERIODO", values="FECHA_HORA", aggfunc="first", fill_value=""
    ).reset_index()
    df_sin_max_fh = df_sin_max_fh.rename(
        columns={
            "Base": "BASE_DEM_SIN_BESS_FECHA_HORA",
            "Intermedio": "INTERMEDIO_DEM_SIN_BESS_FECHA_HORA",
            "Punta": "PUNTA_DEM_SIN_BESS_FECHA_HORA",
        }
    )

    for df_temp in [df_con_max_kw, df_con_max_fh, df_sin_max_kw, df_sin_max_fh]:
        df_med_diario = df_med_diario.merge(df_temp, on="FECHA", how="left").fillna(
            0 if "DEM" in df_temp.columns[1] else ""
        )

    if _columnas_kvarh(df_minuto):
        df_kvarh_src = _normalizar_columnas_kvarh(df_minuto.copy())
        df_kvarh_src["KVARH"] = _kvarh_total(df_kvarh_src, prefijo)
        df_kvarh_dia = df_kvarh_src.groupby("FECHA", as_index=False)["KVARH"].sum()
        df_med_diario = df_med_diario.merge(df_kvarh_dia, on="FECHA", how="left")
        df_med_diario["KVARH"] = pd.to_numeric(df_med_diario["KVARH"], errors="coerce").fillna(0)
    else:
        df_med_diario["KVARH"] = 0.0

    columnas_med = [
        "FECHA",
        "BASE_ENT",
        "INTERMEDIO_ENT",
        "PUNTA_ENT",
        "BASE_REC",
        "INTERMEDIO_REC",
        "PUNTA_REC",
        "BASE_REC_SIN_BESS",
        "INTERMEDIO_REC_SIN_BESS",
        "PUNTA_REC_SIN_BESS",
        "KVARH",
        "BASE_DEM_CON_BESS",
        "BASE_DEM_CON_BESS_FECHA_HORA",
        "INTERMEDIO_DEM_CON_BESS",
        "INTERMEDIO_DEM_CON_BESS_FECHA_HORA",
        "PUNTA_DEM_CON_BESS",
        "PUNTA_DEM_CON_BESS_FECHA_HORA",
        "BASE_DEM_SIN_BESS",
        "BASE_DEM_SIN_BESS_FECHA_HORA",
        "INTERMEDIO_DEM_SIN_BESS",
        "INTERMEDIO_DEM_SIN_BESS_FECHA_HORA",
        "PUNTA_DEM_SIN_BESS",
        "PUNTA_DEM_SIN_BESS_FECHA_HORA",
    ]

    df_med_diario = df_med_diario[columnas_med]
    df_med_diario["FECHA_DT"] = pd.to_datetime(df_med_diario["FECHA"], format="%d/%m/%Y")
    df_med_diario = df_med_diario.sort_values("FECHA_DT").drop("FECHA_DT", axis=1)

    nombre_med_dia = f"ENERGIA_{prefijo}_POR_DIA.csv"
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_med_dia)
    df_med_diario.to_csv(ruta_salida, index=False)
    print(f"OK {nombre_med_dia} - {len(df_med_diario)} dias")

    return df_med_diario
