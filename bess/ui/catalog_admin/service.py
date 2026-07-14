"""Servicio de lectura/escritura del catálogo para la UI de administración."""

from __future__ import annotations

import pandas as pd

from bess.config.catalog import (
    CAMPOS_MEDIDORES,
    CAMPOS_SUBESTACIONES,
    CAMPOS_TIPO_MEDIDOR,
    CatalogError,
    GENERACION_GRUPO,
    GENERACION_INDIVIDUAL,
    GENERACION_NINGUNA,
    guardar_filas_catalogo,
    leer_filas_catalogo,
    validar_filas_catalogo,
)
from bess.data.catalog_db import ruta_bd_catalogo

ETIQUETAS_GENERACION = {
    GENERACION_NINGUNA: "0 — Sin generación",
    GENERACION_GRUPO: "1 — Grupo (tipo 4, Mega…)",
    GENERACION_INDIVIDUAL: "2 — Individual (tipo 5)",
}

REGLAS_RESUMEN = """
**Por subestación**
- Al menos un medidor asignado.
- Exactamente **1** medidor tipo 1 (Neteo / facturación).
- Al menos **1** medidor tipo 3 (BESS).
- `Generacion=0` → sin tipos 4 ni 5.
- `Generacion=1` → medidores tipo 4 con `Grupo_Generacion`; sin tipo 5.
- `Generacion=2` → exactamente un medidor tipo 5; sin tipo 4.

**Por medidor**
- `Descarga=ION` → IP válida (no vacía ni `0`).
- `Descarga=API` → `Numero_Serie` obligatorio.
- Tipo 4 en subestación con generación grupo → `Grupo_Generacion` requerido.
"""


def _filas_a_df(filas: list[dict[str, str]], columnas: tuple[str, ...]) -> pd.DataFrame:
    if not filas:
        return pd.DataFrame(columns=list(columnas))
    df = pd.DataFrame(filas)
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    return df[list(columnas)].astype(str)


def _df_a_filas(df: pd.DataFrame, columnas: tuple[str, ...]) -> list[dict[str, str]]:
    filas: list[dict[str, str]] = []
    for _, row in df.iterrows():
        fila: dict[str, str] = {}
        for col in columnas:
            valor = row.get(col, "")
            if pd.isna(valor):
                valor = ""
            texto = str(valor).strip()
            if col in ("Neteo", "Invertir") and texto.lower() in ("true", "false"):
                texto = "1" if texto.lower() == "true" else "0"
            fila[col] = texto
        filas.append(fila)
    return filas


def cargar_dataframes() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tipos, subs, meds = leer_filas_catalogo()
    return (
        _filas_a_df(tipos, CAMPOS_TIPO_MEDIDOR),
        _filas_a_df(subs, CAMPOS_SUBESTACIONES),
        _filas_a_df(meds, CAMPOS_MEDIDORES),
    )


def validar_dataframes(
    df_tipos: pd.DataFrame,
    df_subs: pd.DataFrame,
    df_meds: pd.DataFrame,
) -> list[str]:
    return validar_filas_catalogo(
        _df_a_filas(df_tipos, CAMPOS_TIPO_MEDIDOR),
        _df_a_filas(df_subs, CAMPOS_SUBESTACIONES),
        _df_a_filas(df_meds, CAMPOS_MEDIDORES),
    )


def guardar_dataframes(
    df_tipos: pd.DataFrame,
    df_subs: pd.DataFrame,
    df_meds: pd.DataFrame,
) -> None:
    try:
        guardar_filas_catalogo(
            _df_a_filas(df_tipos, CAMPOS_TIPO_MEDIDOR),
            _df_a_filas(df_subs, CAMPOS_SUBESTACIONES),
            _df_a_filas(df_meds, CAMPOS_MEDIDORES),
        )
    except CatalogError as exc:
        raise ValueError("\n".join(exc.errores)) from exc


def ruta_almacenamiento() -> str:
    return str(ruta_bd_catalogo())
