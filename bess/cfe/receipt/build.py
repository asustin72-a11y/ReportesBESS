"""Armado del diccionario de datos del recibo."""

from __future__ import annotations

from datetime import timedelta

from bess.core.numbers import redondear_kwh, redondear_mxn_energia
from bess.cfe.energy_month import PERIODOS_ENERGIA, kwh_activo_tres_periodos
from bess.cfe.distribution import calcular_distribucion_gdmth, etiqueta_criterio_distribucion
from bess.cfe.power_factor import calcular_cargo_fp, calcular_factor_potencia_recibo
from bess.cfe.receipt.cliente import datos_cliente_recibo_prefijo
from bess.cfe.receipt.format import _fmt_fecha_cfe, _periodo_facturado_cfe
from bess.config.esquema_tarifa import ESQUEMA_DIST, ESQUEMA_GDMTH, esquema_tarifa_prefijo
from bess.cfe.report_data import obtener_demanda_kw_periodo_mes, obtener_kvarh_mes


def _tarifa_mes(tarifas, mes, *nombres):
    """Obtiene tarifa del mes probando varios nombres de fila (CSV)."""
    for nombre in nombres:
        vals = tarifas.get(nombre)
        if vals is not None:
            return float(vals.get(mes, 0) or 0)
    return 0.0


def _precio_generacion_neto(tarifas, mes, periodo_tarifa, precio_cenace, precio_transmision, precio_scnmem):
    """Tarifa de generación neta = tarifa del periodo − CENACE − Transmisión − ServiciosAuxiliares."""
    tarifa = _tarifa_mes(tarifas, mes, periodo_tarifa)
    return tarifa - precio_cenace - precio_transmision - precio_scnmem


def _celda_generacion_mem(kwh, precio_neto):
    return _celda_mem(redondear_mxn_energia(kwh * precio_neto), precio_kwh=precio_neto)


def _celda_mem(importe, precio_kwh=0.0, precio_kw=0.0):
    return {
        'precio_kwh': precio_kwh,
        'precio_kw': precio_kw,
        'importe': importe,
    }


def _mem_generacion_y_red(pp, tarifas, mes, kwh_activo):
    precio_transmision = _tarifa_mes(tarifas, mes, 'Transmision', 'Transmisión')
    precio_cenace = _tarifa_mes(tarifas, mes, 'CENACE')
    precio_scnmem = _tarifa_mes(tarifas, mes, 'ServiciosAuxiliares', 'SCnMEM')
    importe_transmision = redondear_mxn_energia(kwh_activo * precio_transmision)
    importe_cenace = redondear_mxn_energia(kwh_activo * precio_cenace)
    importe_scnmem = redondear_mxn_energia(kwh_activo * precio_scnmem)
    precio_gen_base = _precio_generacion_neto(
        tarifas, mes, 'Base', precio_cenace, precio_transmision, precio_scnmem
    )
    precio_gen_inter = _precio_generacion_neto(
        tarifas, mes, 'Intermedio', precio_cenace, precio_transmision, precio_scnmem
    )
    precio_gen_punta = _precio_generacion_neto(
        tarifas, mes, 'Punta', precio_cenace, precio_transmision, precio_scnmem
    )
    return {
        'Transmisión': _celda_mem(importe_transmision, precio_kwh=precio_transmision),
        'CENACE': _celda_mem(importe_cenace, precio_kwh=precio_cenace),
        'Generación B': _celda_generacion_mem(pp['base']['kwh'], precio_gen_base),
        'Generación I': _celda_generacion_mem(pp['intermedio']['kwh'], precio_gen_inter),
        'Generación P': _celda_generacion_mem(pp['punta']['kwh'], precio_gen_punta),
        'SCnMEM(1)': _celda_mem(importe_scnmem, precio_kwh=precio_scnmem),
    }


