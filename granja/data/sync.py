"""Sincronización MEGA vía API Farm → SQLite (sin CSV)."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from filelock import FileLock, Timeout

from bess.config.paths import DIRECTORIO_BASE, RUTA_BD_PERFILES
from bess.core.console import log as print
from bess.data.ingest.granja.farm_client import FarmClient, kw_desde_perfil
from bess.data.ingest.ion import db
from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError
from bess.data.ingest.iusasol.sync_db import DIAS_SOLAPAMIENTO_API, _ahora_local, fecha_fin_api
from bess.data.sync_cursor import inicio_api_con_solapamiento, punto_sync_api, registrar_exito_sync

from granja.config import FECHA_INICIO_SYNC
from granja.config.meters import NOMBRES_MEGA
from granja.data.catalogo import asegurar_megas_en_catalogo
from granja.data.farm_map import mapear_megas_farm, resumen_mapeo

LOTE = 500
ZONA = ZoneInfo("America/Mexico_City")
RUTA_LOCK_SYNC = DIRECTORIO_BASE / ".granja_sync.lock"
MENSAJE_SYNC_OCUPADO = (
    "Otra sincronización de Granja sigue en curso. Intente de nuevo en unos minutos."
)

ProgressCallback = Callable[[int, int, str], None]


def _tiene_perfil(medidor_id: str, ruta_bd: Path) -> bool:
    db.init_db(ruta_bd)
    with db.conectar_bd(ruta_bd) as conn:
        row = conn.execute(
            "SELECT 1 FROM perfil_carga WHERE medidor_id = ? LIMIT 1",
            (medidor_id,),
        ).fetchone()
    return row is not None


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

    if _tiene_perfil(medidor_id, ruta_bd):
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
            inicio_min = date.fromisoformat(FECHA_INICIO_SYNC)
            if inicio < inicio_min:
                inicio = inicio_min
        else:
            inicio = date.fromisoformat(FECHA_INICIO_SYNC)
    else:
        inicio = date.fromisoformat(FECHA_INICIO_SYNC)

    if inicio > fin:
        return None
    return inicio, fin


def _registros_desde_perfil(filas: list[tuple[str, float]]) -> list[dict[str, Any]]:
    """
    Canal 0 de Farm/Meter/Profiles → kwh_rec.

    El valor del canal, sumado en el día, es la energía (kWh). Misma convención
    que BESS granja: potencia media del intervalo ≈ kWh_intervalo × 12.
    """
    ahora_txt = _ahora_local().strftime("%Y-%m-%d %H:%M:%S")
    registros: list[dict[str, Any]] = []
    for fecha, valor in filas:
        if fecha > ahora_txt:
            continue
        registros.append({
            "fecha": fecha if len(fecha) > 16 else f"{fecha}:00",
            "kwh_rec": float(valor),
            "kwh_ent": 0.0,
            "kvarh_q1": 0.0,
            "kvarh_q2": 0.0,
            "kvarh_q3": 0.0,
            "kvarh_q4": 0.0,
        })
    return registros


def purgar_perfiles_megas(
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
) -> int:
    """Borra perfiles MEGA (fuente farm_api) para forzar re-sync limpio."""
    db.init_db(ruta_bd)
    placeholders = ",".join("?" * len(NOMBRES_MEGA))
    with db.conectar_bd(ruta_bd) as conn:
        cur = conn.execute(
            f"""
            DELETE FROM perfil_carga
            WHERE fuente = 'farm_api'
              AND medidor_id IN ({placeholders})
            """,
            list(NOMBRES_MEGA),
        )
        borrados = cur.rowcount
        for nombre in NOMBRES_MEGA:
            conn.execute("DELETE FROM sync_state WHERE medidor_id = ?", (nombre,))
        conn.commit()
    return int(borrados or 0)


def _resolver_farm(
    farm_api: FarmClient,
    farm_idcode: str | None,
) -> tuple[str, list[dict[str, Any]]]:
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
    medidores = farm_api.listar_medidores(farm_id)
    if not medidores:
        raise IusasolError("La granja no tiene medidores")
    return farm_id, medidores


def sincronizar_megas(
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    desde: str | None = None,
    hasta: str | None = None,
    quiet: bool = False,
    solo_medidores: tuple[str, ...] | None = None,
    farm_idcode: str | None = None,
    pausa_seg: float = 0.15,
    on_progress: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    """
    Descarga perfiles Farm (5 min) de los 21 MEGAs → SQLite.

    Fuente: Reports/Farm (no ISOL). Canal 0 se guarda en kwh_rec sin escala
    (suma diaria = energía kWh del reporte). `on_progress(step, total, label)`
    se llama por cada día descargado.
    """
    def _prog(step: int, total: int, label: str) -> None:
        if on_progress is not None:
            on_progress(step, total, label)

    db.init_db(ruta_bd)
    asegurar_megas_en_catalogo()
    _prog(0, 1, "Autenticando API Farm…")
    cfg = cargar_config_iusasol()
    api = IusasolClient(cfg)
    api.autenticar()
    farm_api = FarmClient(api)
    _, medidores_farm = _resolver_farm(farm_api, farm_idcode)
    mapeo = mapear_megas_farm(medidores_farm)

    if not quiet:
        print("Granja · mapeo Farm:")
        for fila in resumen_mapeo(mapeo):
            print(
                f"  {fila['mega']}: {fila['estado']} "
                f"nick={fila['nickname']!r} serial={fila['serial_api']!r}"
            )

    nombres = solo_medidores or NOMBRES_MEGA
    resumen: list[dict[str, Any]] = []

    # Plan de trabajo (medidor + días) para dimensionar la barra.
    plan: list[tuple[str, str, list[date]]] = []
    for nombre in nombres:
        item = mapeo.get(nombre)
        if not item:
            resumen.append({
                "medidor": nombre,
                "error": "Sin medidor Farm emparejado (serial/nickname).",
            })
            continue
        meter_id = str(item.get("idcode") or item.get("id") or "")
        if not meter_id:
            resumen.append({"medidor": nombre, "error": "Farm sin idcode"})
            continue
        rango = _calcular_rango(ruta_bd, nombre, desde, hasta)
        if rango is None:
            resumen.append({
                "medidor": nombre,
                "desde": None,
                "hasta": hasta or fecha_fin_api(),
                "leidos": 0,
                "insertados": 0,
                "actualizados": 0,
                "mensaje": "Sin rango pendiente (BD al día).",
            })
            continue
        inicio, fin = rango
        plan.append((nombre, meter_id, _rango_fechas(inicio, fin)))

    total_pasos = sum(len(dias) for _, _, dias in plan) or 1
    hecho = 0
    _prog(0, total_pasos, f"Descargando {len(plan)} MEGA(s)…")

    for nombre, meter_id, dias in plan:
        inicio, fin = dias[0], dias[-1]
        if not quiet:
            print(f"Granja · sync {nombre} ({len(dias)} día(s) {inicio} → {fin})…")

        log_id: int | None = None
        with db.conectar_bd(ruta_bd) as conn:
            log_id = db.iniciar_sync_log(
                conn, nombre, inicio.isoformat(), fin.isoformat()
            )
            conn.commit()

        leidos = 0
        insertados = 0
        actualizados = 0
        dias_ok = 0
        try:
            filas_kw: list[tuple[str, float]] = []
            for dia in dias:
                _prog(hecho, total_pasos, f"{nombre} · {dia.isoformat()}")
                perfiles = farm_api.perfil_medidor_dia(meter_id, dia)
                filas_kw.extend(kw_desde_perfil(perfiles))
                dias_ok += 1
                hecho += 1
                _prog(hecho, total_pasos, f"{nombre} · {dia.isoformat()} listo")
                if pausa_seg > 0:
                    time.sleep(pausa_seg)

            registros = _registros_desde_perfil(filas_kw)
            leidos = len(registros)

            with db.conectar_bd(ruta_bd) as conn:
                for i in range(0, len(registros), LOTE):
                    lote = registros[i : i + LOTE]
                    resultado = db.upsert_registros(
                        conn,
                        nombre,
                        lote,
                        fuente="farm_api",
                        no_degradar_a_ceros=True,
                    )
                    insertados += resultado.insertados
                    actualizados += resultado.actualizados
                if registros:
                    db.actualizar_sync_state(conn, nombre, registros[-1]["fecha"])
                db.cerrar_sync_log(
                    conn, log_id, "ok", leidos, insertados, actualizados
                )
                conn.commit()

            if registros:
                registrar_exito_sync(nombre, ruta_bd)

            resumen.append({
                "medidor": nombre,
                "desde": inicio.isoformat(),
                "hasta": fin.isoformat(),
                "leidos": leidos,
                "insertados": insertados,
                "actualizados": actualizados,
                "farm_idcode": meter_id,
                "mensaje": "OK",
            })
        except Exception as exc:
            faltan = len(dias) - dias_ok
            if faltan > 0:
                hecho += faltan
                _prog(hecho, total_pasos, f"{nombre} · error")
            if log_id is not None:
                with db.conectar_bd(ruta_bd) as conn:
                    db.cerrar_sync_log(
                        conn, log_id, "error", leidos, insertados, actualizados, str(exc)
                    )
                    conn.commit()
            resumen.append({"medidor": nombre, "error": str(exc)})
            if not quiet:
                print(f"  ERROR {nombre}: {exc}")

    _prog(total_pasos, total_pasos, "Sincronización terminada")
    return resumen


def sincronizar_megas_con_lock(
    *,
    timeout: float = 0,
    **kwargs: Any,
) -> list[dict[str, Any]] | None:
    """Igual que `sincronizar_megas`, con lock de archivo entre UI/cron/CLI.

    Con `timeout=0` (auto cada 15 min): si ya hay sync, omite y retorna None.
    Con timeout > 0 (botón manual): espera hasta adquirir o lanza RuntimeError.
    """
    RUTA_LOCK_SYNC.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(RUTA_LOCK_SYNC), timeout=timeout)
    try:
        lock.acquire()
    except Timeout:
        if timeout <= 0:
            return None
        raise RuntimeError(MENSAJE_SYNC_OCUPADO) from None
    try:
        return sincronizar_megas(**kwargs)
    finally:
        lock.release()
