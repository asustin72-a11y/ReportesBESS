"""Administración de datos de cliente CFE por subestación (recibo)."""

from __future__ import annotations

import pandas as pd

from bess.data.cliente_recibo_db import (
    CAMPOS_CLIENTE_RECIBO,
    guardar_filas_cliente_recibo,
    leer_filas_cliente_recibo,
)

REGLAS_CLIENTE = """
**Datos del recibo simulado (por subestación)**
- Una fila por subestación; alimenta el encabezado del recibo (razón social, cuenta, RMU, medidor, etc.).
- **Dirección:** un renglón por línea del domicilio fiscal.
- **Tarifa:** etiqueta visible (p. ej. DIST, GDMTH). Si queda vacía, se usa el esquema tarifario del catálogo.
- **Carga / demanda contratada:** enteros en kW; vacío si no aplica.
"""


def cargar_dataframe_clientes() -> pd.DataFrame:
    filas = leer_filas_cliente_recibo()
    if not filas:
        return pd.DataFrame(columns=list(CAMPOS_CLIENTE_RECIBO))
    return pd.DataFrame(filas)[list(CAMPOS_CLIENTE_RECIBO)].astype(str)


def validar_dataframe_clientes(df: pd.DataFrame) -> list[str]:
    errores: list[str] = []
    if df is None or df.empty:
        return ["No hay subestaciones en el catálogo."]
    vistos: set[str] = set()
    for _, row in df.iterrows():
        sub = str(row.get("Subestacion", "")).strip()
        if not sub:
            errores.append("Hay filas sin nombre de subestación.")
            continue
        if sub in vistos:
            errores.append(f'Subestación duplicada: "{sub}".')
        vistos.add(sub)
        if not str(row.get("Razon_social", "")).strip():
            errores.append(f'"{sub}": falta razón social.')
        for campo in ("Carga_conectada_kW", "Demanda_contratada_kW"):
            texto = str(row.get(campo, "")).strip()
            if texto and texto.lower() not in ("nan", "—", "-"):
                try:
                    int(float(texto))
                except ValueError:
                    errores.append(f'"{sub}": {campo} debe ser un entero o vacío.')
    return errores


def guardar_dataframe_clientes(df: pd.DataFrame) -> None:
    errores = validar_dataframe_clientes(df)
    if errores:
        raise ValueError("\n".join(errores))
    filas = []
    for _, row in df.iterrows():
        fila = {
            col: "" if pd.isna(row.get(col)) else str(row.get(col, "")).strip()
            for col in CAMPOS_CLIENTE_RECIBO
        }
        filas.append(fila)
    guardar_filas_cliente_recibo(filas)
