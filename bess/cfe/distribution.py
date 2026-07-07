"""Cargo por distribución GDMTH (recibo CFE).

GDMTH — dos cargos en $/kW
--------------------------
  Capacidad     (capacity.calcular_criterio_cfe): min(demanda **punta**, D_calc).
  Distribución  (este módulo):                    min(demanda **máx. cualquier horario**, D_calc).

Ambos comparten la misma DemandaCalculadaCFE (f = 0,57) pero difieren en el
primer término del mínimo.

Fórmula Distribución
--------------------
  D_max   Máxima demanda del mes en cualquier periodo (base, intermedio o punta).
          max(BASE_DEM_*_MAX, INTERMEDIO_DEM_*_MAX, PUNTA_DEM_*_MAX) en ACUMULADOS.
  D_calc  E_total / (0,57 × 24 × d).
  D_dist  min(D_max, D_calc), redondeo ceil en kW.
  Costo   D_dist × tarifa Distribución ($/kW).
"""

from __future__ import annotations

from bess.cfe.capacity import calcular_criterio2_cfe_kw
from bess.cfe.report_data import (
    dias_transcurridos_mes,
    obtener_demanda_max_mes,
    obtener_energia_con_bess_mes,
    obtener_energia_sin_bess_mes,
)
from bess.config.esquema_tarifa import (
    ESQUEMA_GDMTH,
    esquema_tarifa_prefijo,
    factor_cfe_capacidad,
)
from bess.core.numbers import redondear_arriba_kw, redondear_arriba_mxn
from bess.tariffs.loader import cargar_tarifas


def calcular_distribucion_gdmth(
    fecha,
    prefijo: str,
    con_bess: bool = True,
    tarifas: dict | None = None,
):
    """
    Cargo por distribución GDMTH al día de corte.

    Retorna None si el prefijo no es GDMTH o faltan datos.
    """
    esquema = esquema_tarifa_prefijo(prefijo)
    if esquema != ESQUEMA_GDMTH:
        return None

    demanda_max = obtener_demanda_max_mes(fecha, prefijo, con_bess=con_bess)
    if con_bess:
        energia_info = obtener_energia_con_bess_mes(fecha, prefijo)
    else:
        energia_info = obtener_energia_sin_bess_mes(fecha, prefijo)
    if demanda_max is None or energia_info is None:
        return None

    dias = dias_transcurridos_mes(fecha)
    energia_kwh = energia_info["total"]
    criterio1_kw = redondear_arriba_kw(demanda_max)
    criterio2_kw = redondear_arriba_kw(
        calcular_criterio2_cfe_kw(energia_kwh, dias, esquema_tarifa_id=esquema)
    )
    distribucion_kw = min(criterio1_kw, criterio2_kw)
    criterio_aplicado = (
        "demanda_maxima" if criterio1_kw <= criterio2_kw else "factor_carga"
    )

    if tarifas is None:
        tarifas = cargar_tarifas(esquema)
    mes = fecha.month
    precio_dist = float(tarifas.get("Distribucion", {}).get(mes, 0) or 0)

    return {
        "criterio1_demanda_max_kw": criterio1_kw,
        "criterio2_factor_kw": criterio2_kw,
        "distribucion_kw": distribucion_kw,
        "criterio_aplicado": criterio_aplicado,
        "energia_kwh": energia_kwh,
        "energia_por_periodo": energia_info["por_periodo"],
        "dias_mes": dias,
        "factor_carga": factor_cfe_capacidad(esquema),
        "precio_dist": precio_dist,
        "costo_mxn": redondear_arriba_mxn(distribucion_kw * precio_dist),
    }


def etiqueta_criterio_distribucion(criterio_aplicado: str) -> str:
    """Etiqueta legible para UI / recibo."""
    if criterio_aplicado == "demanda_maxima":
        return "Demanda máxima (cualquier horario)"
    if criterio_aplicado == "factor_carga":
        return "DemandaCalculadaCFE"
    return criterio_aplicado
