"""Reporte acumulado BESS: ahorros del mes a la fecha de corte."""

from __future__ import annotations

import os
from datetime import date

import pandas as pd

from bess.cfe.arbitrage import calcular_arbitraje_rango
from bess.cfe.shapley import ParticipacionCapacidadError, calcular_participacion_capacidad
from bess.config.paths import ruta_energia_bess_por_dia
from bess.config.subestaciones import (
    medidor_consumo_por_prefijo,
    subestacion_por_prefijo,
    soporta_participacion_capacidad,
)
from bess.core.numbers import fmt_kwh, kwh_para_calculo, redondear_mxn_energia, sumar_energia
from bess.reports.dia_tipo import buscar_dia_tipo


class ReporteAcumuladoError(Exception):
    """Datos insuficientes para el reporte acumulado."""


def _sumar_columnas_rango(
    ruta_csv: str,
    fecha_inicio: date,
    fecha_fin: date,
    columnas: list[str],
) -> dict[str, float]:
    resultado = {c: 0.0 for c in columnas}
    if not os.path.exists(ruta_csv):
        return resultado
    df = pd.read_csv(ruta_csv)
    df["FECHA_DT"] = pd.to_datetime(df["FECHA"], format="%d/%m/%Y")
    mask = (df["FECHA_DT"].dt.date >= fecha_inicio) & (df["FECHA_DT"].dt.date <= fecha_fin)
    df_r = df[mask]
    for col in columnas:
        if col in df_r.columns:
            resultado[col] = float(pd.to_numeric(df_r[col], errors="coerce").fillna(0).sum())
    return resultado


def calcular_reporte_acumulado(prefijo: str, fecha_corte: date, *, tarifas: dict | None = None) -> dict:
    """
    Ahorros BESS acumulados del día 1 del mes a fecha_corte (inclusive).

    Incluye operación (carga/descarga), arbitraje y atribución Shapley solo del BESS
    (reducción de capacidad en kW y MXN).
    """
    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        raise ReporteAcumuladoError(f"Medidor desconocido: {prefijo}")

    sub = subestacion_por_prefijo(prefijo)
    fecha_inicio = fecha_corte.replace(day=1)
    if fecha_corte < fecha_inicio:
        raise ReporteAcumuladoError("La fecha de corte debe pertenecer al mes en curso.")

    ruta_bess = str(ruta_energia_bess_por_dia(prefijo))
    cols = [
        "BASE_REC",
        "INTERMEDIO_REC",
        "PUNTA_REC",
        "BASE_ENT",
        "INTERMEDIO_ENT",
        "PUNTA_ENT",
    ]
    sums = _sumar_columnas_rango(ruta_bess, fecha_inicio, fecha_corte, cols)
    if not os.path.exists(ruta_bess):
        raise ReporteAcumuladoError(
            f"No existe {os.path.basename(ruta_bess)}. Genere reportes CSV primero."
        )

    carga_base = sumar_energia(sums["BASE_REC"])
    carga_intermedio = sumar_energia(sums["INTERMEDIO_REC"])
    carga_punta = sumar_energia(sums["PUNTA_REC"])
    descarga_base = sumar_energia(sums["BASE_ENT"])
    descarga_intermedio = sumar_energia(sums["INTERMEDIO_ENT"])
    descarga_punta = sumar_energia(sums["PUNTA_ENT"])

    carga_total = (
        kwh_para_calculo(carga_base)
        + kwh_para_calculo(carga_intermedio)
        + kwh_para_calculo(carga_punta)
    )
    descarga_total = (
        kwh_para_calculo(descarga_base)
        + kwh_para_calculo(descarga_intermedio)
        + kwh_para_calculo(descarga_punta)
    )
    eficiencia_pct = (descarga_total / carga_total * 100) if carga_total > 0 else 0.0

    arb = calcular_arbitraje_rango(
        fecha_inicio,
        fecha_corte,
        prefijo,
        carga_base=carga_base,
        carga_intermedio=carga_intermedio,
        carga_punta=carga_punta,
        descarga_base=descarga_base,
        descarga_intermedio=descarga_intermedio,
        descarga_punta=descarga_punta,
        tarifas=tarifas,
    )
    arbitraje_mxn = redondear_mxn_energia(arb["total"])

    shapley_bess_kw = 0
    shapley_bess_mxn = 0.0
    shapley_disponible = bool(sub and soporta_participacion_capacidad(sub.id))
    shapley_error: str | None = None

    if shapley_disponible and sub:
        try:
            part = calcular_participacion_capacidad(sub.id, fecha_corte, tarifas=tarifas)
            shapley_bess_kw = int(part["shapley_kw"]["bess"])
            shapley_bess_mxn = redondear_mxn_energia(part["shapley_mxn"]["bess"])
        except ParticipacionCapacidadError as exc:
            shapley_error = str(exc)

    ahorro_demanda_mxn = shapley_bess_mxn
    ahorro_total_mxn = redondear_mxn_energia(arbitraje_mxn + ahorro_demanda_mxn)

    meses = (
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    )
    periodo_label = f"{meses[fecha_corte.month - 1]} {fecha_corte.year}"
    dia_tipo = buscar_dia_tipo(prefijo, fecha_corte)

    filas = [
        {"Concepto": "Energía cargada", "Valor": f"{fmt_kwh(carga_total)} kWh"},
        {"Concepto": "Energía descargada", "Valor": f"{fmt_kwh(descarga_total)} kWh"},
        {"Concepto": "Eficiencia", "Valor": f"{eficiencia_pct:.1f} %"},
        {"Concepto": "Ahorro por arbitraje", "Valor": f"${arbitraje_mxn:,.2f}"},
        {
            "Concepto": "Reducción de demanda aportada por el BESS (Shapley)",
            "Valor": f"{shapley_bess_kw:,} kW" if shapley_disponible else "—",
        },
        {
            "Concepto": "Ahorro de la reducción de demanda",
            "Valor": f"${ahorro_demanda_mxn:,.2f}" if shapley_disponible else "—",
        },
        {
            "Concepto": "Ahorro total del mes (arbitraje + demanda)",
            "Valor": f"${ahorro_total_mxn:,.2f}",
        },
    ]

    return {
        "prefijo": prefijo,
        "subestacion_id": sub.id if sub else "",
        "subestacion_nombre": sub.nombre if sub else "",
        "medidor_nombre": med.nombre,
        "fecha_inicio": fecha_inicio,
        "fecha_corte": fecha_corte,
        "dias": (fecha_corte - fecha_inicio).days + 1,
        "periodo_label": periodo_label,
        "carga_total_kwh": carga_total,
        "descarga_total_kwh": descarga_total,
        "eficiencia_pct": eficiencia_pct,
        "arbitraje": arb,
        "arbitraje_mxn": arbitraje_mxn,
        "shapley_bess_kw": shapley_bess_kw,
        "shapley_bess_mxn": shapley_bess_mxn,
        "shapley_disponible": shapley_disponible,
        "shapley_error": shapley_error,
        "ahorro_demanda_mxn": ahorro_demanda_mxn,
        "ahorro_total_mxn": ahorro_total_mxn,
        "tabla_resumen": pd.DataFrame(filas),
        "dia_tipo": dia_tipo,
    }
