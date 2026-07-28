"""Emparejar MEGAs del catálogo con medidores Reports/Farm."""

from __future__ import annotations

import re
from typing import Any

from bess.data.ingest.iusasol.meters import serial_patron

from granja.config.meters import MEGAS, Mega

_RE_MEGA_NUM = re.compile(r"MEGA\s*0*(\d+)", re.IGNORECASE)


def numero_desde_nickname(nickname: str) -> int | None:
    m = _RE_MEGA_NUM.search(nickname or "")
    return int(m.group(1)) if m else None


def mapear_megas_farm(medidores_farm: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Devuelve {nombre_catalogo: item_farm} para Mega01…Mega21.

    Prioridad: serial (CYM769…) → número en nickname (MEGA 1) → orden API.
    """
    por_nombre: dict[str, dict[str, Any]] = {}
    usados: set[int] = set()

    # 1) Por serial
    for mega in MEGAS:
        patron = serial_patron(mega.numero_serie)
        if not patron:
            continue
        for idx, item in enumerate(medidores_farm):
            if idx in usados:
                continue
            serial = str(item.get("serial") or item.get("Serie") or "").upper()
            if patron in serial:
                por_nombre[mega.nombre] = item
                usados.add(idx)
                break

    # 2) Por número en nickname
    for mega in MEGAS:
        if mega.nombre in por_nombre:
            continue
        num = int(mega.nombre.replace("Mega", ""))
        for idx, item in enumerate(medidores_farm):
            if idx in usados:
                continue
            nick_num = numero_desde_nickname(str(item.get("nickname") or ""))
            if nick_num == num:
                por_nombre[mega.nombre] = item
                usados.add(idx)
                break

    # 3) Relleno por orden API (solo los que falten)
    libres = [i for i, _ in enumerate(medidores_farm) if i not in usados]
    for mega in MEGAS:
        if mega.nombre in por_nombre:
            continue
        if not libres:
            break
        idx = libres.pop(0)
        por_nombre[mega.nombre] = medidores_farm[idx]
        usados.add(idx)

    return por_nombre


def resumen_mapeo(mapeo: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    filas: list[dict[str, str]] = []
    for mega in MEGAS:
        item = mapeo.get(mega.nombre)
        if not item:
            filas.append({
                "mega": mega.nombre,
                "serie_catalogo": mega.numero_serie,
                "idcode": "",
                "nickname": "",
                "serial_api": "",
                "estado": "SIN MATCH",
            })
            continue
        filas.append({
            "mega": mega.nombre,
            "serie_catalogo": mega.numero_serie,
            "idcode": str(item.get("idcode") or item.get("id") or ""),
            "nickname": str(item.get("nickname") or ""),
            "serial_api": str(item.get("serial") or ""),
            "estado": "OK",
        })
    return filas
