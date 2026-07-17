"""
CSV de última sincronización por medidor (cursor de petición de perfiles).

Archivo: data/Tarifas/Ultima_Sincronizacion.csv
Columnas: medidor_id, ultima_fecha

- Tras cada sync exitoso se actualiza ultima_fecha con MAX(fecha) en SQLite.
- Si edita ultima_fecha a una fecha anterior, el siguiente sync pide desde ahí
  y los registros existentes se sobrescriben (upsert en perfil_carga).
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bess.config.paths import RUTA_BD_PERFILES, RUTA_ULTIMA_SINCRONIZACION
from bess.data.ingest.ion import db
from bess.data.ingest.medidor_ids import construir_medidores_catalogo_bd, medidor_id_canonico

ZONA_DEFAULT = ZoneInfo("America/Mexico_City")
UMBRAL_REDESCARGA_API = timedelta(days=1)
UMBRAL_REDESCARGA_ION = timedelta(minutes=5)


@dataclass(frozen=True)
class PuntoSync:
    """Punto de partida para la siguiente petición de perfiles."""

    desde_forzado: datetime | None = None
    ultima_incremental: datetime | None = None

    @property
    def es_redescarga(self) -> bool:
        return self.desde_forzado is not None


def _medidores_conocidos() -> list[str]:
    return sorted({fila[0] for fila in construir_medidores_catalogo_bd()})


def _parse_fecha(texto: str, zona: ZoneInfo = ZONA_DEFAULT) -> datetime:
    txt = (texto or "").strip()
    if not txt:
        raise ValueError("fecha vacía")
    if len(txt) == 10:
        txt = f"{txt} 00:05:00"
    dt = datetime.fromisoformat(txt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zona)
    return dt


def leer_mapa(ruta: Path = RUTA_ULTIMA_SINCRONIZACION) -> dict[str, str]:
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "medidor_id" not in reader.fieldnames:
            return {}
        out: dict[str, str] = {}
        for row in reader:
            med = medidor_id_canonico((row.get("medidor_id") or "").strip())
            fecha = (row.get("ultima_fecha") or "").strip()
            if med and fecha:
                out[med] = fecha
        return out


def leer_ultima_fecha(
    medidor_id: str,
    ruta: Path = RUTA_ULTIMA_SINCRONIZACION,
) -> str | None:
    return leer_mapa(ruta).get(medidor_id_canonico(medidor_id))


def _max_fecha_bd(medidor_id: str, ruta_bd: Path) -> str | None:
    canon = medidor_id_canonico(medidor_id)
    if not ruta_bd.is_file():
        return None
    with sqlite3.connect(ruta_bd) as conn:
        row = conn.execute(
            "SELECT MAX(fecha) AS mx FROM perfil_carga WHERE medidor_id = ?",
            (canon,),
        ).fetchone()
    if not row or not row[0]:
        return None
    return str(row[0])


def escribir_mapa(
    datos: dict[str, str],
    ruta: Path = RUTA_ULTIMA_SINCRONIZACION,
) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["medidor_id", "ultima_fecha"])
        writer.writeheader()
        for medidor_id, ultima_fecha in sorted(datos.items()):
            writer.writerow({"medidor_id": medidor_id, "ultima_fecha": ultima_fecha})
    tmp.replace(ruta)


def guardar_ultima_fecha(
    medidor_id: str,
    ultima_fecha: str,
    ruta: Path = RUTA_ULTIMA_SINCRONIZACION,
) -> None:
    canon = medidor_id_canonico(medidor_id)
    datos = leer_mapa(ruta)
    datos[canon] = ultima_fecha.strip()
    escribir_mapa(datos, ruta)


def inicializar_desde_bd(
    ruta_bd: Path = RUTA_BD_PERFILES,
    ruta_csv: Path = RUTA_ULTIMA_SINCRONIZACION,
    *,
    sobrescribir: bool = False,
) -> int:
    """Crea o completa el CSV desde MAX(fecha) en perfil_carga."""
    datos = {} if sobrescribir else leer_mapa(ruta_csv)
    actualizados = 0
    for medidor_id in _medidores_conocidos():
        mx = _max_fecha_bd(medidor_id, ruta_bd)
        if mx and (sobrescribir or medidor_id not in datos):
            datos[medidor_id] = mx
            actualizados += 1
    if actualizados or not ruta_csv.is_file():
        escribir_mapa(datos, ruta_csv)
    return actualizados


def registrar_exito_sync(
    medidor_id: str,
    ruta_bd: Path = RUTA_BD_PERFILES,
    ruta_csv: Path | None = None,
) -> str | None:
    """Tras sync/import OK: cursor CSV = último registro en BD."""
    if ruta_csv is None:
        ruta_csv = RUTA_ULTIMA_SINCRONIZACION
    mx = _max_fecha_bd(medidor_id, ruta_bd)
    if not mx:
        return None
    canon = medidor_id_canonico(medidor_id)
    guardar_ultima_fecha(canon, mx, ruta_csv)
    with db.conectar_bd(ruta_bd) as conn:
        db.actualizar_sync_state(conn, canon, mx)
        conn.commit()
    return mx


def _punto_desde_csv_y_bd(
    medidor_id: str,
    ruta_bd: Path,
    zona: ZoneInfo,
    *,
    umbral_redescarga: timedelta,
) -> PuntoSync:
    canon = medidor_id_canonico(medidor_id)
    if not RUTA_ULTIMA_SINCRONIZACION.is_file():
        inicializar_desde_bd(ruta_bd)

    csv_txt = leer_ultima_fecha(canon)
    if not csv_txt:
        mx = _max_fecha_bd(canon, ruta_bd)
        if mx:
            guardar_ultima_fecha(canon, mx)
            csv_txt = mx
        else:
            return PuntoSync()

    csv_dt = _parse_fecha(csv_txt, zona)
    bd_txt = _max_fecha_bd(canon, ruta_bd)
    if bd_txt:
        bd_dt = _parse_fecha(bd_txt, zona)
        if csv_dt < bd_dt - umbral_redescarga:
            return PuntoSync(desde_forzado=csv_dt)
    return PuntoSync(ultima_incremental=csv_dt)


def punto_sync_api(medidor_id: str, ruta_bd: Path = RUTA_BD_PERFILES) -> PuntoSync:
    return _punto_desde_csv_y_bd(
        medidor_id,
        ruta_bd,
        ZONA_DEFAULT,
        umbral_redescarga=UMBRAL_REDESCARGA_API,
    )


def punto_sync_ion(
    medidor_id: str,
    ruta_bd: Path,
    zona: ZoneInfo,
    *,
    reiniciar: bool = False,
) -> PuntoSync:
    if reiniciar:
        csv_txt = leer_ultima_fecha(medidor_id)
        if csv_txt:
            return PuntoSync(desde_forzado=_parse_fecha(csv_txt, zona))
        return PuntoSync()
    return _punto_desde_csv_y_bd(
        medidor_id,
        ruta_bd,
        zona,
        umbral_redescarga=UMBRAL_REDESCARGA_ION,
    )


def _fecha_sync_state(medidor_id: str, ruta_bd: Path) -> str | None:
    canon = medidor_id_canonico(medidor_id)
    if not ruta_bd.is_file():
        return None
    with sqlite3.connect(ruta_bd) as conn:
        row = conn.execute(
            "SELECT ultima_fecha FROM sync_state WHERE medidor_id = ?",
            (canon,),
        ).fetchone()
    if not row or not row[0]:
        return None
    return str(row[0])


def divergencias_cursores(
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    ruta_csv: Path | None = None,
    umbral: timedelta = timedelta(minutes=5),
) -> list[dict]:
    """Compara sync_state.ultima_fecha vs Ultima_Sincronizacion.csv.

    Devuelve solo medidores donde ambos existen y difieren más que `umbral`,
    o donde uno existe y el otro no (con datos en BD).
    """
    if ruta_csv is None:
        ruta_csv = RUTA_ULTIMA_SINCRONIZACION
    mapa_csv = leer_mapa(ruta_csv) if ruta_csv.is_file() else {}
    ids = sorted(set(_medidores_conocidos()) | set(mapa_csv))
    out: list[dict] = []
    for medidor_id in ids:
        csv_txt = mapa_csv.get(medidor_id) or mapa_csv.get(medidor_id_canonico(medidor_id))
        state_txt = _fecha_sync_state(medidor_id, ruta_bd)
        max_bd = _max_fecha_bd(medidor_id, ruta_bd)
        if not csv_txt and not state_txt and not max_bd:
            continue
        if csv_txt == state_txt:
            continue
        motivo = "distintos"
        desfase_seg: float | None = None
        if csv_txt and state_txt:
            try:
                csv_dt = _parse_fecha(csv_txt, ZONA_DEFAULT)
                state_dt = _parse_fecha(state_txt, ZONA_DEFAULT)
                desfase_seg = abs((state_dt - csv_dt).total_seconds())
                if desfase_seg <= umbral.total_seconds():
                    continue
                if csv_dt < state_dt:
                    motivo = "CSV atrás de sync_state (riesgo de redescarga)"
                else:
                    motivo = "CSV adelante de sync_state"
            except ValueError:
                motivo = "fechas no parseables"
        elif csv_txt and not state_txt:
            motivo = "solo en Ultima_Sincronizacion"
        elif state_txt and not csv_txt:
            motivo = "solo en sync_state"
        out.append(
            {
                "medidor_id": medidor_id,
                "sync_state": state_txt,
                "ultima_sincronizacion_csv": csv_txt,
                "max_perfil_carga": max_bd,
                "desfase_segundos": desfase_seg,
                "motivo": motivo,
            }
        )
    return out


def alinear_cursores_a_bd(
    medidores: list[str] | None = None,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    ruta_csv: Path | None = None,
) -> list[dict]:
    """Pone Ultima_Sincronizacion = MAX(fecha) en BD (y refresca sync_state)."""
    if ruta_csv is None:
        ruta_csv = RUTA_ULTIMA_SINCRONIZACION
    ids = medidores or _medidores_conocidos()
    hechos: list[dict] = []
    for medidor_id in ids:
        mx = registrar_exito_sync(medidor_id, ruta_bd, ruta_csv)
        if mx:
            hechos.append({"medidor_id": medidor_id, "cursor": mx})
    return hechos


def inicio_api_con_solapamiento(ultima: datetime) -> str:
    """Día anterior al cursor (mínimo FECHA_INICIO_DEFAULT de sync_db)."""
    from bess.data.ingest.iusasol.sync_db import FECHA_INICIO_DEFAULT

    dia = ultima.date() - timedelta(days=1)
    inicio_min = datetime.fromisoformat(FECHA_INICIO_DEFAULT).date()
    if dia < inicio_min:
        return FECHA_INICIO_DEFAULT
    return dia.isoformat()
