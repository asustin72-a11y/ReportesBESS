"""Constantes del recibo simulado."""

MESES_CFE = (
    'ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN',
    'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC',
)

DATOS_CLIENTE_RECIBO = {
    'ION_Testigo_IUSA1': {
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
    'Banco_1': {
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
        'no_medidor': 'Banco 1',
        'carga_conectada_kw': None,
        'demanda_contratada_kw': None,
    },
    'ION_TESTIGO_IUSA2': {
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
        'no_medidor': 'ION IUSA 2',
        'carga_conectada_kw': None,
        'demanda_contratada_kw': None,
    },
    'Consumo_Aragon': {
        'razon_social': 'INDUSTRIAS UNIDAS SA DE CV',
        'direccion': ('—',),
        'no_servicio': '—',
        'cuenta': '—',
        'rmu': '—',
        'tarifa': 'GDMTH',
        'multiplicador': '—',
        'no_hilos': '3',
        'no_medidor': 'Consumo Aragón',
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
