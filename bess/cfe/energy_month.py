"""Costos de energía acumulados por mes o rango."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.subestaciones import ruta_energia_dia_por_prefijo
from bess.core.numbers import (
    kwh_para_calculo,
    redondear_mxn_energia,
    sumar_energia,
)
from bess.config.esquema_tarifa import esquema_tarifa_prefijo
from bess.tariffs.loader import cargar_tarifas
from bess.cfe.report_data import dias_transcurridos_mes

PERIODOS_ENERGIA = [
    ('base', 'Base'),
    ('intermedio', 'Intermedio'),
    ('punta', 'Punta'),
]

_COLUMNAS_ENERGIA_CON = {
    'base': 'BASE_REC',
    'intermedio': 'INTERMEDIO_REC',
    'punta': 'PUNTA_REC',
}
_COLUMNAS_ENERGIA_SIN = {
    'base': 'BASE_REC_SIN_BESS',
    'intermedio': 'INTERMEDIO_REC_SIN_BESS',
    'punta': 'PUNTA_REC_SIN_BESS',
}

def calcular_costo_energia_rango(fecha_inicio, fecha_fin, prefijo, con_bess=True, tarifas=None):
    """kWh por periodo en un rango de fechas × tarifa → costo MXN."""
    if tarifas is None:
        tarifas = cargar_tarifas(esquema_tarifa_prefijo(prefijo))
    columnas = _COLUMNAS_ENERGIA_CON if con_bess else _COLUMNAS_ENERGIA_SIN
    ruta_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return None
    ruta = str(ruta_p)
    df = pd.read_csv(ruta)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    mask = (df['FECHA_DT'].dt.date >= fecha_inicio) & (df['FECHA_DT'].dt.date <= fecha_fin)
    df_r = df[mask]
    if df_r.empty:
        return None

    por_periodo_raw = {}
    for clave, col in columnas.items():
        if col not in df_r.columns:
            return None
        por_periodo_raw[clave] = sumar_energia(pd.to_numeric(df_r[col], errors='coerce').fillna(0))

    mes = fecha_fin.month
    tarifa_keys = {'base': 'Base', 'intermedio': 'Intermedio', 'punta': 'Punta'}
    por_periodo = {}
    for clave, _ in PERIODOS_ENERGIA:
        kwh = kwh_para_calculo(por_periodo_raw.get(clave, 0))
        precio = tarifas.get(tarifa_keys[clave], {}).get(mes, 0)
        por_periodo[clave] = {
            'kwh': kwh,
            'precio': precio,
            'costo_mxn': redondear_mxn_energia(kwh * precio),
        }
    total_mxn = redondear_mxn_energia(sum(p['costo_mxn'] for p in por_periodo.values()))
    kwh_activo = sum(por_periodo_raw.get(clave, 0) for clave, _ in PERIODOS_ENERGIA)
    return {
        'por_periodo': por_periodo,
        'total_kwh': sum(p['kwh'] for p in por_periodo.values()),
        'kwh_activo': kwh_activo,
        'total_mxn': total_mxn,
        'dias_rango': (fecha_fin - fecha_inicio).days + 1,
    }


def calcular_costo_energia_mes(fecha, prefijo, con_bess=True, tarifas=None):
    """Acumulado del mes: kWh por periodo × tarifa → costo MXN."""
    fecha_inicio = fecha.replace(day=1)
    res = calcular_costo_energia_rango(fecha_inicio, fecha, prefijo, con_bess, tarifas)
    if res is None:
        return None
    res['dias_mes'] = dias_transcurridos_mes(fecha)
    return res


def calcular_arbitraje_desde_costos(res_sin, res_con):
    """Ahorro/arbitraje = costo sin BESS − costo con BESS (misma regla que Energía y costos)."""
    arbitraje = {}
    for clave, _ in PERIODOS_ENERGIA:
        arbitraje[clave] = (
            res_sin['por_periodo'][clave]['costo_mxn']
            - res_con['por_periodo'][clave]['costo_mxn']
        )
    return {
        'base': arbitraje['base'],
        'intermedio': arbitraje['intermedio'],
        'punta': arbitraje['punta'],
        'total': res_sin['total_mxn'] - res_con['total_mxn'],
    }


def _calcular_arbitraje_bess_periodo(carga_base, carga_intermedio, carga_punta,
                                     descarga_base, descarga_intermedio, descarga_punta,
                                     precio_base, precio_intermedio, precio_punta):
    """Arbitraje operativo BESS: (descarga − carga) × tarifa por periodo."""
    arbitraje_base = redondear_mxn_energia(
        (kwh_para_calculo(descarga_base) - kwh_para_calculo(carga_base)) * precio_base
    )
    arbitraje_intermedio = redondear_mxn_energia(
        (kwh_para_calculo(descarga_intermedio) - kwh_para_calculo(carga_intermedio)) * precio_intermedio
    )
    arbitraje_punta = redondear_mxn_energia(
        (kwh_para_calculo(descarga_punta) - kwh_para_calculo(carga_punta)) * precio_punta
    )
    arbitraje_total = redondear_mxn_energia(
        arbitraje_base + arbitraje_intermedio + arbitraje_punta
    )
    return arbitraje_base, arbitraje_intermedio, arbitraje_punta, arbitraje_total


def _html_lineas_costo_periodo(res):
    return ''.join(
        f'<div class="cap-demanda">'
        f'{res["por_periodo"][clave]["kwh"]:,} kWh {lbl} · '
        f'${res["por_periodo"][clave]["costo_mxn"]:,.2f}'
        f'</div>'
        for clave, lbl in PERIODOS_ENERGIA
    )


def _texto_tarifas_mes(tarifas, mes_num):
    partes = [
        f'{lbl} ${tarifas.get(lbl, {}).get(mes_num, 0):,.4f}'
        for _, lbl in PERIODOS_ENERGIA
    ]
    precio_cap = tarifas.get('Capacidad', {}).get(mes_num, 0)
    partes.append(f'Capacidad ${precio_cap:,.2f}')
    return ' · '.join(partes)


def html_comparacion_costo_energia(res_con, res_sin, tarifas, mes_num):
    tarifas_txt = _texto_tarifas_mes(tarifas, mes_num)
    ahorro = res_sin['total_mxn'] - res_con['total_mxn']
    pct_ahorro = (ahorro / res_sin['total_mxn'] * 100) if res_sin['total_mxn'] > 0 else 0
    diff_kwh = res_sin['total_kwh'] - res_con['total_kwh']
    clase_centro = '' if ahorro >= 0 else 'negativo'
    etiqueta_ahorro = 'Ahorro acumulado' if ahorro >= 0 else 'Incremento'
    return f"""
    <div class="cap-tarifa">
        Tarifas del mes: {tarifas_txt}<br>
        Acumulado del mes al día seleccionado · kWh × tarifa por periodo
    </div>
    <div class="capacidad-comparacion">
        <div class="cap-bloque cap-sin">
            <div class="cap-etiqueta">Sin BESS</div>
            {_html_lineas_costo_periodo(res_sin)}
            <div class="cap-costo">${res_sin['total_mxn']:,.2f}</div>
            <div class="cap-ahorro-sub">{res_sin['total_kwh']:,} kWh total</div>
        </div>
        <div class="cap-centro {clase_centro}">
            <div class="cap-ahorro-valor">${abs(ahorro):,.2f}</div>
            <div class="cap-ahorro-label">{etiqueta_ahorro} ({pct_ahorro:+.1f}%)</div>
            <div class="cap-ahorro-sub">{diff_kwh:+,} kWh vs sin BESS</div>
        </div>
        <div class="cap-bloque cap-con">
            <div class="cap-etiqueta">Con BESS</div>
            {_html_lineas_costo_periodo(res_con)}
            <div class="cap-costo">${res_con['total_mxn']:,.2f}</div>
            <div class="cap-ahorro-sub">{res_con['total_kwh']:,} kWh total</div>
        </div>
    </div>
    """


def construir_tabla_costo_energia(res_con, res_sin):
    filas = []
    for clave, lbl in PERIODOS_ENERGIA:
        pc = res_con['por_periodo'][clave]
        ps = res_sin['por_periodo'][clave]
        filas.append({
            'Periodo': lbl,
            'kWh con BESS': f"{pc['kwh']:,}",
            'kWh sin BESS': f"{ps['kwh']:,}",
            'Tarifa ($/kWh)': f"${pc['precio']:.4f}",
            'Costo con BESS (MXN)': f"${pc['costo_mxn']:,.2f}",
            'Costo sin BESS (MXN)': f"${ps['costo_mxn']:,.2f}",
            'Diferencia (MXN)': f"${ps['costo_mxn'] - pc['costo_mxn']:,.2f}",
        })
    filas.append({
        'Periodo': 'Total',
        'kWh con BESS': f"{res_con['total_kwh']:,}",
        'kWh sin BESS': f"{res_sin['total_kwh']:,}",
        'Tarifa ($/kWh)': '—',
        'Costo con BESS (MXN)': f"${res_con['total_mxn']:,.2f}",
        'Costo sin BESS (MXN)': f"${res_sin['total_mxn']:,.2f}",
        'Diferencia (MXN)': f"${res_sin['total_mxn'] - res_con['total_mxn']:,.2f}",
    })
    return pd.DataFrame(filas)


def kwh_activo_tres_periodos(res_energia):
    kwh = res_energia.get("kwh_activo")
    if kwh is not None:
        return float(kwh)
    return float(
        sum(res_energia["por_periodo"][clave]["kwh"] for clave, _ in PERIODOS_ENERGIA)
    )
