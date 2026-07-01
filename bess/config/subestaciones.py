"""Subestaciones: medidores de facturación + BESS por instalación."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MedidorConsumo:
    """Medidor de facturación / consumo enlazado al BESS de la subestación."""

    prefijo: str
    etiqueta: str
    consumo_csv: str
    consumo_filtrado: str
    consumo_lectura: str
    consumo_bd: str
    intercambiar_consumo: bool = False
    api_alias: str | None = None
    usa_consumo_neto: bool = False


@dataclass(frozen=True)
class Subestacion:
    """Subestación con uno o más medidores de consumo y un BESS propio."""

    id: str
    nombre: str
    medidores_consumo: tuple[MedidorConsumo, ...]
    bess_csv: str
    bess_filtrado: str
    bess_bd: str
    modbus_ip: str | None = None
    serial_bess: str | None = None
    generar_bess_general: bool = False
    cliente_recibo: str = ""
    api_bess_alias: str | None = None
    granja_csv: str | None = None
    granja_filtrado: str | None = None
    granja_bd: str | None = None

    @property
    def prefijo(self) -> str:
        return self.medidores_consumo[0].prefijo

    @property
    def etiqueta_facturacion(self) -> str:
        return self.medidores_consumo[0].etiqueta

    @property
    def consumo_csv(self) -> str:
        return self.medidores_consumo[0].consumo_csv

    @property
    def consumo_filtrado(self) -> str:
        return self.medidores_consumo[0].consumo_filtrado

    @property
    def consumo_lectura(self) -> str:
        return self.medidores_consumo[0].consumo_lectura

    @property
    def consumo_bd(self) -> str:
        return self.medidores_consumo[0].consumo_bd

    @property
    def intercambiar_consumo(self) -> bool:
        return self.medidores_consumo[0].intercambiar_consumo


_MED_ION_IUSA1 = MedidorConsumo(
    prefijo="ION",
    etiqueta="ION",
    consumo_csv="ION.csv",
    consumo_filtrado="ION_Filtrado.csv",
    consumo_lectura="ION",
    consumo_bd="ION",
)
_MED_BANCO_IUSA1 = MedidorConsumo(
    prefijo="BANCO",
    etiqueta="Banco 1",
    consumo_csv="Banco1.csv",
    consumo_filtrado="Banco1_Filtrado.csv",
    consumo_lectura="Banco1",
    consumo_bd="BANCO",
    api_alias="banco1",
    intercambiar_consumo=True,
)
_MED_ION_IUSA2 = MedidorConsumo(
    prefijo="IUSA2",
    etiqueta="ION",
    consumo_csv="ION_IUSA2.csv",
    consumo_filtrado="ION_IUSA2_Filtrado.csv",
    consumo_lectura="ION_IUSA2",
    consumo_bd="ION_IUSA2",
    usa_consumo_neto=True,
)

SUBESTACIONES: tuple[Subestacion, ...] = (
    Subestacion(
        id="IUSA1",
        nombre="Subestación IUSA 1",
        medidores_consumo=(_MED_ION_IUSA1, _MED_BANCO_IUSA1),
        bess_csv="BESS.csv",
        bess_filtrado="BESS_Filtrado.csv",
        bess_bd="BESS",
        modbus_ip="172.16.111.209",
        generar_bess_general=True,
        cliente_recibo="ION",
        api_bess_alias="BESS",
    ),
    Subestacion(
        id="IUSA2",
        nombre="Subestación IUSA 2",
        medidores_consumo=(_MED_ION_IUSA2,),
        bess_csv="BESS_IUSA2.csv",
        bess_filtrado="BESS_IUSA2_Filtrado.csv",
        bess_bd="BESS_IUSA2",
        modbus_ip="172.16.205.203",
        serial_bess="CS3190",
        generar_bess_general=False,
        cliente_recibo="IUSA2",
        api_bess_alias="bess_iusa2",
        granja_csv="GRANJA_IUSA2.csv",
        granja_filtrado="GRANJA_IUSA2_Filtrado.csv",
        granja_bd="GRANJA_IUSA2",
    ),
)


def subestacion_por_id(sub_id: str) -> Subestacion | None:
    clave = (sub_id or "").strip().upper()
    for sub in SUBESTACIONES:
        if sub.id.upper() == clave:
            return sub
    return None


def medidor_consumo_por_prefijo(prefijo: str) -> MedidorConsumo | None:
    clave = (prefijo or "").strip().upper()
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            if med.prefijo.upper() == clave:
                return med
    return None


def subestacion_por_prefijo(prefijo: str) -> Subestacion | None:
    clave = (prefijo or "").strip().upper()
    for sub in SUBESTACIONES:
        if sub.prefijo.upper() == clave:
            return sub
        for med in sub.medidores_consumo:
            if med.prefijo.upper() == clave:
                return sub
    return None


def nombre_subestacion(prefijo_o_id: str) -> str:
    sub = subestacion_por_prefijo(prefijo_o_id) or subestacion_por_id(prefijo_o_id)
    if sub:
        return sub.nombre
    return prefijo_o_id


def medidores_facturacion_subestacion(sub_id: str) -> list[str]:
    sub = subestacion_por_id(sub_id)
    if not sub:
        return []
    return [med.prefijo for med in sub.medidores_consumo]


def prefijos_facturacion() -> list[str]:
    prefijos: list[str] = []
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            prefijos.append(med.prefijo)
    return prefijos


def etiqueta_medidor_consumo(prefijo: str) -> str:
    med = medidor_consumo_por_prefijo(prefijo)
    if med:
        return med.etiqueta
    return prefijo


def archivos_fuente_subestacion(sub: Subestacion) -> list[str]:
    """CSV de fuente que corresponden a una subestación (consumo + BESS + granja)."""
    archivos: list[str] = [med.consumo_csv for med in sub.medidores_consumo]
    archivos.append(sub.bess_csv)
    if sub.granja_csv:
        archivos.append(sub.granja_csv)
    return archivos


def archivos_fuente_requeridos() -> list[str]:
    vistos: set[str] = set()
    orden: list[str] = []
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            if med.consumo_csv not in vistos:
                vistos.add(med.consumo_csv)
                orden.append(med.consumo_csv)
        if sub.bess_csv not in vistos:
            vistos.add(sub.bess_csv)
            orden.append(sub.bess_csv)
        if sub.granja_csv and sub.granja_csv not in vistos:
            vistos.add(sub.granja_csv)
            orden.append(sub.granja_csv)
    return orden


def pares_filtrado() -> list[tuple[str, str, str]]:
    """(csv_origen, csv_filtrado, etiqueta) por archivo de cada subestación."""
    pares: list[tuple[str, str, str]] = []
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            pares.append((med.consumo_csv, med.consumo_filtrado, med.consumo_csv))
        pares.append((sub.bess_csv, sub.bess_filtrado, sub.bess_csv))
        if sub.granja_csv and sub.granja_filtrado:
            pares.append((sub.granja_csv, sub.granja_filtrado, sub.granja_csv))
    return pares


def aliases_sync_api() -> list[tuple[str, str]]:
    """(alias API, id medidor en BD): BESS por subestación + Banco 1 en IUSA 1."""
    aliases: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for sub in SUBESTACIONES:
        if sub.api_bess_alias:
            aliases.append((sub.api_bess_alias, sub.bess_bd))
            vistos.add(sub.bess_bd)
        for med in sub.medidores_consumo:
            if med.api_alias and med.consumo_bd not in vistos:
                aliases.append((med.api_alias, med.consumo_bd))
                vistos.add(med.consumo_bd)
    return aliases
