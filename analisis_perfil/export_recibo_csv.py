"""Export CSV estilo recibo: energía, precios e importes del resumen."""

from __future__ import annotations

import csv
import io
from typing import Any


def _filas_escalones(pago: dict, etiquetas: tuple | list | None) -> list[list[Any]]:
    esc = pago.get("escalones") or {}
    filas = []
    if etiquetas:
        pares = list(etiquetas)
    else:
        pares = [(k, str(k).capitalize()) for k in esc]
    for clave, nombre in pares:
        e = esc.get(clave) or {}
        filas.append(
            [
                nombre,
                round(float(e.get("kwh", 0) or 0), 3),
                round(float(e.get("importe", 0) or 0), 2),
            ]
        )
    return filas


def _filas_periodos(valores: dict) -> list[list[Any]]:
    por = valores.get("por_periodo") or {}
    out = []
    for periodo, kwh in por.items():
        out.append([periodo, round(float(kwh), 3), ""])
    return out


def generar_csv_recibo(resumen: dict) -> bytes:
    """CSV legible en Excel con desglose de energía y costos del resumen."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")

    w.writerow(["IUSASOL — Análisis de Perfil (recibo-ready)"])
    w.writerow([])
    w.writerow(["Periodo inicio", resumen.get("fecha_min") or ""])
    w.writerow(["Periodo fin", resumen.get("fecha_max") or ""])
    w.writerow(["Días", resumen.get("n_dias") or ""])
    w.writerow(["Tarifa", resumen.get("esquema") or ""])
    w.writerow(["Servicio", resumen.get("servicio") or ""])
    if resumen.get("region"):
        w.writerow(["Región", resumen.get("region")])
    w.writerow([])

    costo = resumen.get("costo_energia")
    ahorro = resumen.get("ahorro_energia")
    bloque = costo or ahorro

    if bloque:
        w.writerow(["Método precios", bloque.get("metodo") or ""])
        w.writerow(["Vigencia / etiqueta", bloque.get("fecha_tarifa") or ""])
        precios = bloque.get("precios") or {}
        etiq = tuple(bloque.get("etiquetas_escalones") or ())
        w.writerow([])
        w.writerow(["Concepto precio", "MXN/kWh"])
        if etiq:
            for clave, nombre in etiq:
                if clave in precios:
                    w.writerow([nombre, precios[clave]])
        else:
            for k, v in precios.items():
                w.writerow([k, v])
        w.writerow([])

    if costo:
        cons = costo.get("consumo") or {}
        w.writerow(["— Costo consumo —"])
        w.writerow(["Escalón / Periodo", "kWh", "Importe MXN"])
        filas = _filas_escalones(cons, etiq if bloque else None)
        if not filas and resumen.get("horaria"):
            # horaria: poner periodos del flujo REC si existen
            flujos = (resumen.get("flujos") or {}).get("REC") or {}
            filas = _filas_periodos(flujos)
            # rellenar importes desde escalones si vienen como Base/Intermedio/Punta
            if not filas:
                filas = _filas_escalones(cons, None)
        for f in filas:
            w.writerow(f)
        w.writerow(
            [
                "TOTAL",
                round(float(cons.get("kwh", 0) or 0), 3),
                round(float(cons.get("importe", 0) or 0), 2),
            ]
        )
        w.writerow([])
        dac = costo.get("dac") or {}
        if dac:
            w.writerow(
                [
                    "Promedio mensual equiv. kWh",
                    dac.get("promedio_mensual_kwh", ""),
                ]
            )
            w.writerow(["Límite DAC kWh/mes", dac.get("limite_kwh_mes", "")])
            w.writerow(
                ["Supera DAC", "Sí" if dac.get("supera_dac") else "No"]
            )
            w.writerow([])

    if ahorro:
        etiq_a = tuple(ahorro.get("etiquetas_escalones") or ())
        for etiqueta, clave in (
            ("Neteo", "neteo"),
            (ahorro.get("etiqueta_real") or "Consumo real", "real"),
        ):
            pago = ahorro.get(clave) or {}
            w.writerow([f"— {etiqueta} —"])
            w.writerow(["Escalón / Periodo", "kWh", "Importe MXN"])
            for f in _filas_escalones(pago, etiq_a):
                w.writerow(f)
            w.writerow(
                [
                    "TOTAL",
                    round(float(pago.get("kwh", 0) or 0), 3),
                    round(float(pago.get("importe", 0) or 0), 2),
                ]
            )
            w.writerow([])
        w.writerow(
            [
                "Ahorro (Real − Neteo) MXN",
                "",
                round(float(ahorro.get("ahorro", 0) or 0), 2),
            ]
        )
        w.writerow([])
        dac = ahorro.get("dac") or {}
        if dac:
            w.writerow(
                [
                    "Promedio mensual equiv. kWh",
                    dac.get("promedio_mensual_kwh", ""),
                ]
            )
            w.writerow(["Límite DAC kWh/mes", dac.get("limite_kwh_mes", "")])
            w.writerow(
                ["Supera DAC", "Sí" if dac.get("supera_dac") else "No"]
            )
            w.writerow([])

    # Energía sin costo (resumen simple)
    if not costo and not ahorro:
        w.writerow(["— Energía —"])
        w.writerow(["Concepto", "kWh", ""])
        if resumen.get("layout") in ("bidireccional_3col", "neteo"):
            cols = resumen.get("columnas") or {}
            for bloque_c in cols.values():
                for renglon in bloque_c.get("renglones") or []:
                    vals = renglon.get("valores") or {}
                    w.writerow(
                        [
                            renglon.get("etiqueta") or "",
                            round(float(vals.get("total", 0) or 0), 3),
                            "",
                        ]
                    )
        else:
            for clave, vals in (resumen.get("flujos") or {}).items():
                etiq_f = (resumen.get("etiquetas") or {}).get(clave, clave)
                w.writerow(
                    [etiq_f, round(float(vals.get("total", 0) or 0), 3), ""]
                )

    # UTF-8 BOM para Excel
    return ("\ufeff" + buf.getvalue()).encode("utf-8")
