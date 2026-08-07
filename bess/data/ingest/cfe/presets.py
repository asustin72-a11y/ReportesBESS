"""Presets BESS (actualización automática) y reexport del catálogo."""

from __future__ import annotations

from dataclasses import dataclass

from bess.config.esquema_tarifa import ESQUEMA_DIST, ESQUEMA_GDMTH, ESQUEMA_PDBT, ESQUEMA_T1
from bess.data.ingest.cfe.catalog import FamiliaForm
from bess.data.ingest.cfe.tarifas_client import (
    ConsultaTarifaCFE,
    ResultadoTarifaCFE,
    consultar_tarifas_cfe,
)

URL_DIST = (
    "https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCREIndustria/"
    "Tarifas/DemandaIndustrialSub.aspx"
)
URL_GDMTH = (
    "https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCRENegocio/"
    "Tarifas/GranDemandaMTH.aspx"
)
URL_PDBT = (
    "https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCRENegocio/"
    "Tarifas/PequenaDemandaBT.aspx"
)
URL_T1 = (
    "https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCRECasa/"
    "Tarifas/Tarifa1.aspx"
)


@dataclass(frozen=True)
class PresetTarifaCFE:
    id: str
    descripcion: str
    esquema_id: str
    url: str
    estado: str = ""
    municipio: str = ""
    division: str = ""
    region_tabla: str | None = None
    familia: FamiliaForm = FamiliaForm.GEO
    codigo_cfe: str = ""


# Presets ligados a medidores/esquemas BESS (cron + CLI legacy).
PRESETS: dict[str, PresetTarifaCFE] = {
    "jocotitlan": PresetTarifaCFE(
        id="jocotitlan",
        descripcion="IUSA 1/2 — DIST Jocotitlán (Centro Sur)",
        esquema_id=ESQUEMA_DIST,
        url=URL_DIST,
        estado="ESTADO DE MÉXICO",
        municipio="JOCOTITLAN",
        division="CENTRO SUR",
        region_tabla="Centro Sur",
        familia=FamiliaForm.GEO,
        codigo_cfe="DIST",
    ),
    "aragon": PresetTarifaCFE(
        id="aragon",
        descripcion="IUSA Aragón — GDMTH Gustavo A. Madero (Valle de México Norte)",
        esquema_id=ESQUEMA_GDMTH,
        url=URL_GDMTH,
        estado="CIUDAD DE MÉXICO",
        municipio="GUSTAVO A. MADERO",
        division="VALLE DE MÉXICO NORTE",
        region_tabla="Valle de México Norte",
        familia=FamiliaForm.GEO,
        codigo_cfe="GDMTH",
    ),
    "miguel_hidalgo": PresetTarifaCFE(
        id="miguel_hidalgo",
        descripcion="PDBT (ex-tarifa 2) — Miguel Hidalgo (Valle de México Norte)",
        esquema_id=ESQUEMA_PDBT,
        url=URL_PDBT,
        estado="CIUDAD DE MÉXICO",
        municipio="MIGUEL HIDALGO",
        division="VALLE DE MÉXICO NORTE",
        region_tabla="Valle de México Norte",
        familia=FamiliaForm.GEO,
        codigo_cfe="PDBT",
    ),
    "tarifa1": PresetTarifaCFE(
        id="tarifa1",
        descripcion="Tarifa 1 / 01 — doméstica (Hogar, nacional)",
        esquema_id=ESQUEMA_T1,
        url=URL_T1,
        familia=FamiliaForm.T1,
        codigo_cfe="1",
    ),
}

# Presets que el cron BESS actualiza automáticamente.
PRESETS_BESS_AUTO = ("jocotitlan", "aragon")


def consultar_preset(
    preset_id: str,
    *,
    anio: int,
    mes: int,
    headless: bool = True,
    timeout_ms: int = 90_000,
) -> ResultadoTarifaCFE:
    preset = PRESETS.get(preset_id.strip().lower())
    if preset is None:
        conocidos = ", ".join(sorted(PRESETS))
        raise KeyError(f"Preset desconocido: {preset_id!r}. Disponibles: {conocidos}")
    consulta = ConsultaTarifaCFE(
        url=preset.url,
        anio=anio,
        mes=mes,
        estado=preset.estado,
        municipio=preset.municipio,
        division=preset.division,
        esquema_id=preset.esquema_id,
        region_tabla=preset.region_tabla,
        familia=preset.familia,
    )
    resultado = consultar_tarifas_cfe(
        consulta, headless=headless, timeout_ms=timeout_ms
    )
    resultado.codigo_tarifa = preset.codigo_cfe or preset.esquema_id
    resultado.nombre_tarifa = preset.descripcion
    return resultado
