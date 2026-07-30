"""Orquestación: listar medidores y descargar perfiles a CSV/ZIP."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from bess.data.ingest.granja.farm_client import FarmClient
from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError

from descargas.export_csv import (
    csv_farm_bytes,
    csv_isol_bytes,
    csv_porteo_bytes,
    slug_medidor,
)
from descargas.porteo_client import PorteoClient

ProgressCb = Callable[[float, str], None]


@dataclass(frozen=True)
class MedidorInfo:
    idcode: str
    etiqueta: str
    serial: str = ""


def _etiqueta(item: dict[str, Any]) -> str:
    nick = str(item.get("nickname") or "").strip()
    serial = str(item.get("serial") or "").strip()
    if nick and serial:
        return f"{nick} ({serial})"
    return nick or serial or str(item.get("idcode") or item.get("id") or "?")


def _idcode(item: dict[str, Any]) -> str:
    return str(item.get("idcode") or item.get("id") or "").strip()


def crear_clientes() -> tuple[IusasolClient, FarmClient, PorteoClient]:
    isol = IusasolClient(cargar_config_iusasol())
    isol.autenticar()
    return isol, FarmClient(isol), PorteoClient(isol)


def listar_medidores_clientes(isol: IusasolClient) -> list[MedidorInfo]:
    datos = isol.listar_medidores()
    items = datos.get("meters", []) if isinstance(datos, dict) else datos
    if not isinstance(items, list):
        raise IusasolError("Respuesta inesperada en Reports/ISOL/Meters")
    out: list[MedidorInfo] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        mid = _idcode(item)
        if not mid:
            continue
        out.append(
            MedidorInfo(
                idcode=mid,
                etiqueta=_etiqueta(item),
                serial=str(item.get("serial") or ""),
            )
        )
    return out


def listar_medidores_granja(farm: FarmClient, farm_idcode: str | None = None) -> list[MedidorInfo]:
    granjas = farm.listar_granjas()
    if not granjas:
        raise IusasolError("No hay granjas en Reports/Farms")
    if farm_idcode:
        elegido = farm_idcode
    else:
        elegido = str(granjas[0].get("idcode") or granjas[0].get("id") or "")
    if not elegido:
        raise IusasolError("Granja sin idcode")
    items = farm.listar_medidores(elegido)
    out: list[MedidorInfo] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        mid = _idcode(item)
        if not mid:
            continue
        out.append(
            MedidorInfo(
                idcode=mid,
                etiqueta=_etiqueta(item),
                serial=str(item.get("serial") or ""),
            )
        )
    return out


def listar_medidores_porteo(porteo: PorteoClient) -> list[MedidorInfo]:
    items = porteo.listar_medidores()
    out: list[MedidorInfo] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        mid = _idcode(item)
        if not mid:
            continue
        out.append(
            MedidorInfo(
                idcode=mid,
                etiqueta=_etiqueta(item),
                serial=str(item.get("serial") or ""),
            )
        )
    return out


def _rango_dias(desde: date, hasta: date) -> list[date]:
    if hasta < desde:
        raise ValueError("La fecha fin debe ser >= fecha inicio")
    dias: list[date] = []
    cursor = desde
    while cursor <= hasta:
        dias.append(cursor)
        cursor += timedelta(days=1)
    return dias


def descargar_clientes_csv(
    isol: IusasolClient,
    medidores: list[MedidorInfo],
    desde: date,
    hasta: date,
    *,
    progress: ProgressCb | None = None,
) -> tuple[bytes, str]:
    """Retorna (contenido, nombre_archivo) — CSV o ZIP."""
    archivos: list[tuple[str, bytes]] = []
    total = max(len(medidores), 1)
    for i, med in enumerate(medidores):
        if progress:
            progress(i / total, f"Clientes · {med.etiqueta}")
        perfil = isol.obtener_perfil(
            med.idcode,
            desde.isoformat(),
            hasta.isoformat(),
            tym=isol.config.tym or "2",
            tye=isol.config.tye or "E",
        )
        csv_bytes = csv_isol_bytes(perfil)
        nombre = (
            f"clientes_{slug_medidor(med.etiqueta, med.idcode)}"
            f"_{desde.isoformat()}_{hasta.isoformat()}.csv"
        )
        archivos.append((nombre, csv_bytes))
    if progress:
        progress(1.0, "Listo")
    return _empaquetar(archivos)


def descargar_porteo_csv(
    porteo: PorteoClient,
    medidores: list[MedidorInfo],
    desde: date,
    hasta: date,
    *,
    progress: ProgressCb | None = None,
) -> tuple[bytes, str]:
    archivos: list[tuple[str, bytes]] = []
    total = max(len(medidores), 1)
    for i, med in enumerate(medidores):
        if progress:
            progress(i / total, f"Porteo · {med.etiqueta}")
        perfil = porteo.obtener_perfil(
            med.idcode,
            desde.isoformat(),
            hasta.isoformat(),
        )
        csv_bytes = csv_porteo_bytes(perfil)
        nombre = (
            f"porteo_{slug_medidor(med.etiqueta, med.idcode)}"
            f"_{desde.isoformat()}_{hasta.isoformat()}.csv"
        )
        archivos.append((nombre, csv_bytes))
    if progress:
        progress(1.0, "Listo")
    return _empaquetar(archivos)


def descargar_granja_csv(
    farm: FarmClient,
    medidores: list[MedidorInfo],
    desde: date,
    hasta: date,
    *,
    progress: ProgressCb | None = None,
) -> tuple[bytes, str]:
    dias = _rango_dias(desde, hasta)
    archivos: list[tuple[str, bytes]] = []
    total_pasos = max(len(medidores) * len(dias), 1)
    paso = 0
    for med in medidores:
        acumulado: list[dict] = []
        for dia in dias:
            if progress:
                progress(
                    paso / total_pasos,
                    f"Granja · {med.etiqueta} · {dia.isoformat()}",
                )
            acumulado.extend(farm.perfil_medidor_dia(med.idcode, dia))
            paso += 1
        csv_bytes = csv_farm_bytes(acumulado)
        nombre = (
            f"granja_{slug_medidor(med.etiqueta, med.idcode)}"
            f"_{desde.isoformat()}_{hasta.isoformat()}.csv"
        )
        archivos.append((nombre, csv_bytes))
    if progress:
        progress(1.0, "Listo")
    return _empaquetar(archivos)


def _empaquetar(archivos: list[tuple[str, bytes]]) -> tuple[bytes, str]:
    if not archivos:
        raise ValueError("No hay archivos para descargar")
    if len(archivos) == 1:
        return archivos[0][1], archivos[0][0]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in archivos:
            zf.writestr(nombre, contenido)
    return buffer.getvalue(), "perfiles_descarga.zip"


def estimar_requests_granja(n_medidores: int, desde: date, hasta: date) -> int:
    dias = max((hasta - desde).days + 1, 0)
    return n_medidores * dias
