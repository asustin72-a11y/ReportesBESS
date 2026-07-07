"""Resolución de datos de cliente/receptor del recibo por subestación."""

from __future__ import annotations

from bess.cfe.receipt.constants import DATOS_CLIENTE_RECIBO
from bess.config.esquema_tarifa import normalizar_esquema_tarifa
from bess.config.subestaciones import subestacion_por_prefijo
from bess.data.cliente_recibo_db import (
    direccion_como_tupla,
    leer_cliente_recibo_subestacion,
)
from bess.data.ingest.medidor_ids import MEDIDOR_ION, medidor_id_canonico


def _dict_desde_bd(fila: dict[str, object], esquema_tarifa_id: str) -> dict:
    tarifa = (str(fila.get("tarifa_etiqueta") or "").strip().upper()
              or normalizar_esquema_tarifa(esquema_tarifa_id))
    multiplicador = str(fila.get("multiplicador") or "").strip() or "—"
    return {
        "razon_social": str(fila.get("razon_social") or "").strip() or "—",
        "direccion": direccion_como_tupla(str(fila.get("direccion") or "")),
        "no_servicio": str(fila.get("no_servicio") or "").strip() or "—",
        "cuenta": str(fila.get("cuenta") or "").strip() or "—",
        "rmu": str(fila.get("rmu") or "").strip() or "—",
        "tarifa": tarifa,
        "multiplicador": multiplicador,
        "no_hilos": str(fila.get("no_hilos") or "3").strip() or "3",
        "no_medidor": str(fila.get("no_medidor") or "").strip() or "—",
        "carga_conectada_kw": fila.get("carga_conectada_kw"),
        "demanda_contratada_kw": fila.get("demanda_contratada_kw"),
    }


def _dict_legacy_prefijo(prefijo: str) -> dict | None:
    medidor_id = medidor_id_canonico(prefijo)
    return DATOS_CLIENTE_RECIBO.get(medidor_id)


def datos_cliente_recibo_prefijo(prefijo: str) -> dict:
    """
    Datos fiscales del receptor para el recibo simulado.

    Fuente: `catalog_cliente_recibo` por subestación; fallback a constantes legacy.
    """
    sub = subestacion_por_prefijo(prefijo)
    if sub:
        fila = leer_cliente_recibo_subestacion(sub.id)
        if fila and (fila.get("razon_social") or fila.get("no_servicio")):
            return _dict_desde_bd(fila, sub.esquema_tarifa_id)

    legacy = _dict_legacy_prefijo(prefijo)
    if legacy:
        return legacy

    return DATOS_CLIENTE_RECIBO[MEDIDOR_ION]
