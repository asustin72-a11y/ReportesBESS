"""Marca cincominutal → día y hora CFE que cierra.

La misma regla que ``bess.cfe.periods.fecha_y_hora_archivo``.
La marca en punto cierra la hora anterior. Las 23:05–23:55 y las 00:00
del día siguiente son la hora 23 del día en que empezó esa hora: no se
adelanta el calendario, porque un festivo o un domingo cambia el periodo.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


def fecha_y_hora_cfe(dt: datetime) -> tuple[date, int]:
    """Día dueño de la hora y hora de reloj 0–23."""
    if dt.hour == 0 and dt.minute == 0:
        return (dt - timedelta(days=1)).date(), 23
    if dt.minute == 0:
        return dt.date(), dt.hour - 1
    return dt.date(), dt.hour
