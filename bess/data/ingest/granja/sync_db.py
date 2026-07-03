"""Sincroniza suma de generación granja (20 MEGA) hacia SQLite."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bess.config.paths import RUTA_BD_PERFILES
from bess.core.console import log as print
from bess.data.ingest.granja.consolidar import acumular_kw, totales_a_registros_bess
from bess.data.ingest.granja.farm_client import FarmClient, kw_desde_perfil
from bess.data.ingest.ion import db
from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError
from bess.data.ingest.iusasol.gaps import persistir_slots_medianoche_bd
from bess.data.ingest.iusasol.sync_db import DIAS_SOLAPAMIENTO_API, fecha_fin_api
from bess.data.sync_cursor import inicio_api_con_solapamiento, punto_sync_api, registrar_exito_sync

FECHA_INICIO_DEFAULT = "2026-05-01"
LOTE = 500
ZONA = ZoneInfo("America/Mexico_City")
CANTIDAD_MEGA_DEFAULT = 20


def _rango_fechas(desde: date, hasta: date) -> list[date]:
    dias: list[date] = []
    cursor = desde
    while cursor <= hasta:
        dias.append(cursor)
        cursor += timedelta(days=1)
    return dias


def _calcular_rango(
    ruta_bd: Path,
    medidor_id: str,
    desde: str | None,
    hasta: str | None,
) -> tuple[date, date] | None:
    fin_txt = (hasta or fecha_fin_api())[:10]
    fin = date.fromisoformat(fin_txt)

    if desde:
        inicio = date.fromisoformat(desde[:10])
        return (inicio, fin) if inicio <= fin else None

    cursor = punto_sync_api(medidor_id, ruta_bd)
    if cursor.es_redescarga and cursor.desde_forzado:
        inicio = cursor.desde_forzado.date()
        return (inicio, fin) if inicio <= fin else None
    if cursor.ultima_incremental:
        inicio = date.fromisoformat(inicio_api_con_solapamiento(cursor.ultima_incremental))
        return (inicio, fin) if inicio <= fin else None

    db.init_db(ruta_bd)
    with db.conectar_bd(ruta_bd) as conn:
        row = conn.execute(
            """
            SELECT MAX(fecha) AS mx FROM perfil_carga
            WHERE medidor_id = ? AND substr(fecha, 1, 10) <= ?
            """,
            (medidor_id, fin_txt),
        ).fetchone()
        ultima_txt = row["mx"] if row else None

    if ultima_txt:
        ultima = datetime.fromisoformat(ultima_txt[:19])
        inicio = ultima.date() - timedelta(days=DIAS_SOLAPAMIENTO_API)
        inicio_min = date.fromisoformat(FECHA_INICIO_DEFAULT)
        if inicio < inicio_min:
            inicio = inicio_min
    else:
        inicio = date.fromisoformat(FECHA_INICIO_DEFAULT)

    if inicio > fin:
        return None
    return inicio, fin


def sincronizar_granja_iusa2(
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    medidor_id: str = db.MEDIDOR_GRANJA_IUSA2,
    desde: str | None = None,
    hasta: str | None = None,
    farm_idcode: str | None = None,
    cantidad_medidores: int = CANTIDAD_MEGA_DEFAULT,
    pausa_seg: float = 0.15,
    client: IusasolClient | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    db.init_db(ruta_bd)
    rango = _calcular_rango(ruta_bd, medidor_id, desde, hasta)
    if rango is None:
        return {
            "medidor": medidor_id,
            "desde": None,
            "hasta": hasta or fecha_fin_api(),
            "leidos": 0,
            "insertados": 0,
            "actualizados": 0,
            "mensaje": "Sin rango pendiente (BD al día).",
        }

    inicio, fin = rango
    dias = _rango_fechas(inicio, fin)

    if not quiet:
        print(
            f"  Granja IUSA2: {cantidad_medidores} MEGA | "
            f"{len(dias)} día(s) {inicio} -> {fin}"
        )

    cfg = cargar_config_iusasol()
    api = client or IusasolClient(cfg)
    api.autenticar()
    farm_api = FarmClient(api)

    granjas = farm_api.listar_granjas()
    if not granjas:
        raise IusasolError("No hay granjas en Reports/Farms")

    if farm_idcode:
        granja = next((g for g in granjas if g.get("idcode") == farm_idcode), None)
        if not granja:
            raise IusasolError(f"Granja {farm_idcode!r} no encontrada")
    else:
        granja = granjas[0]

    farm_id = str(granja["idcode"])
    medidores = farm_api.listar_medidores(farm_id)[:cantidad_medidores]
    if not medidores:
        raise IusasolError("La granja no tiene medidores")

    totales: dict[str, float] = {}
    peticiones = 0

    for dia in dias:
        for medidor in medidores:
            meter_id = str(medidor["idcode"])
            perfiles = farm_api.perfil_medidor_dia(meter_id, dia)
            acumular_kw(totales, kw_desde_perfil(perfiles))
            peticiones += 1
            if pausa_seg > 0:
                time.sleep(pausa_seg)

    registros = totales_a_registros_bess(totales)
    insertados = 0
    actualizados = 0

    with db.conectar_bd(ruta_bd) as conn:
        for i in range(0, len(registros), LOTE):
            lote = registros[i : i + LOTE]
            resultado = db.upsert_registros(conn, medidor_id, lote, fuente="farm_api")
            insertados += resultado.insertados
            actualizados += resultado.actualizados
        if registros:
            db.actualizar_sync_state(conn, medidor_id, registros[-1]["fecha"])
        conn.commit()

    if registros:
        registrar_exito_sync(medidor_id, ruta_bd)

    medianoche_persistidos = persistir_slots_medianoche_bd(medidor_id, ruta_bd)
    if medianoche_persistidos and not quiet:
        print(f"  {medidor_id}: {medianoche_persistidos} slot(s) 00:00 rellenados en BD")

    return {
        "medidor": medidor_id,
        "desde": inicio.isoformat(),
        "hasta": fin.isoformat(),
        "leidos": len(registros),
        "insertados": insertados,
        "actualizados": actualizados,
        "medidores_mega": len(medidores),
        "peticiones_api": peticiones,
        "mensaje": "OK",
    }