def _construir_recibo_dist(
    fecha,
    res_energia,
    res_cfe,
    tarifas,
    cliente,
    escenario,
    pp,
    demanda,
    kvarh,
    fp_pct,
):
    costo_cap = res_cfe['costo_mxn'] if res_cfe else 0.0
    precio_cap = res_cfe['precio_cap'] if res_cfe else 0.0
    capacidad_kw = res_cfe['capacidad_kw'] if res_cfe else 0
    mes = fecha.month
    kwh_activo = kwh_activo_tres_periodos(res_energia)

    tarifa_suministro = _tarifa_mes(tarifas, mes, 'Suministro')
    tarifa_cargo_fijo = _tarifa_mes(tarifas, mes, 'CargoFijo', 'Cargo Fijo')
    tarifa_distribucion = _tarifa_mes(tarifas, mes, 'Distribucion', 'Distribución')

    mem = {
        'Suministro': _celda_mem(tarifa_suministro),
        'Distribución': _celda_mem(tarifa_distribucion),
        **_mem_generacion_y_red(pp, tarifas, mes, kwh_activo),
        'Capacidad': _celda_mem(costo_cap, precio_kw=precio_cap),
    }
    total_mem = sum(v['importe'] for v in mem.values())

    importe_energia = res_energia['total_mxn']
    importe_cargo_fp = calcular_cargo_fp(
        fp_pct, tarifa_cargo_fijo, importe_energia, costo_cap
    )
    subtotal = importe_energia + costo_cap + tarifa_cargo_fijo + importe_cargo_fp
    iva = redondear_mxn_energia(subtotal * 0.16)
    total_pagar = redondear_mxn_energia(subtotal + iva)

    return _empaquetar_recibo(
        fecha=fecha,
        cliente=cliente,
        escenario=escenario,
        res_energia=res_energia,
        pp=pp,
        demanda=demanda,
        kvarh=kvarh,
        fp_pct=fp_pct,
        mem=mem,
        total_mem=total_mem,
        desglose={
            'cargo_fijo': tarifa_cargo_fijo,
            'energia': importe_energia,
            'capacidad': costo_cap,
            'cargo_fp': importe_cargo_fp,
            'subtotal': subtotal,
            'iva': iva,
            'total': total_pagar,
        },
        esquema_tarifa=ESQUEMA_DIST,
        capacidad_kw=capacidad_kw,
        capacidad_criterio=(
            'Demanda punta'
            if res_cfe and res_cfe['criterio_aplicado'] == 'punta'
            else 'DemandaCalculadaCFE'
        ) if res_cfe else '—',
        mostrar_capacidad_desglose=True,
        distribucion_kw=0,
        distribucion_criterio='—',
    )


def _construir_recibo_gdmth(
    fecha,
    con_bess,
    prefijo,
    res_energia,
    res_cfe,
    tarifas,
    cliente,
    escenario,
    pp,
    demanda,
    kvarh,
    fp_pct,
):
    res_dist = calcular_distribucion_gdmth(fecha, prefijo, con_bess=con_bess, tarifas=tarifas)
    costo_cap = res_cfe['costo_mxn'] if res_cfe else 0.0
    precio_cap = res_cfe['precio_cap'] if res_cfe else 0.0
    capacidad_kw = res_cfe['capacidad_kw'] if res_cfe else 0
    costo_dist = res_dist['costo_mxn'] if res_dist else 0.0
    precio_dist = res_dist['precio_dist'] if res_dist else _tarifa_mes(
        tarifas, fecha.month, 'Distribucion', 'Distribución'
    )
    dist_kw = res_dist['distribucion_kw'] if res_dist else 0

    mes = fecha.month
    kwh_activo = kwh_activo_tres_periodos(res_energia)
    tarifa_suministro = _tarifa_mes(tarifas, mes, 'Suministro')
    tarifa_cargo_fijo = _tarifa_mes(tarifas, mes, 'CargoFijo', 'Cargo Fijo')
    importe_suministro = redondear_mxn_energia(
        tarifa_cargo_fijo or tarifa_suministro
    )

    mem = {
        'Suministro': _celda_mem(importe_suministro),
        'Distribución': _celda_mem(costo_dist, precio_kw=precio_dist),
        **_mem_generacion_y_red(pp, tarifas, mes, kwh_activo),
        'Capacidad': _celda_mem(costo_cap, precio_kw=precio_cap),
    }
    total_mem = sum(v['importe'] for v in mem.values())
    importe_energia = redondear_mxn_energia(total_mem - importe_suministro)
    importe_cargo_fp = calcular_cargo_fp(
        fp_pct, importe_suministro, importe_energia, 0.0
    )
    subtotal = importe_suministro + importe_energia + importe_cargo_fp
    iva = redondear_mxn_energia(subtotal * 0.16)
    total_pagar = redondear_mxn_energia(subtotal + iva)

    return _empaquetar_recibo(
        fecha=fecha,
        cliente=cliente,
        escenario=escenario,
        res_energia=res_energia,
        pp=pp,
        demanda=demanda,
        kvarh=kvarh,
        fp_pct=fp_pct,
        mem=mem,
        total_mem=total_mem,
        desglose={
            'cargo_fijo': importe_suministro,
            'energia': importe_energia,
            'capacidad': costo_cap,
            'cargo_fp': importe_cargo_fp,
            'subtotal': subtotal,
            'iva': iva,
            'total': total_pagar,
        },
        esquema_tarifa=ESQUEMA_GDMTH,
        capacidad_kw=capacidad_kw,
        capacidad_criterio=(
            'Demanda punta'
            if res_cfe and res_cfe['criterio_aplicado'] == 'punta'
            else 'DemandaCalculadaCFE'
        ) if res_cfe else '—',
        mostrar_capacidad_desglose=False,
        distribucion_kw=dist_kw,
        distribucion_criterio=(
            etiqueta_criterio_distribucion(res_dist['criterio_aplicado'])
            if res_dist else '—'
        ),
    )


