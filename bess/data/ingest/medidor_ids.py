"""IDs de medidor en SQLite alineados con Medidores.csv (Nombre)."""

from __future__ import annotations

from pathlib import Path

# Mapeo único de migración: IDs legacy en perfil_carga → Nombre del catálogo.
LEGACY_A_NOMBRE: dict[str, str] = {
    "ION": "ION_Testigo_IUSA1",
    "BESS": "BESS_NORTE",
    "BANCO": "Banco_1",
    "ION_IUSA2": "ION_TESTIGO_IUSA2",
    "BESS_IUSA2": "BESS_SUR",
    "GRANJA_IUSA2": "Generacion_IUSA_2",
}

NOMBRE_A_LEGACY: dict[str, str] = {v: k for k, v in LEGACY_A_NOMBRE.items()}

# Medidores lógicos (constantes de aplicación)
MEDIDOR_ION = "ION_Testigo_IUSA1"
MEDIDOR_ION_IUSA2 = "ION_TESTIGO_IUSA2"
MEDIDOR_BESS = "BESS_NORTE"
MEDIDOR_BANCO = "Banco_1"
MEDIDOR_BESS_IUSA2 = "BESS_SUR"
MEDIDOR_GENERACION_IUSA2 = "Generacion_IUSA_2"
MEDIDOR_COGENERACION = "Cogeneracion"

# Alias de compatibilidad con scripts que usan el nombre antiguo de la constante.
MEDIDOR_GRANJA_IUSA2 = MEDIDOR_GENERACION_IUSA2

MEDIDORES_RELLENAR_MEDIANOCHE_API = frozenset({
    MEDIDOR_BESS,
    MEDIDOR_BANCO,
    MEDIDOR_BESS_IUSA2,
    MEDIDOR_GENERACION_IUSA2,
    MEDIDOR_COGENERACION,
})

FUENTE_MEDIANOCHE_API: dict[str, str] = {
    MEDIDOR_GENERACION_IUSA2: "farm_api",
}


def medidor_id_canonico(medidor_id: str) -> str:
    """Resuelve un ID legacy o de catálogo al Nombre canónico."""
    clave = (medidor_id or "").strip()
    return LEGACY_A_NOMBRE.get(clave, clave)


def es_id_legacy(medidor_id: str) -> bool:
    return (medidor_id or "").strip() in LEGACY_A_NOMBRE


def construir_medidores_catalogo_bd() -> tuple[tuple, ...]:
    """
    Filas para tabla medidores: (id, nombre, tipo, ip, dr_modulo, intervalo_min, activo).
    Incluye medidores individuales del catálogo + agregado Generacion_IUSA_2.
    """
    from bess.config.catalog import (
        TIPO_BESS,
        TIPO_COGENERACION,
        TIPO_FACTURACION,
        TIPO_TESTIGO,
        obtener_catalogo,
    )

    cat = obtener_catalogo()
    filas: list[tuple] = []

    for m in cat.medidores:
        if m.tipo_medidor not in (TIPO_FACTURACION, TIPO_TESTIGO, TIPO_BESS, TIPO_COGENERACION):
            continue
        if m.descarga == "ION":
            tipo = "ION8650"
            ip = m.ip if m.ip and m.ip != "0" else None
            dr = 1
        elif m.es_bess:
            tipo = "BESS"
            ip = None
            dr = None
        elif m.es_cogeneracion:
            tipo = "COGENERACION"
            ip = None
            dr = None
        else:
            tipo = "BANCO"
            ip = None
            dr = None
        etiqueta = f"{m.nombre} · Subestación {m.subestacion_nombre.replace('_', ' ')}"
        filas.append((m.nombre, etiqueta, tipo, ip, dr, 5, 1))

    filas.append((
        MEDIDOR_GENERACION_IUSA2,
        "Generación · Subestación IUSA 2 (20 MEGA)",
        "GRANJA",
        None,
        None,
        5,
        1,
    ))
    return tuple(filas)


def destinos_export_bd(ruta_bd: Path | None = None) -> list[tuple[str, Path]]:
    """(medidor_id, ruta_csv) para exportar SQLite → ArchivosFuente/{Subestacion}/."""
    from bess.config import rutas as rutas_mod
    from bess.config.catalog import (
        TIPO_BESS,
        TIPO_COGENERACION,
        TIPO_FACTURACION,
        TIPO_TESTIGO,
        obtener_catalogo,
    )

    cat = obtener_catalogo()
    destinos: list[tuple[str, Path]] = []
    for m in cat.medidores:
        if m.tipo_medidor in (TIPO_FACTURACION, TIPO_TESTIGO, TIPO_BESS, TIPO_COGENERACION):
            destinos.append((
                m.nombre,
                rutas_mod.ruta_fuente_medidor(m.nombre, m.subestacion_nombre),
            ))
    destinos.append((
        MEDIDOR_GENERACION_IUSA2,
        rutas_mod.ruta_fuente("IUSA_2", rutas_mod.nombre_generacion_subestacion("IUSA_2")),
    ))
    return destinos


def resolver_medidor_bd_desde_api(medidor: str) -> str:
    """Alias API o nombre de catálogo → medidor_id canónico en SQLite."""
    from bess.config.subestaciones import aliases_sync_api

    clave = (medidor or "").strip()
    clave_lower = clave.lower()
    for alias, nombre in aliases_sync_api():
        if alias.lower() == clave_lower or nombre.lower() == clave_lower:
            return nombre
    return medidor_id_canonico(clave)
