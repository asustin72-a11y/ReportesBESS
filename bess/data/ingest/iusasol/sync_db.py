"""Sincroniza perfiles ISOL (API) hacia SQLite."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bess.config.paths import RUTA_BD_PERFILES
from bess.core.console import log as print
from bess.config.subestaciones import aliases_sync_api
from bess.data.ingest.ion import db
from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError
from bess.data.ingest.iusasol.meters import resolver_id_medidor
from bess.data.ingest.iusasol.gaps import (
    contexto_previo_bd,
    persistir_slots_medianoche_bd,
    rellenar_slots_medianoche_api,
)
from bess.data.ingest.iusasol.to_csv import perfil_json_a_dataframe

FECHA_INICIO_DEFAULT = '2026-05-01'
LOTE = 500
ZONA_API = ZoneInfo('America/Mexico_City')
# La API ISOL solo acepta beginDate/endDate por día; se re-pide el día anterior
# y se sobrescribe en BD para corregir huecos o ceros del sync incremental.
DIAS_SOLAPAMIENTO_API = 1

from bess.data.ingest.medidor_ids import resolver_medidor_bd_desde_api
from bess.data.sync_cursor import (
    inicio_api_con_solapamiento,
    punto_sync_api,
    registrar_exito_sync,
)


def _resolver_medidor_bd(medidor: str) -> str:
    return resolver_medidor_bd_desde_api(medidor)


def _dataframe_a_registros(df) -> list[dict[str, Any]]:
    registros: list[dict[str, Any]] = []
    for _, fila in df.iterrows():
        fecha = fila['Fecha']
        if hasattr(fecha, 'strftime'):
            fecha_txt = fecha.strftime('%Y-%m-%d %H:%M:%S')
        else:
            fecha_txt = str(fecha)
        registros.append({
            'fecha': fecha_txt,
            'kwh_rec': float(fila['KWH_REC'] or 0),
            'kwh_ent': float(fila['KWH_ENT'] or 0),
            'kvarh_q1': float(fila['KVARH_Q1'] or 0),
            'kvarh_q2': float(fila['KVARH_Q2'] or 0),
            'kvarh_q3': float(fila['KVARH_Q3'] or 0),
            'kvarh_q4': float(fila['KVARH_Q4'] or 0),
        })
    return registros


def fecha_fin_api() -> str:
    """Fin del rango API: mañana en America/Mexico_City (hoy + 1 día)."""
    return (datetime.now(ZONA_API).date() + timedelta(days=1)).isoformat()


def _fecha_fin_api() -> str:
    return fecha_fin_api()


def _parse_fecha_iso(texto: str) -> date:
    return date.fromisoformat(texto[:10])


def _ultima_fecha_bd(medidor_bd: str, ruta_bd: Path) -> datetime | None:
    db.init_db(ruta_bd)
    with db.conectar_bd(ruta_bd) as conn:
        row = conn.execute(
            'SELECT MAX(fecha) AS mx FROM perfil_carga WHERE medidor_id = ?',
            (medidor_bd,),
        ).fetchone()
    if not row or not row['mx']:
        return None
    ultima = datetime.fromisoformat(row['mx'])
    if ultima.tzinfo is None:
        ultima = ultima.replace(tzinfo=ZONA_API)
    return ultima


def _sin_rango_api(inicio: str, fin: str, ultima_bd: datetime | None) -> bool:
    """
    True solo si no hay días que pedir a la API.
    Con solapamiento, aunque la BD tenga 23:55 del día fin, se refresca el día anterior.
    """
    if inicio > fin:
        return True
    if ultima_bd is None:
        return False
    # BD más de un día por delante del fin API: no hay ventana válida con solapamiento.
    fin_date = _parse_fecha_iso(fin)
    return ultima_bd.date() > fin_date + timedelta(days=DIAS_SOLAPAMIENTO_API)


def _inicio_con_solapamiento(ultima: datetime) -> str:
    """Día anterior al último slot en BD (mínimo FECHA_INICIO_DEFAULT)."""
    dia = ultima.date() - timedelta(days=DIAS_SOLAPAMIENTO_API)
    inicio_min = date.fromisoformat(FECHA_INICIO_DEFAULT)
    if dia < inicio_min:
        return FECHA_INICIO_DEFAULT
    return dia.isoformat()


def _calcular_rango_fechas(
    medidor_bd: str,
    ruta_bd: Path,
    desde: str | None,
    hasta: str | None,
) -> tuple[str, str]:
    fin_default = _fecha_fin_api()
    fin_explicito = hasta[:10] if hasta else fin_default

    if desde and hasta:
        return desde[:10], fin_explicito

    if not desde and not hasta:
        cursor = punto_sync_api(medidor_bd, ruta_bd)
        if cursor.es_redescarga and cursor.desde_forzado:
            inicio = cursor.desde_forzado.date().isoformat()
            return inicio, fin_default
        if cursor.ultima_incremental:
            inicio = inicio_api_con_solapamiento(cursor.ultima_incremental)
            return inicio, fin_default

        db.init_db(ruta_bd)
        with db.conectar_bd(ruta_bd) as conn:
            row = conn.execute(
                """
                SELECT MAX(fecha) AS mx FROM perfil_carga
                WHERE medidor_id = ? AND substr(fecha, 1, 10) <= ?
                """,
                (medidor_bd, fin_default),
            ).fetchone()
            ultima_txt = row['mx'] if row else None
            ultima = None
            if ultima_txt:
                ultima = datetime.fromisoformat(ultima_txt)
                if ultima.tzinfo is None:
                    ultima = ultima.replace(tzinfo=ZONA_API)
        if ultima is None:
            inicio = FECHA_INICIO_DEFAULT
        else:
            inicio = _inicio_con_solapamiento(ultima)
        return inicio, fin_default

    if desde and not hasta:
        return desde[:10], fin_default
    return FECHA_INICIO_DEFAULT, fin_explicito


def sincronizar_medidor_api(
    medidor: str,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    desde: str | None = None,
    hasta: str | None = None,
    client: IusasolClient | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    medidor_bd = _resolver_medidor_bd(medidor)
    db.init_db(ruta_bd)

    inicio, fin = _calcular_rango_fechas(medidor_bd, ruta_bd, desde, hasta)
    fin_date = _parse_fecha_iso(fin)
    ultima_bd = _ultima_fecha_bd(medidor_bd, ruta_bd)
    incremental = desde is None and hasta is None
    if _sin_rango_api(inicio, fin, ultima_bd if incremental else None):
        ultima_txt = ultima_bd.strftime('%Y-%m-%d %H:%M:%S') if ultima_bd else None
        return {
            'medidor': medidor_bd,
            'desde': inicio,
            'hasta': fin,
            'ultima_bd': ultima_txt,
            'leidos': 0,
            'insertados': 0,
            'actualizados': 0,
            'mensaje': 'Sin rango pendiente (BD al día).',
        }

    if not quiet:
        nota = (
            f' (incluye {DIAS_SOLAPAMIENTO_API} día(s) de solapamiento para refrescar)'
            if incremental and ultima_bd
            else ''
        )
        print(f'  Peticion API {medidor_bd}: beginDate={inicio} endDate={fin}{nota}')

    cfg = cargar_config_iusasol()
    api = client or IusasolClient(cfg)
    medidores_api = api.listar_medidores()
    meter_id = resolver_id_medidor(medidor, medidores_api)

    perfil = api.obtener_perfil(
        meter_id,
        inicio,
        fin,
        tym=cfg.tym,
        tye=cfg.tye,
    )
    df = perfil_json_a_dataframe(perfil)
    if not df.empty:
        contexto = contexto_previo_bd(medidor_bd, ruta_bd, df['Fecha'].min())
        df = rellenar_slots_medianoche_api(df, contexto_prev=contexto)
        df = df[df['Fecha'].dt.date <= fin_date].copy()
    registros = _dataframe_a_registros(df)

    insertados = 0
    actualizados = 0
    with db.conectar_bd(ruta_bd) as conn:
        for i in range(0, len(registros), LOTE):
            lote = registros[i:i + LOTE]
            resultado = db.upsert_registros(conn, medidor_bd, lote, fuente='iusasol')
            insertados += resultado.insertados
            actualizados += resultado.actualizados
        if registros:
            row = conn.execute(
                'SELECT MAX(fecha) AS mx FROM perfil_carga WHERE medidor_id = ?',
                (medidor_bd,),
            ).fetchone()
            ultima_guardada = row['mx'] if row and row['mx'] else registros[-1]['fecha']
            db.actualizar_sync_state(conn, medidor_bd, ultima_guardada)
        conn.commit()

    if registros:
        registrar_exito_sync(medidor_bd, ruta_bd)

    medianoche_persistidos = persistir_slots_medianoche_bd(medidor_bd, ruta_bd)
    if medianoche_persistidos and not quiet:
        print(f'  {medidor_bd}: {medianoche_persistidos} slot(s) 00:00 rellenados en BD')

    return {
        'medidor': medidor_bd,
        'desde': inicio,
        'hasta': fin,
        'leidos': len(registros),
        'insertados': insertados,
        'actualizados': actualizados,
        'mensaje': 'OK',
    }


def sincronizar_api(
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    desde: str | None = None,
    hasta: str | None = None,
    quiet: bool = False,
    solo_aliases: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    cfg = cargar_config_iusasol()
    client = IusasolClient(cfg)
    resumen: list[dict[str, Any]] = []
    vistos: set[str] = set()
    aliases_permitidos = (
        {a.lower() for a in solo_aliases} if solo_aliases is not None else None
    )
    for alias, medidor_bd in aliases_sync_api():
        if medidor_bd in vistos:
            continue
        if aliases_permitidos is not None:
            if alias.lower() not in aliases_permitidos and medidor_bd.lower() not in aliases_permitidos:
                continue
        vistos.add(medidor_bd)
        try:
            resumen.append(
                sincronizar_medidor_api(
                    alias,
                    ruta_bd=ruta_bd,
                    desde=desde,
                    hasta=hasta,
                    client=client,
                    quiet=quiet,
                )
            )
        except (IusasolError, ValueError) as exc:
            resumen.append({
                'medidor': medidor_bd,
                'error': str(exc),
            })
            return resumen
    return resumen


def sincronizar_bess_iusa2(
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    desde: str | None = None,
    hasta: str | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """Sincroniza solo el BESS de Subestación IUSA 2 (serial CS3190) vía API."""
    items = sincronizar_api(
        ruta_bd=ruta_bd,
        desde=desde,
        hasta=hasta,
        quiet=quiet,
        solo_aliases=('bess_iusa2', 'BESS_IUSA2'),
    )
    if not items:
        return {'medidor': db.MEDIDOR_BESS_IUSA2, 'error': 'Sin configuración API para IUSA 2'}
    return items[0]
