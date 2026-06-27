"""Criterio de capacidad CFE (demanda punta vs factor de carga)."""

from __future__ import annotations

import pandas as pd

from bess.core.numbers import fmt_kwh, redondear_arriba_kw, redondear_arriba_mxn
from bess.cfe.report_data import (
    dias_transcurridos_mes,
    obtener_demanda_rolada_punta,
    obtener_energia_con_bess_mes,
    obtener_energia_sin_bess_mes,
)
from bess.tariffs.loader import cargar_tarifas

FACTOR_CFE_CAPACIDAD = 0.74


def calcular_criterio2_cfe_kw(energia_kwh, dias):
    """Factor de carga CFE: energía total / (0.74 × 24 × días transcurridos)."""
    divisor = FACTOR_CFE_CAPACIDAD * 24 * dias
    return energia_kwh / divisor if divisor > 0 else 0


def calcular_criterio_cfe(fecha, prefijo, con_bess=True, tarifas=None):
    """
    Criterio CFE: capacidad (kW) = min(demanda máx. punta, factor de carga).
    Costo = capacidad × tarifa capacidad del mes.
    """
    demanda_punta = obtener_demanda_rolada_punta(fecha, prefijo, con_bess=con_bess)
    if con_bess:
        energia_info = obtener_energia_con_bess_mes(fecha, prefijo)
    else:
        energia_info = obtener_energia_sin_bess_mes(fecha, prefijo)
    if demanda_punta is None or energia_info is None:
        return None

    dias = dias_transcurridos_mes(fecha)
    energia_kwh = energia_info["total"]
    criterio1_kw = redondear_arriba_kw(demanda_punta)
    criterio2_kw = redondear_arriba_kw(calcular_criterio2_cfe_kw(energia_kwh, dias))
    capacidad_kw = min(criterio1_kw, criterio2_kw)
    criterio_aplicado = "punta" if criterio1_kw <= criterio2_kw else "factor_carga"

    if tarifas is None:
        tarifas = cargar_tarifas()
    mes = fecha.month
    precio_cap = tarifas.get("Capacidad", {}).get(mes, 0)

    return {
        "criterio1_punta_kw": criterio1_kw,
        "criterio2_factor_kw": criterio2_kw,
        "capacidad_kw": capacidad_kw,
        "criterio_aplicado": criterio_aplicado,
        "energia_kwh": energia_kwh,
        "energia_por_periodo": energia_info["por_periodo"],
        "dias_mes": dias,
        "precio_cap": precio_cap,
        "costo_mxn": redondear_arriba_mxn(capacidad_kw * precio_cap),
    }


def construir_tabla_criterio_cfe(resultado_con, resultado_sin=None):
    filas = []
    for escenario, res in [("Con BESS", resultado_con), ("Sin BESS", resultado_sin)]:
        if res is None:
            continue
        lbl_criterio = (
            "Demanda punta"
            if res["criterio_aplicado"] == "punta"
            else "DemandaCalculadaCFE"
        )
        pp = res.get("energia_por_periodo", {})
        filas.append({
            "Escenario": escenario,
            "Energía (kWh)": fmt_kwh(res["energia_kwh"]),
            "Base (kWh)": fmt_kwh(pp.get("base", 0)),
            "Intermedio (kWh)": fmt_kwh(pp.get("intermedio", 0)),
            "Punta (kWh)": fmt_kwh(pp.get("punta", 0)),
            "Días transcurridos": res["dias_mes"],
            "Demanda punta (kW)": f"{int(res['criterio1_punta_kw']):,}",
            "DemandaCalculadaCFE": f"{res['criterio2_factor_kw']:,}",
            "Capacidad CFE (kW)": f"{res['capacidad_kw']:,}",
            "Criterio aplicado": lbl_criterio,
            "Costo capacidad (MXN)": f"${res['costo_mxn']:,.2f}",
        })
    return pd.DataFrame(filas) if filas else None
