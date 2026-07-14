"""Criterio de capacidad CFE (demanda punta vs factor de carga).

Cargo **Capacidad** (DIST y GDMTH)
----------------------------------
  Criterio 1: demanda máxima **en horario punta** (rodada 15 min, PUNTA_DEM_*_MAX).
  Criterio 2: DemandaCalculadaCFE = E / (f × 24 × d).
  kW facturables = min(criterio1, criterio2) · tarifa Capacidad del mes.

  f = 0,74 (DIST) · 0,57 (GDMTH).

En GDMTH coexisten dos cargos en $/kW con bases de demanda distintas:
  - **Capacidad** (este módulo): compara contra demanda **punta**.
  - **Distribución** (distribution.py): compara contra demanda máxima en
    **cualquier horario** (base, intermedio o punta).
"""

from __future__ import annotations

import pandas as pd

from bess.core.numbers import fmt_kwh, redondear_arriba_kw, redondear_arriba_mxn
from bess.cfe.report_data import (
    dias_transcurridos_mes,
    obtener_demanda_rolada_punta,
    obtener_energia_con_bess_mes,
    obtener_energia_sin_bess_mes,
)
from bess.config.esquema_tarifa import (
    FACTOR_CFE_CAPACIDAD_DIST,
    esquema_tarifa_prefijo,
    factor_cfe_capacidad,
)
from bess.tariffs.loader import cargar_tarifas

FACTOR_CFE_CAPACIDAD = FACTOR_CFE_CAPACIDAD_DIST


def calcular_criterio2_cfe_kw(energia_kwh, dias, *, esquema_tarifa_id: str | None = None):
    """Factor de carga CFE: energía total / (factor × 24 × días transcurridos)."""
    divisor = factor_cfe_capacidad(esquema_tarifa_id) * 24 * dias
    return energia_kwh / divisor if divisor > 0 else 0


def calcular_criterio_cfe(fecha, prefijo, con_bess=True, tarifas=None):
    """
    Cargo por capacidad CFE al día de corte.

    Usa demanda máxima en horario **punta** (no la máxima global del mes).
    Válido para DIST y GDMTH; en GDMTH el cargo Distribución es aparte.
    """
    demanda_punta = obtener_demanda_rolada_punta(fecha, prefijo, con_bess=con_bess)
    if con_bess:
        energia_info = obtener_energia_con_bess_mes(fecha, prefijo)
    else:
        energia_info = obtener_energia_sin_bess_mes(fecha, prefijo)
    if demanda_punta is None or energia_info is None:
        return None

    dias = dias_transcurridos_mes(fecha)
    esquema = esquema_tarifa_prefijo(prefijo)
    energia_kwh = energia_info["total"]
    criterio1_kw = redondear_arriba_kw(demanda_punta)
    criterio2_kw = redondear_arriba_kw(
        calcular_criterio2_cfe_kw(energia_kwh, dias, esquema_tarifa_id=esquema)
    )
    capacidad_kw = min(criterio1_kw, criterio2_kw)
    criterio_aplicado = "punta" if criterio1_kw <= criterio2_kw else "factor_carga"

    if tarifas is None:
        tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))
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
        "factor_carga": factor_cfe_capacidad(esquema),
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
