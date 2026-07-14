"""Reglas de temporada y periodo tarifario CFE (Region Central)."""

from __future__ import annotations

from datetime import datetime, timedelta

from bess.core.console import log
print = log

def obtener_temporada(fecha):
    """Determina la temporada según la fecha (Región Central)"""
    mes = fecha.month
    dia = fecha.day
    año = fecha.year
    
    primer_domingo_abril = None
    for d in range(1, 8):
        fecha_temp = datetime(año, 4, d)
        if fecha_temp.weekday() == 6:
            primer_domingo_abril = d
            break
    
    ultimo_domingo_octubre = None
    for d in range(31, 24, -1):
        fecha_temp = datetime(año, 10, d)
        if fecha_temp.weekday() == 6:
            ultimo_domingo_octubre = d
            break
    
    if primer_domingo_abril is None:
        primer_domingo_abril = 7
    if ultimo_domingo_octubre is None:
        ultimo_domingo_octubre = 25
    
    sabado_antes_abril = primer_domingo_abril - 1
    if (mes == 2) or (mes == 3) or (mes == 4 and dia <= sabado_antes_abril):
        return 1
    if (mes == 4 and dia >= primer_domingo_abril) or (mes in [5, 6]) or (mes == 7):
        return 2
    sabado_antes_octubre = ultimo_domingo_octubre - 1
    if (mes == 8) or (mes == 9) or (mes == 10 and dia <= sabado_antes_octubre):
        return 3
    return 4


def es_festivo(fecha):
    """Determina si una fecha es festivo"""
    festivos_fijos = [(1, 1), (2, 5), (3, 21), (5, 1), (9, 16), (11, 20), (12, 25)]
    return (fecha.month, fecha.day) in festivos_fijos


def obtener_periodo_por_hora(fecha, hora_archivo):
    """Determina el periodo (Base, Intermedio, Punta) según la tabla oficial"""
    hora = hora_archivo - 1
    if hora == 24:
        hora = 0
    
    temporada = obtener_temporada(fecha)
    dia_semana = fecha.weekday()
    es_domingo = (dia_semana == 6)
    es_sabado = (dia_semana == 5)
    es_fest = es_festivo(fecha)
    
    if es_domingo or es_fest:
        if temporada == 1 or temporada == 3:
            if 0 <= hora <= 18 or hora == 23:
                return 'Base'
            else:
                return 'Intermedio'
        elif temporada == 2:
            if 0 <= hora <= 18:
                return 'Base'
            else:
                return 'Intermedio'
        else:
            if 0 <= hora <= 17:
                return 'Base'
            else:
                return 'Intermedio'
    elif es_sabado:
        if temporada == 1 or temporada == 3:
            if 0 <= hora <= 6:
                return 'Base'
            else:
                return 'Intermedio'
        elif temporada == 2:
            if hora == 0:
                return 'Intermedio'
            elif 1 <= hora <= 6:
                return 'Base'
            else:
                return 'Intermedio'
        else:
            if 0 <= hora <= 7:
                return 'Base'
            elif 8 <= hora <= 18:
                return 'Intermedio'
            elif 19 <= hora <= 20:
                return 'Punta'
            else:
                return 'Intermedio'
    else:
        if temporada == 1 or temporada == 3:
            if 0 <= hora <= 5:
                return 'Base'
            elif 6 <= hora <= 18:
                return 'Intermedio'
            elif 19 <= hora <= 21:
                return 'Punta'
            else:
                return 'Intermedio'
        elif temporada == 2:
            if hora == 0:
                return 'Intermedio'
            elif 1 <= hora <= 5:
                return 'Base'
            elif 6 <= hora <= 19:
                return 'Intermedio'
            elif 20 <= hora <= 21:
                return 'Punta'
            else:
                return 'Intermedio'
        else:
            if 0 <= hora <= 5:
                return 'Base'
            elif 6 <= hora <= 17:
                return 'Intermedio'
            elif 18 <= hora <= 21:
                return 'Punta'
            else:
                return 'Intermedio'


def obtener_periodo_por_fecha_hora(fecha_hora_str, esquema_tarifa: str = "DIST"):
    """Determina el periodo según fecha y hora exacta y esquema tarifario."""
    return periodo_por_fecha_hora(fecha_hora_str, esquema_tarifa)


def periodo_por_fecha_hora(fecha_hora_str: str, esquema_tarifa: str = "DIST") -> str:
    """Enruta al horario DIST o GDMTH."""
    from bess.config.esquema_tarifa import ESQUEMA_GDMTH, normalizar_esquema_tarifa

    esquema = normalizar_esquema_tarifa(esquema_tarifa)
    if esquema == ESQUEMA_GDMTH:
        from bess.cfe.periods_gdmth import periodo_por_fecha_hora_gdmth
        return periodo_por_fecha_hora_gdmth(fecha_hora_str)
    return _periodo_por_fecha_hora_dist(fecha_hora_str)


def _periodo_por_fecha_hora_dist(fecha_hora_str: str) -> str:
    """Horario DIST / Región Central (comportamiento histórico)."""
    dt = datetime.strptime(fecha_hora_str, '%d/%m/%Y %H:%M')
    fecha = dt.date()
    hora = dt.hour
    minuto = dt.minute

    hora_base = hora if minuto == 0 else hora + 1
    if hora_base == 24:
        hora_base = 0
        fecha = fecha + timedelta(days=1)

    return obtener_periodo_por_hora(fecha, hora_base if hora_base > 0 else 24)


def agregar_periodo(df):
    """Agrega la columna PERIODO a un dataframe"""
    periodos = []
    for idx, row in df.iterrows():
        fecha = datetime.strptime(row['FECHA'], '%d/%m/%Y')
        hora = row['HORA']
        periodo = obtener_periodo_por_hora(fecha, hora)
        periodos.append(periodo)
    df['PERIODO'] = periodos
    return df

# ========== FUNCIONES DE IDENTIFICACIÓN Y RENOMBRADO ==========
