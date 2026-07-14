"""Formato de fechas y montos del recibo."""

from __future__ import annotations

from bess.core.numbers import a_num as _a_num
from bess.cfe.receipt.constants import MESES_CFE, _CENTENAS_LETRAS, _DECENAS_ES, _DECENAS_LETRAS, _UNIDADES_ES, _UNIDADES_LETRAS

def _fmt_fecha_cfe(fecha):
    return f'{fecha.day:02d} {MESES_CFE[fecha.month - 1]} {fecha.year % 100:02d}'


def _periodo_facturado_cfe(fecha):
    inicio = fecha.replace(day=1)
    return f'{_fmt_fecha_cfe(inicio)}-{_fmt_fecha_cfe(fecha)}'


def _fmt_mxn_entero(val):
    return f'${int(round(_a_num(val))):,}'


def _fmt_mxn_decimal(val):
    return f'${_a_num(val):,.2f}'


def _fmt_cargo_fp_recibo(val):
    """Penalización positiva; bonificación negativa en el desglose."""
    monto = _a_num(val)
    if monto < 0:
        return f'-${abs(monto):,.2f}'
    return _fmt_mxn_decimal(monto)


def _numero_menor_1000_a_letras(n):
    n = int(n)
    if n == 0:
        return ''
    if n == 100:
        return 'cien'
    if n < 10:
        return _UNIDADES_LETRAS[n]
    if n < 20:
        return _DECENAS_ES[n - 10]
    if n < 100:
        d, u = divmod(n, 10)
        if u == 0:
            return _DECENAS_LETRAS[d]
        if d == 2:
            return f'veinti{_UNIDADES_LETRAS[u]}'
        return f'{_DECENAS_LETRAS[d]} y {_UNIDADES_LETRAS[u]}'
    c, resto = divmod(n, 100)
    pref = _CENTENAS_LETRAS[c]
    if resto == 0:
        return pref
    return f'{pref} {_numero_menor_1000_a_letras(resto)}'


def _entero_a_letras_es(n):
    n = int(n)
    if n == 0:
        return 'cero'
    partes = []
    for nombre, valor in _UNIDADES_ES:
        if n >= valor:
            cant = n // valor
            n %= valor
            texto = _numero_menor_1000_a_letras(cant)
            if nombre == 'millones' and cant == 1:
                texto = 'un millón'
            elif nombre == 'millones':
                texto = f'{texto} millones'
            elif nombre == 'mil' and cant == 1:
                texto = 'mil'
            elif nombre == 'mil':
                texto = f'{texto} mil'
            partes.append(texto)
    return ' '.join(partes)


def _monto_a_letras_mxn(val):
    entero = int(round(_a_num(val)))
    letras = _entero_a_letras_es(entero).upper()
    return f'({letras} PESOS M.N.)'
