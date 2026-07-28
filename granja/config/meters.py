"""Catálogo lógico de los 21 MEGAs (seriales alineados con catalog_medidores)."""

from __future__ import annotations

from dataclasses import dataclass

from granja.config import GRUPO_GENERACION


@dataclass(frozen=True)
class Mega:
    nombre: str
    numero_serie: str
    etiqueta: str


# Orden operativo Mega01…Mega21 (mismo serial que DineroMegas / catálogo BESS).
MEGAS: tuple[Mega, ...] = (
    Mega("Mega01", "CYM769 VL2E 17NB", "MEGA 1"),
    Mega("Mega02", "CS0008 VL2E 17NB", "MEGA 2"),
    Mega("Mega03", "CS0003 VL2E 17NB", "MEGA 3"),
    Mega("Mega04", "00000000000009SI0402R048", "MEGA 4"),
    Mega("Mega05", "CYM775 VL2E 17NB", "MEGA 5"),
    Mega("Mega06", "CS0002 VL2E 17NB", "MEGA 6"),
    Mega("Mega07", "CS0007 VL2E 17NB", "MEGA 7"),
    Mega("Mega08", "CS0005 VL2E 17NB", "MEGA 8"),
    Mega("Mega09", "CS0004 VL2E 17NB", "MEGA 9"),
    Mega("Mega10", "CS0000 VL2E 17NB", "MEGA 10"),
    Mega("Mega11", "CS0490 VL2E 19NB", "MEGA 11"),
    Mega("Mega12", "CS0489 VL2E 19NB", "MEGA 12"),
    Mega("Mega13", "CS0492 VL2E 19NB", "MEGA 13"),
    Mega("Mega14", "CS0491 VL2E 19NB", "MEGA 14"),
    Mega("Mega15", "CS0475 VL2E 19NB", "MEGA 15"),
    Mega("Mega16", "CS0473 VL2E 19NB", "MEGA 16"),
    Mega("Mega17", "CS0474 VL2E 19NB", "MEGA 17"),
    Mega("Mega18", "CS0476 VL2E 19NB", "MEGA 18"),
    Mega("Mega19", "CS0496 VL2E 19NB", "MEGA 19"),
    Mega("Mega20", "CS0495 VL2E 19NB", "MEGA 20"),
    Mega("Mega21", "CS0493 VL2E 19NB", "MEGA 21"),
)

NOMBRES_MEGA: tuple[str, ...] = tuple(m.nombre for m in MEGAS)
ETIQUETAS_POR_NOMBRE: dict[str, str] = {m.nombre: m.etiqueta for m in MEGAS}
SERIES_POR_NOMBRE: dict[str, str] = {m.nombre: m.numero_serie for m in MEGAS}


def mega_por_nombre(nombre: str) -> Mega | None:
    clave = (nombre or "").strip()
    for mega in MEGAS:
        if mega.nombre == clave:
            return mega
    return None


def nombres_grupo_generacion() -> tuple[str, ...]:
    """Nombres en catálogo BESS con Grupo_Generacion = Generacion_IUSA_2."""
    try:
        from bess.config.catalog import obtener_catalogo

        cat = obtener_catalogo()
        del_catalogo = tuple(
            m.nombre
            for m in cat.medidores
            if (m.grupo_generacion or "").strip() == GRUPO_GENERACION
        )
        if del_catalogo:
            return del_catalogo
    except Exception:
        pass
    return NOMBRES_MEGA
