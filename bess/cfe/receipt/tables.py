"""Tablas de desglose del recibo."""

from __future__ import annotations

import pandas as pd

from bess.cfe.energy_month import PERIODOS_ENERGIA

def construir_tabla_recibo_energia(res_energia):
    """Desglose de energía para un escenario (con o sin BESS)."""
    filas = []
    for clave, lbl in PERIODOS_ENERGIA:
        p = res_energia['por_periodo'][clave]
        filas.append({
            'Concepto': f'Energía {lbl}',
            'kWh': f"{p['kwh']:,}",
            'Tarifa ($/kWh)': f"${p['precio']:.4f}",
            'Importe (MXN)': f"${p['costo_mxn']:,.2f}",
        })
    filas.append({
        'Concepto': 'Subtotal energía',
        'kWh': f"{res_energia['total_kwh']:,}",
        'Tarifa ($/kWh)': '—',
        'Importe (MXN)': f"${res_energia['total_mxn']:,.2f}",
    })
    return pd.DataFrame(filas)


def construir_tabla_recibo_completo(res_energia, res_cfe):
    """Tabla unificada del recibo: energía + capacidad CFE + total."""
    filas = construir_tabla_recibo_energia(res_energia).to_dict('records')
    if res_cfe is not None:
        lbl_criterio = (
            'Demanda punta'
            if res_cfe['criterio_aplicado'] == 'punta'
            else 'DemandaCalculadaCFE'
        )
        filas.append({
            'Concepto': 'Capacidad CFE',
            'kWh': (
                f"{res_cfe['capacidad_kw']:,} kW · {lbl_criterio} · "
                f"${res_cfe['precio_cap']:,.2f}/kW"
            ),
            'Tarifa ($/kWh)': '—',
            'Importe (MXN)': f"${res_cfe['costo_mxn']:,.2f}",
        })
    total = res_energia['total_mxn'] + (res_cfe['costo_mxn'] if res_cfe else 0)
    filas.append({
        'Concepto': 'Total recibo',
        'kWh': '—',
        'Tarifa ($/kWh)': '—',
        'Importe (MXN)': f"${total:,.2f}",
    })
    return pd.DataFrame(filas), total

MESES_CFE = (
    'ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN',
    'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC',
)

DATOS_CLIENTE_RECIBO = {
    'ION': {
        'razon_social': 'INDUSTRIAS UNIDAS SA DE CV',
        'direccion': (
            'CARR PANAMERICANA MEXICO QUERE',
            'JOCOTITLAN C FZA',
            'C.P.50700',
            'JOCOTITLAN,MEX.',
        ),
        'no_servicio': '306140811981',
        'cuenta': '84DG41H108350020',
        'rmu': '50700 14-07-31 IUN -390731 001 CFE',
        'tarifa': 'DIST',
        'multiplicador': '44000',
        'no_hilos': '3',
        'no_medidor': '764DXX',
        'carga_conectada_kw': 31000,
        'demanda_contratada_kw': 31000,
    },
    'BANCO': {
        'razon_social': 'INDUSTRIAS UNIDAS SA DE CV',
        'direccion': (
            'CARR PANAMERICANA MEXICO QUERE',
            'JOCOTITLAN C FZA',
            'C.P.50700',
            'JOCOTITLAN,MEX.',
        ),
        'no_servicio': '—',
        'cuenta': '—',
        'rmu': '—',
        'tarifa': 'DIST',
        'multiplicador': '—',
        'no_hilos': '3',
        'no_medidor': 'BANCO',
        'carga_conectada_kw': None,
        'demanda_contratada_kw': None,
    },
}

_UNIDADES_ES = (
    ('millones', 1_000_000),
    ('mil', 1_000),
    ('', 1),
)
_DECENAS_ES = (
    'diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete',
    'dieciocho', 'diecinueve',
)
_UNIDADES_LETRAS = (
    '', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve',
)
_DECENAS_LETRAS = (
    '', '', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta',
    'ochenta', 'noventa',
)
_CENTENAS_LETRAS = (
    '', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos',
    'seiscientos', 'setecientos', 'ochocientos', 'novecientos',
)
