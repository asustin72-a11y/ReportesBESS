"""Sincroniza perfiles ISOL (API) hacia SQLite."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bess.config.paths import RUTA_BD_PERFILES
from bess.core.console import log as print
from bess.data.ingest.ion import db
from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError
from bess.data.ingest.iusasol.meters import resolver_id_medidor
from bess.data.ingest.iusasol.to_csv import perfil_json_a_dataframe

FECHA_INICIO_DEFAULT = '2026-05-01'
LOTE = 500
ZONA_API = ZoneInfo('America/Mexico_City')

MEDIDOR_API_A_BD: dict[str, str] = {
    'BESS': 'BESS',
    'bess': 'BESS',
    'banco1': 'BANCO',
    'banco': 'BANCO',
    'BANCO': 'BANCO',
}


def _resolver_medidor_bd(medidor: str) -> str:
    clave = medidor.strip()
    if clave in MEDIDOR_API_A_BD:
        return MEDIDOR_API_A_BD[clave]
    clave_lower = clave.lower()
    for alias, medidor_bd in MEDIDOR_API_A_BD.items():
        if alias.lower() == clave_lower:
            return medidor_bd
    raise ValueError(f'Medidor API no reconocido: {medidor!r}')


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
    """Fin del rango API: hoy en America/Mexico_City (sin +1 día)."""
    return datetime.now(ZONA_API).date().isoformat()


def _fecha_fin_api() -> str:
    return fecha_fin_api()


def _parse_fecha_iso(texto: str) -> date:
    return date.fromisoformat(texto[:10])


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
            inicio_dt = ultima + timedelta(minutes=5)
            inicio = inicio_dt.date().isoformat()
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
    if inicio > fin:
        return {
            'medidor': medidor_bd,
            'desde': inicio,
            'hasta': fin,
            'leidos': 0,
            'insertados': 0,
            'actualizados': 0,
            'mensaje': 'Sin rango pendiente (BD al día).',
        }

    if not quiet:
        print(f'  Peticion API {medidor_bd}: beginDate={inicio} endDate={fin}')

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
            db.actualizar_sync_state(conn, medidor_bd, registros[-1]['fecha'])
        conn.commit()

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
) -> list[dict[str, Any]]:
    cfg = cargar_config_iusasol()
    client = IusasolClient(cfg)
    resumen: list[dict[str, Any]] = []
    for alias in ('BESS', 'banco1'):
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
        except IusasolError as exc:
            resumen.append({
                'medidor': MEDIDOR_API_A_BD.get(alias, alias),
                'error': str(exc),
            })
    return resumen
