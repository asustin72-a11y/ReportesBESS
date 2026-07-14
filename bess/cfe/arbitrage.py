"""Arbitraje diario BESS (ahorro por periodo tarifario)."""



from __future__ import annotations



from datetime import datetime



from bess.config.paths import ruta_energia_bess_por_dia

from bess.core.numbers import a_num, kwh_para_calculo, redondear_mxn_energia

from bess.cfe.daily_data import energia_diaria_tiene_sin_bess, fila_por_fecha_csv

from bess.cfe.energy import calcular_costo_energia_dia

from bess.cfe.energy_month import (

    _calcular_arbitraje_bess_periodo,

    calcular_arbitraje_desde_costos,

    calcular_costo_energia_rango,

)

from bess.config.esquema_tarifa import esquema_tarifa_prefijo
from bess.tariffs.loader import cargar_tarifas





def calcular_arbitraje_rango(

    fecha_inicio,

    fecha_fin,

    prefijo: str,

    *,

    carga_base: float,

    carga_intermedio: float,

    carga_punta: float,

    descarga_base: float,

    descarga_intermedio: float,

    descarga_punta: float,

    tarifas: dict | None = None,

) -> dict[str, float]:

    """

    Arbitraje en un rango de fechas.

    Con columnas sin BESS en ENERGIA_*_POR_DIA: costo sin − costo con (IUSA 1 e IUSA 2).

    Sin esas columnas: (descarga − carga) × tarifa desde ENERGIA_BESS_POR_DIA.

    """

    if tarifas is None:

        tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))

    mes = fecha_fin.month

    precio_base = tarifas["Base"].get(mes, 0)

    precio_intermedio = tarifas["Intermedio"].get(mes, 0)

    precio_punta = tarifas["Punta"].get(mes, 0)



    if energia_diaria_tiene_sin_bess(prefijo):

        res_con = calcular_costo_energia_rango(

            fecha_inicio, fecha_fin, prefijo, con_bess=True, tarifas=tarifas

        )

        res_sin = calcular_costo_energia_rango(

            fecha_inicio, fecha_fin, prefijo, con_bess=False, tarifas=tarifas

        )

        if res_con is not None and res_sin is not None:

            return calcular_arbitraje_desde_costos(res_sin, res_con)



    base, intermedio, punta, total = _calcular_arbitraje_bess_periodo(

        carga_base,

        carga_intermedio,

        carga_punta,

        descarga_base,

        descarga_intermedio,

        descarga_punta,

        precio_base,

        precio_intermedio,

        precio_punta,

    )

    return {

        "base": base,

        "intermedio": intermedio,

        "punta": punta,

        "total": total,

    }





def _arbitraje_desde_fila_bess(fila, mes: int, tarifas: dict) -> dict[str, float]:

    carga_base = a_num(fila.get("BASE_REC", 0))

    carga_intermedio = a_num(fila.get("INTERMEDIO_REC", 0))

    carga_punta = a_num(fila.get("PUNTA_REC", 0))

    descarga_base = a_num(fila.get("BASE_ENT", 0))

    descarga_intermedio = a_num(fila.get("INTERMEDIO_ENT", 0))

    descarga_punta = a_num(fila.get("PUNTA_ENT", 0))



    precio_base = tarifas["Base"].get(mes, 0)

    precio_intermedio = tarifas["Intermedio"].get(mes, 0)

    precio_punta = tarifas["Punta"].get(mes, 0)



    arbitraje_base = redondear_mxn_energia(

        (kwh_para_calculo(descarga_base) - kwh_para_calculo(carga_base)) * precio_base

    )

    arbitraje_intermedio = redondear_mxn_energia(

        (kwh_para_calculo(descarga_intermedio) - kwh_para_calculo(carga_intermedio))

        * precio_intermedio

    )

    arbitraje_punta = redondear_mxn_energia(

        (kwh_para_calculo(descarga_punta) - kwh_para_calculo(carga_punta)) * precio_punta

    )

    return {

        "base": arbitraje_base,

        "intermedio": arbitraje_intermedio,

        "punta": arbitraje_punta,

        "total": redondear_mxn_energia(arbitraje_base + arbitraje_intermedio + arbitraje_punta),

    }





def calcular_arbitraje_dia(fecha_str: str, prefijo: str, tarifas: dict | None = None):

    """

    Arbitraje del día seleccionado.

    Con sin BESS en ENERGIA_*_POR_DIA: costo sin − costo con por periodo.

    Si no: (descarga − carga) × tarifa desde ENERGIA_BESS_POR_DIA.

    """

    if tarifas is None:

        tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))

    mes = datetime.strptime(fecha_str, "%d/%m/%Y").month



    if energia_diaria_tiene_sin_bess(prefijo):

        res_con = calcular_costo_energia_dia(fecha_str, prefijo, con_bess=True, tarifas=tarifas)

        res_sin = calcular_costo_energia_dia(fecha_str, prefijo, con_bess=False, tarifas=tarifas)

        if res_con is not None and res_sin is not None:

            return {

                "base": res_sin["por_periodo"]["base"]["costo_mxn"]

                - res_con["por_periodo"]["base"]["costo_mxn"],

                "intermedio": res_sin["por_periodo"]["intermedio"]["costo_mxn"]

                - res_con["por_periodo"]["intermedio"]["costo_mxn"],

                "punta": res_sin["por_periodo"]["punta"]["costo_mxn"]

                - res_con["por_periodo"]["punta"]["costo_mxn"],

                "total": res_sin["total_mxn"] - res_con["total_mxn"],

            }



    fila = fila_por_fecha_csv(str(ruta_energia_bess_por_dia(prefijo)), fecha_str)

    if fila is None:

        return {"base": 0.0, "intermedio": 0.0, "punta": 0.0, "total": 0.0}



    return _arbitraje_desde_fila_bess(fila, mes, tarifas)