def _empaquetar_recibo(
    *,
    fecha,
    cliente,
    escenario,
    res_energia,
    pp,
    demanda,
    kvarh,
    fp_pct,
    mem,
    total_mem,
    desglose,
    esquema_tarifa,
    capacidad_kw,
    capacidad_criterio,
    mostrar_capacidad_desglose,
    distribucion_kw,
    distribucion_criterio,
):
    fecha_limite = fecha + timedelta(days=18)
    corte_partir = fecha + timedelta(days=1)
    return {
        'escenario': escenario,
        'esquema_tarifa': esquema_tarifa,
        'cliente': cliente,
        'fecha_corte': fecha,
        'periodo_facturado': _periodo_facturado_cfe(fecha),
        'fecha_limite_pago': _fmt_fecha_cfe(fecha_limite),
        'corte_partir': _fmt_fecha_cfe(corte_partir),
        'dias_mes': res_energia['dias_mes'],
        'kwh': {
            'base': redondear_kwh(pp['base']['kwh']),
            'intermedio': redondear_kwh(pp['intermedio']['kwh']),
            'punta': redondear_kwh(pp['punta']['kwh']),
            'total': redondear_kwh(res_energia['total_kwh']),
        },
        'kw': demanda or {'base': 0, 'intermedio': 0, 'punta': 0, 'kw_max': 0},
        'kvarh': kvarh,
        'factor_potencia_pct': fp_pct,
        'mem': mem,
        'total_mem': total_mem,
        'desglose': desglose,
        'capacidad_kw': capacidad_kw,
        'capacidad_criterio': capacidad_criterio,
        'distribucion_kw': distribucion_kw,
        'distribucion_criterio': distribucion_criterio,
        'mostrar_capacidad_desglose': mostrar_capacidad_desglose,
    }


def construir_datos_recibo_cfe(fecha, prefijo, con_bess, res_energia, res_cfe, tarifas):
    """Arma el diccionario de datos para el layout tipo recibo CFE."""
    cliente = datos_cliente_recibo_prefijo(prefijo)
    escenario = 'Con BESS' if con_bess else 'Sin BESS'
    pp = res_energia['por_periodo']
    demanda = obtener_demanda_kw_periodo_mes(fecha, prefijo, con_bess=con_bess)
    kvarh = obtener_kvarh_mes(fecha, prefijo)
    fp_pct = calcular_factor_potencia_recibo(res_energia, kvarh)

    esquema = esquema_tarifa_prefijo(prefijo)
    base = dict(
        fecha=fecha,
        res_energia=res_energia,
        res_cfe=res_cfe,
        tarifas=tarifas,
        cliente=cliente,
        escenario=escenario,
        pp=pp,
        demanda=demanda,
        kvarh=kvarh,
        fp_pct=fp_pct,
    )
    if esquema == ESQUEMA_GDMTH:
        return _construir_recibo_gdmth(
            **base, prefijo=prefijo, con_bess=con_bess
        )
    return _construir_recibo_dist(**base)

RECIBO_ANCHO_REF_PX = 920
RECIBO_FACTOR_ANCHO = 0.80
RECIBO_FACTOR_ALTURA = 1.20
RECIBO_LOGO_ANCHO_REF = 210
RECIBO_FACTOR_LOGO = 0.98
