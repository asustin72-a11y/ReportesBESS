"""Subestaciones y medidores derivados del catálogo CSV."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from bess.config import rutas as rutas_mod
from bess.config.paths import DIRECTORIO_REPORTES
from bess.config.catalog import (
    TIPO_BESS,
    TIPO_FACTURACION,
    TIPO_GENERACION,
    TIPO_TESTIGO,
    MedidorCatalogo,
    obtener_catalogo,
)

_LEGACY_PREFIJO: dict[str, str] = {
    "ION_Testigo_IUSA1": "ION",
    "Banco_1": "BANCO",
    "ION_TESTIGO_IUSA2": "IUSA2",
}

_API_ALIAS: dict[str, str] = {
    "Banco_1": "banco1",
    "BESS_NORTE": "BESS",
    "BESS_SUR": "bess_iusa2",
}

_ETIQUETAS: dict[str, str] = {
    "ION_Testigo_IUSA1": "ION",
    "Banco_1": "Banco 1",
    "ION_TESTIGO_IUSA2": "ION",
}


@dataclass(frozen=True)
class MedidorConsumo:
    """Medidor tipo 1 o 2 (facturación / testigo)."""

    nombre: str
    prefijo: str
    subestacion_nombre: str
    etiqueta: str
    consumo_csv: str
    consumo_filtrado: str
    consumo_lectura: str
    consumo_bd: str
    intercambiar_consumo: bool = False
    api_alias: str | None = None
    usa_consumo_neto: bool = False

    def ruta_consumo(self, *, filtrado: bool = False) -> Path:
        return rutas_mod.ruta_procesado_medidor(
            self.nombre, self.subestacion_nombre, filtrado=filtrado
        )

    def ruta_consumo_lectura(self, *, filtrado: bool = False) -> Path:
        return rutas_mod.resolver_ruta_procesado(self.ruta_consumo(filtrado=filtrado))

    def ruta_combinado(self) -> Path:
        return rutas_mod.ruta_combinado_minuto(self.nombre, self.subestacion_nombre)

    def ruta_energia_dia(self) -> Path:
        return rutas_mod.ruta_energia_por_dia(self.nombre, self.subestacion_nombre)

    def ruta_acumulados(self) -> Path:
        return rutas_mod.ruta_acumulados(self.nombre, self.subestacion_nombre)


@dataclass(frozen=True)
class Subestacion:
    """Subestación con medidores de consumo y agregados BESS / generación."""

    id: str
    nombre: str
    medidores_consumo: tuple[MedidorConsumo, ...]
    bess_csv: str
    bess_filtrado: str
    bess_bd: str
    modbus_ip: str | None = None
    serial_bess: str | None = None
    cliente_recibo: str = ""
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

    def ruta_bess(self, *, filtrado: bool = False) -> Path:
        return rutas_mod.ruta_bess_subestacion(self.id, filtrado=filtrado)

    def ruta_bess_lectura(self, *, filtrado: bool = False) -> Path:
        return rutas_mod.resolver_ruta_procesado(self.ruta_bess(filtrado=filtrado))

    def ruta_generacion(self, *, filtrado: bool = False) -> Path:
        if not self.granja_csv:
            return rutas_mod.ruta_generacion_subestacion(self.id, filtrado=filtrado)
        archivo = self.granja_filtrado if filtrado else self.granja_csv
        return rutas_mod.ruta_procesado(self.id, archivo or "")

    def ruta_generacion_lectura(self, *, filtrado: bool = False) -> Path:
        return rutas_mod.resolver_ruta_procesado(self.ruta_generacion(filtrado=filtrado))

    def ruta_energia_bess_dia(self) -> Path:
        return rutas_mod.ruta_energia_bess_por_dia(self.id)


def _medidor_consumo_desde_catalogo(m: MedidorCatalogo) -> MedidorConsumo:
    cat = obtener_catalogo()
    reglas = cat.reglas_tipo(m.tipo_medidor)
    if reglas is None:
        raise ValueError(f"Sin reglas para tipo {m.tipo_medidor}")
    return MedidorConsumo(
        nombre=m.nombre,
        prefijo=_LEGACY_PREFIJO.get(m.nombre, m.nombre),
        subestacion_nombre=m.subestacion_nombre,
        etiqueta=_ETIQUETAS.get(m.nombre, m.nombre),
        consumo_csv=rutas_mod.nombre_archivo_medidor(m.nombre),
        consumo_filtrado=rutas_mod.nombre_archivo_filtrado(m.nombre),
        consumo_lectura=m.nombre,
        consumo_bd=m.nombre,
        intercambiar_consumo=reglas.invertir,
        usa_consumo_neto=reglas.neteo,
        api_alias=_API_ALIAS.get(m.nombre),
    )


@lru_cache(maxsize=1)
def _construir_subestaciones() -> tuple[Subestacion, ...]:
    cat = obtener_catalogo()
    subs: list[Subestacion] = []

    for sub_c in cat.subestaciones:
        meds_sub = cat.medidores_subestacion(sub_c.nombre)
        consumo = tuple(
            _medidor_consumo_desde_catalogo(m)
            for m in meds_sub
            if m.tipo_medidor in (TIPO_FACTURACION, TIPO_TESTIGO)
        )
        bess_meds = [m for m in meds_sub if m.tipo_medidor == TIPO_BESS]
        ion_fact = next((m for m in meds_sub if m.es_facturacion and m.descarga == "ION"), None)

        granja_csv = None
        granja_filtrado = None
        granja_bd = None
        if sub_c.generacion:
            granja_csv = rutas_mod.nombre_generacion_subestacion(sub_c.nombre)
            granja_filtrado = rutas_mod.nombre_generacion_subestacion_filtrado(sub_c.nombre)
            granja_bd = granja_csv.replace(".csv", "")

        serial_bess = bess_meds[0].numero_serie.split()[0] if bess_meds else None
        cliente = consumo[0].prefijo if consumo else sub_c.nombre

        subs.append(
            Subestacion(
                id=sub_c.nombre,
                nombre=f"Subestación {sub_c.nombre.replace('_', ' ')}",
                medidores_consumo=consumo,
                bess_csv=rutas_mod.nombre_bess_subestacion(sub_c.nombre),
                bess_filtrado=rutas_mod.nombre_bess_subestacion_filtrado(sub_c.nombre),
                bess_bd=f"BESS_{sub_c.nombre}",
                modbus_ip=ion_fact.ip if ion_fact and ion_fact.ip != "0" else None,
                serial_bess=serial_bess,
                cliente_recibo=cliente,
                granja_csv=granja_csv,
                granja_filtrado=granja_filtrado,
                granja_bd=granja_bd,
            )
        )
    return tuple(subs)


def _subs() -> tuple[Subestacion, ...]:
    return _construir_subestaciones()


class _SubestacionesProxy:
    """Lista perezosa para compatibilidad con SUBESTACIONES."""

    def __iter__(self):
        return iter(_subs())

    def __len__(self) -> int:
        return len(_subs())

    def __getitem__(self, index: int) -> Subestacion:
        return _subs()[index]


SUBESTACIONES = _SubestacionesProxy()


def invalidar_cache_subestaciones() -> None:
    _construir_subestaciones.cache_clear()


def subestacion_por_id(sub_id: str) -> Subestacion | None:
    clave = (sub_id or "").strip()
    for sub in _subs():
        if sub.id.upper() == clave.upper():
            return sub
    return None


def medidor_consumo_por_prefijo(prefijo: str) -> MedidorConsumo | None:
    clave = (prefijo or "").strip().upper()
    for sub in _subs():
        for med in sub.medidores_consumo:
            if med.prefijo.upper() == clave or med.nombre.upper() == clave:
                return med
    return None


def medidor_consumo_por_nombre(nombre: str) -> MedidorConsumo | None:
    clave = (nombre or "").strip()
    for sub in _subs():
        for med in sub.medidores_consumo:
            if med.nombre == clave:
                return med
    return None


def subestacion_por_prefijo(prefijo: str) -> Subestacion | None:
    med = medidor_consumo_por_prefijo(prefijo)
    if med:
        return subestacion_por_id(med.subestacion_nombre)
    clave = (prefijo or "").strip().upper()
    for sub in _subs():
        if sub.id.upper() == clave:
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
    return [med.prefijo for sub in _subs() for med in sub.medidores_consumo]


def etiqueta_medidor_consumo(prefijo: str) -> str:
    med = medidor_consumo_por_prefijo(prefijo)
    if med:
        return med.etiqueta
    return prefijo


def aliases_sync_api() -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = []
    vistos: set[str] = set()
    cat = obtener_catalogo()
    for m in cat.medidores:
        alias = _API_ALIAS.get(m.nombre)
        if alias and m.nombre not in vistos:
            aliases.append((alias, m.nombre))
            vistos.add(m.nombre)
    return aliases


def archivos_fuente_subestacion(sub: Subestacion) -> list[str]:
    """CSV en ArchivosFuente/{sub}/: consumo, BESS individual; agregado de generación."""
    cat = obtener_catalogo()
    nombres: list[str] = []
    for m in cat.medidores_subestacion(sub.id):
        if m.tipo_medidor in (TIPO_BESS, TIPO_FACTURACION, TIPO_TESTIGO):
            nombres.append(rutas_mod.nombre_archivo_medidor(m.nombre))
    if sub.granja_csv:
        nombres.append(sub.granja_csv)
    return nombres


def archivos_fuente_requeridos() -> list[str]:
    vistos: set[str] = set()
    orden: list[str] = []
    for sub in _subs():
        for archivo in archivos_fuente_subestacion(sub):
            if archivo not in vistos:
                vistos.add(archivo)
                orden.append(archivo)
    return orden


def pares_filtrado() -> list[tuple[str, str, str]]:
    pares: list[tuple[str, str, str]] = []
    for sub in _subs():
        for med in sub.medidores_consumo:
            pares.append((med.consumo_csv, med.consumo_filtrado, med.consumo_csv))
        pares.append((sub.bess_csv, sub.bess_filtrado, sub.bess_csv))
        if sub.granja_csv and sub.granja_filtrado:
            pares.append((sub.granja_csv, sub.granja_filtrado, sub.granja_csv))
    return pares


def _legacy_combinado(prefijo: str) -> Path:
    return DIRECTORIO_REPORTES / f"COMBINADO_POR_MINUTO_{prefijo}.csv"


def _legacy_energia_dia(prefijo: str) -> Path:
    return DIRECTORIO_REPORTES / f"ENERGIA_{prefijo}_POR_DIA.csv"


def _legacy_acumulados(prefijo: str) -> Path:
    return DIRECTORIO_REPORTES / f"ACUMULADOS_{prefijo}.csv"


def _resolver_ruta(nueva: Path, legacy: Path) -> Path:
    if nueva.exists():
        return nueva
    if legacy.exists():
        return legacy
    return nueva


def rutas_consumo_por_prefijo(prefijo: str) -> tuple[Path, Path] | None:
    """(combinado, energía día) para un medidor de consumo."""
    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        return None
    return (
        _resolver_ruta(med.ruta_combinado(), _legacy_combinado(med.prefijo)),
        _resolver_ruta(med.ruta_energia_dia(), _legacy_energia_dia(med.prefijo)),
    )


def ruta_combinado_por_prefijo(prefijo: str) -> Path | None:
    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        legacy = _legacy_combinado(prefijo)
        return legacy if legacy.exists() else None
    return _resolver_ruta(med.ruta_combinado(), _legacy_combinado(med.prefijo))


def ruta_energia_dia_por_prefijo(prefijo: str) -> Path | None:
    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        legacy = _legacy_energia_dia(prefijo)
        return legacy if legacy.exists() else None
    return _resolver_ruta(med.ruta_energia_dia(), _legacy_energia_dia(med.prefijo))


def ruta_acumulados_por_prefijo(prefijo: str) -> Path | None:
    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        legacy = _legacy_acumulados(prefijo)
        return legacy if legacy.exists() else None
    return _resolver_ruta(med.ruta_acumulados(), _legacy_acumulados(med.prefijo))

