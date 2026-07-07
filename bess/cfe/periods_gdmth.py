"""Periodos horarios tarifa GDMTH (regiones Central, Noreste, Noroeste, Norte, Peninsular y Sur)."""

from __future__ import annotations

from datetime import datetime, timedelta

from bess.cfe.periods import es_festivo


def _primer_domingo_abril(año: int) -> datetime:
    for dia in range(1, 8):
        fecha = datetime(año, 4, dia)
        if fecha.weekday() == 6:
            return fecha
    return datetime(año, 4, 7)


def _ultimo_domingo_octubre(año: int) -> datetime:
    for dia in range(31, 24, -1):
        fecha = datetime(año, 10, dia)
        if fecha.weekday() == 6:
            return fecha
    return datetime(año, 10, 25)


def obtener_temporada_gdmth(fecha) -> int:
    """1 = verano (abr–oct); 2 = invierno (oct–abr)."""
    if hasattr(fecha, "date"):
        fecha = fecha.date()
    año = fecha.year
    inicio_verano = _primer_domingo_abril(año).date()
    ultimo_dom_oct = _ultimo_domingo_octubre(año).date()
    fin_verano = ultimo_dom_oct - timedelta(days=1)
    if inicio_verano <= fecha <= fin_verano:
        return 1
    return 2


def _en_rango(hora: int, inicio: int, fin: int) -> bool:
    """hora del reloj (0–23) dentro de [inicio, fin)."""
    return inicio <= hora < fin


def obtener_periodo_gdmth_por_hora(fecha, hora: int) -> str:
    """Clasifica la hora CFE (0–23) según tablas GDMTH."""
    temporada = obtener_temporada_gdmth(fecha)
    dia_semana = fecha.weekday()
    es_domingo_fest = dia_semana == 6 or es_festivo(fecha)
    es_sabado = dia_semana == 5 and not es_festivo(fecha)

    if es_domingo_fest:
        if temporada == 1:
            if _en_rango(hora, 0, 19):
                return "Base"
            return "Intermedio"
        if _en_rango(hora, 0, 18):
            return "Base"
        return "Intermedio"

    if es_sabado:
        if temporada == 1:
            if _en_rango(hora, 0, 7):
                return "Base"
            return "Intermedio"
        if _en_rango(hora, 0, 8):
            return "Base"
        if _en_rango(hora, 19, 21):
            return "Punta"
        return "Intermedio"

    # Lunes a viernes
    if temporada == 1:
        if _en_rango(hora, 0, 6):
            return "Base"
        if _en_rango(hora, 20, 22):
            return "Punta"
        if _en_rango(hora, 6, 20) or _en_rango(hora, 22, 24):
            return "Intermedio"
        return "Intermedio"

    if _en_rango(hora, 0, 6):
        return "Base"
    if _en_rango(hora, 18, 22):
        return "Punta"
    if _en_rango(hora, 6, 18) or _en_rango(hora, 22, 24):
        return "Intermedio"
    return "Intermedio"


def periodo_por_fecha_hora_gdmth(fecha_hora_str: str) -> str:
    """Misma convención de marcas de 5 min que DIST (obtener_periodo_por_fecha_hora)."""
    dt = datetime.strptime(fecha_hora_str, "%d/%m/%Y %H:%M")
    fecha = dt.date()
    hora = dt.hour
    minuto = dt.minute

    hora_base = hora if minuto == 0 else hora + 1
    if hora_base == 24:
        hora_base = 0
        fecha = fecha + timedelta(days=1)

    hora_archivo = hora_base if hora_base > 0 else 24
    hora_cfe = hora_archivo - 1
    if hora_cfe < 0:
        hora_cfe = 0
    return obtener_periodo_gdmth_por_hora(fecha, hora_cfe)
