"""Catálogo de tarifas CFE públicas (Hogar / Negocio / Industria)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FamiliaForm(str, Enum):
    """Familias de formularios ASP.NET en app.cfe.mx."""

    T1 = "t1"  # Año + MesVerano1_ddMesConsulta (Tarifa 1, 9CU)
    VERANO = "verano"  # Año + inicio verano + mes (1A–1F)
    DAC = "dac"  # Año + Fecha1_ddMes
    AGRICOLA_9N = "9n"  # Fecha1_ddAnio + MesVerano1_ddMesConsulta
    GEO = "geo"  # Año + Fecha2_ddMes + Estado/Mpo/División


BASE_CASA = "https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCRECasa/Tarifas"
BASE_NEGOCIO = "https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCRENegocio/Tarifas"
BASE_INDUSTRIA = "https://app.cfe.mx/Aplicaciones/CCFE/Tarifas/TarifasCREIndustria/Tarifas"


@dataclass(frozen=True)
class TarifaCFEDef:
    codigo: str
    nombre: str
    categoria: str  # Hogar | Negocio | Industria | Agrícola
    url: str
    familia: FamiliaForm
    descripcion: str = ""
    requiere_geo: bool = False
    requiere_inicio_verano: bool = False
    # Preferir URL de Negocio cuando hay espejo Industria.
    hub: str = ""


def _t(
    codigo: str,
    nombre: str,
    categoria: str,
    base: str,
    archivo: str,
    familia: FamiliaForm,
    *,
    descripcion: str = "",
    geo: bool = False,
    verano: bool = False,
) -> TarifaCFEDef:
    return TarifaCFEDef(
        codigo=codigo,
        nombre=nombre,
        categoria=categoria,
        url=f"{base}/{archivo}",
        familia=familia,
        descripcion=descripcion,
        requiere_geo=geo,
        requiere_inicio_verano=verano,
        hub=categoria,
    )


# Catálogo completo enlazado desde hubs CRE (sin EA CMS).
TARIFAS_CFE: tuple[TarifaCFEDef, ...] = (
    # —— Hogar ——
    _t("1", "Tarifa 1", "Hogar", BASE_CASA, "Tarifa1.aspx", FamiliaForm.T1,
       descripcion="Doméstica básica (bloques básico / intermedio / excedente)."),
    _t("1A", "Tarifa 1A", "Hogar", BASE_CASA, "Tarifa1A.aspx", FamiliaForm.VERANO,
       descripcion="Doméstica · temperatura verano ≥ 25 °C.", verano=True),
    _t("1B", "Tarifa 1B", "Hogar", BASE_CASA, "Tarifa1B.aspx", FamiliaForm.VERANO,
       descripcion="Doméstica · temperatura verano ≥ 28 °C.", verano=True),
    _t("1C", "Tarifa 1C", "Hogar", BASE_CASA, "Tarifa1C.aspx", FamiliaForm.VERANO,
       descripcion="Doméstica · temperatura verano ≥ 30 °C.", verano=True),
    _t("1D", "Tarifa 1D", "Hogar", BASE_CASA, "Tarifa1D.aspx", FamiliaForm.VERANO,
       descripcion="Doméstica · temperatura verano ≥ 31 °C.", verano=True),
    _t("1E", "Tarifa 1E", "Hogar", BASE_CASA, "Tarifa1E.aspx", FamiliaForm.VERANO,
       descripcion="Doméstica · temperatura verano ≥ 32 °C.", verano=True),
    _t("1F", "Tarifa 1F", "Hogar", BASE_CASA, "Tarifa1F.aspx", FamiliaForm.VERANO,
       descripcion="Doméstica · temperatura verano ≥ 33 °C.", verano=True),
    _t("DAC", "Tarifa DAC", "Hogar", BASE_CASA, "TarifaDAC.aspx", FamiliaForm.DAC,
       descripcion="Doméstica de alto consumo (por región)."),
    # —— Agrícola (estímulo; ASPX bajo Negocio) ——
    _t("9CU", "Tarifa 9 Cargo Único", "Agrícola", BASE_NEGOCIO, "AgricolaCargoUnico.aspx",
       FamiliaForm.T1, descripcion="Riego agrícola · cargo único $/kWh."),
    _t("9N", "Tarifa 9 Nocturna", "Agrícola", BASE_NEGOCIO, "AgricolaNocturna.aspx",
       FamiliaForm.AGRICOLA_9N, descripcion="Riego agrícola · diurno / nocturno."),
    # —— Negocio ——
    _t("PDBT", "Pequeña demanda BT", "Negocio", BASE_NEGOCIO, "PequenaDemandaBT.aspx",
       FamiliaForm.GEO, descripcion="Hasta 25 kW-mes (ex-tarifa 2).", geo=True),
    _t("GDBT", "Gran demanda BT", "Negocio", BASE_NEGOCIO, "GranDemandaBT.aspx",
       FamiliaForm.GEO, descripcion="Mayor a 25 kW-mes (ex-tarifa 3).", geo=True),
    _t("GDMTO", "Gran demanda MT ordinaria", "Negocio", BASE_NEGOCIO, "GranDemandaMTO.aspx",
       FamiliaForm.GEO, descripcion="Media tensión · demanda < 100 kW.", geo=True),
    _t("GDMTH", "Gran demanda MT horaria", "Negocio", BASE_NEGOCIO, "GranDemandaMTH.aspx",
       FamiliaForm.GEO, descripcion="Media tensión · demanda ≥ 100 kW.", geo=True),
    _t("APBT", "Alumbrado público BT", "Negocio", BASE_NEGOCIO, "AlumbradoPublicoBT.aspx",
       FamiliaForm.GEO, descripcion="Alumbrado público en baja tensión.", geo=True),
    _t("APMT", "Alumbrado público MT", "Negocio", BASE_NEGOCIO, "AlumbradoPublicoMT.aspx",
       FamiliaForm.GEO, descripcion="Alumbrado público en media tensión.", geo=True),
    _t("RABT", "Riego agrícola BT", "Agrícola", BASE_NEGOCIO, "RiegoAgricolaBT.aspx",
       FamiliaForm.GEO, descripcion="Riego agrícola en baja tensión.", geo=True),
    _t("RAMT", "Riego agrícola MT", "Agrícola", BASE_NEGOCIO, "RiegoAgricolaMT.aspx",
       FamiliaForm.GEO, descripcion="Riego agrícola en media tensión.", geo=True),
    # —— Industria ——
    _t("DIST", "Demanda industrial subtransmisión", "Industria", BASE_INDUSTRIA,
       "DemandaIndustrialSub.aspx", FamiliaForm.GEO,
       descripcion="Alta tensión · subtransmisión (IUSA 1/2).", geo=True),
    _t("DIT", "Demanda industrial transmisión", "Industria", BASE_INDUSTRIA,
       "DemandaIndustrialTran.aspx", FamiliaForm.GEO,
       descripcion="Alta tensión · transmisión.", geo=True),
)

CATEGORIAS = ("Hogar", "Negocio", "Industria", "Agrícola")

# Meses válidos como inicio de temporada de verano (páginas 1A–1F).
INICIOS_VERANO = (
    "FEBRERO",
    "MARZO",
    "ABRIL",
    "MAYO",
)


def tarifas_por_categoria(categoria: str) -> list[TarifaCFEDef]:
    return [t for t in TARIFAS_CFE if t.categoria == categoria]


def tarifa_por_codigo(codigo: str) -> TarifaCFEDef | None:
    clave = (codigo or "").strip().upper()
    for t in TARIFAS_CFE:
        if t.codigo.upper() == clave:
            return t
    return None


def catalogo_dict() -> list[dict[str, str]]:
    return [
        {
            "codigo": t.codigo,
            "nombre": t.nombre,
            "categoria": t.categoria,
            "familia": t.familia.value,
            "url": t.url,
            "geo": "sí" if t.requiere_geo else "no",
            "verano": "sí" if t.requiere_inicio_verano else "no",
        }
        for t in TARIFAS_CFE
    ]
