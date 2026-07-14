"""Resumen compacto de sincronizacion de perfiles (sidebar / --quiet)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bess.config.constants import etiqueta_medidor
from bess.config.subestaciones import SUBESTACIONES
from bess.data.ingest.ion import db


def _fmt_fecha_corta(fecha: str | None) -> str:
    if not fecha:
        return '-'
    txt = str(fecha).strip()
    if len(txt) >= 16:
        # 2026-06-27 00:15:00 -> 27/06 00:15
        return f"{txt[8:10]}/{txt[5:7]} {txt[11:16]}"
    if len(txt) >= 10:
        return f"{txt[8:10]}/{txt[5:7]}"
    return txt


def _max_fecha_bd(ruta_bd: Path, medidor: str) -> str | None:
    if not ruta_bd.is_file():
        return None
    with db.conectar_bd(ruta_bd) as conn:
        row = conn.execute(
            'SELECT MAX(fecha) AS mx FROM perfil_carga WHERE medidor_id = ?',
            (medidor,),
        ).fetchone()
    return row['mx'] if row and row['mx'] else None


def linea_ion_modbus(
    medidor_bd: str,
    etiqueta: str,
    ion_stats: dict[str, Any] | None,
    *,
    no_disponible: bool,
    ruta_bd: Path,
) -> str:
    if no_disponible:
        hasta = _fmt_fecha_corta(_max_fecha_bd(ruta_bd, medidor_bd))
        return f'{etiqueta}: no disponible | BD {hasta}'
    if not ion_stats:
        return f'{etiqueta}: -'
    nuevos = int(ion_stats.get('insertados') or 0)
    leidos = int(ion_stats.get('leidos') or 0)
    hasta = ion_stats.get('ultima') or _max_fecha_bd(ruta_bd, medidor_bd)
    if leidos == 0 and nuevos == 0:
        return f'{etiqueta}: al dia | {_fmt_fecha_corta(hasta)}'
    return f'{etiqueta}: +{nuevos} | {_fmt_fecha_corta(hasta)}'


def linea_ion(ion_stats: dict[str, Any] | None, *, no_disponible: bool, ruta_bd: Path) -> str:
    return linea_ion_modbus(db.MEDIDOR_ION, 'ION', ion_stats, no_disponible=no_disponible, ruta_bd=ruta_bd)


def _etiqueta_sync(medidor_bd: str) -> str:
    for sub in SUBESTACIONES:
        if sub.granja_bd and medidor_bd == sub.granja_bd:
            return f"Granja · {sub.nombre}"
        if medidor_bd == sub.bess_bd:
            return f"BESS · {sub.nombre}"
        for med in sub.medidores_consumo:
            if medidor_bd == med.consumo_bd:
                return f"{med.etiqueta} · {sub.nombre}"
    return etiqueta_medidor(medidor_bd)


def linea_api(item: dict[str, Any], ruta_bd: Path) -> str:
    medidor = item.get('medidor', '?')
    etiqueta = _etiqueta_sync(medidor)
    if 'error' in item:
        return f'{etiqueta}: error API'
    nuevos = int(item.get('insertados') or 0)
    leidos = int(item.get('leidos') or 0)
    hasta = _max_fecha_bd(ruta_bd, medidor)
    if leidos == 0 and nuevos == 0:
        return f'{etiqueta}: al dia | {_fmt_fecha_corta(hasta)}'
    return f'{etiqueta}: +{nuevos} | {_fmt_fecha_corta(hasta)}'


def construir_lineas_resumen(
    *,
    ruta_bd: Path,
    ion_stats: dict[str, Any] | None,
    ion_no_disponible: bool,
    ion_iusa2_stats: dict[str, Any] | None = None,
    ion_iusa2_no_disponible: bool = False,
    incluir_ion_iusa2: bool = True,
    api_items: list[dict[str, Any]],
    granja_item: dict[str, Any] | None = None,
    incluir_granja: bool = True,
    export_ok: bool,
    incluir_ion: bool = True,
) -> list[str]:
    lineas: list[str] = []
    if incluir_ion:
        lineas.append(linea_ion(ion_stats, no_disponible=ion_no_disponible, ruta_bd=ruta_bd))
    if incluir_ion_iusa2:
        lineas.append(
            linea_ion_modbus(
                db.MEDIDOR_ION_IUSA2,
                _etiqueta_sync(db.MEDIDOR_ION_IUSA2),
                ion_iusa2_stats,
                no_disponible=ion_iusa2_no_disponible,
                ruta_bd=ruta_bd,
            )
        )
    lineas.extend(linea_api(item, ruta_bd) for item in api_items)
    if incluir_granja and granja_item is not None:
        lineas.append(linea_api(granja_item, ruta_bd))
    lineas.append('Export: OK' if export_ok else 'Export: error')
    return lineas


def html_resumen_sidebar(lineas: list[str]) -> str:
    filas = ''.join(f'<div>{ln}</div>' for ln in lineas)
    return f'<div class="sync-resumen">{filas}</div>'
