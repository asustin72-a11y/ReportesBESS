"""Suma de perfiles kW de varios medidores MEGA por timestamp."""

from __future__ import annotations

from collections import defaultdict


def acumular_kw(
    totales: dict[str, float],
    filas: list[tuple[str, float]],
) -> None:
    for fecha, kw in filas:
        totales[fecha] = totales.get(fecha, 0.0) + kw


def totales_a_registros_bess(totales: dict[str, float]) -> list[dict]:
    """
    Convierte suma kW por timestamp a registros perfil_carga / CSV BESS.
    kwh_rec almacena la generación cincuminutal sumada (kW del intervalo).
    """
    registros: list[dict] = []
    for fecha in sorted(totales):
        kw = totales[fecha]
        registros.append({
            "fecha": fecha,
            "kwh_rec": kw,
            "kwh_ent": 0.0,
            "kvarh_q1": 0.0,
            "kvarh_q2": 0.0,
            "kvarh_q3": 0.0,
            "kvarh_q4": 0.0,
        })
    return registros


def sumar_filas_por_medidor(
    lecturas_por_medidor: list[list[tuple[str, float]]],
) -> dict[str, float]:
    totales: dict[str, float] = defaultdict(float)
    for filas in lecturas_por_medidor:
        acumular_kw(totales, filas)
    return dict(totales)
