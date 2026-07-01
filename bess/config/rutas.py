"""Rutas y nombres de archivo por subestación (catálogo CSV)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from bess.config.paths import (
    DIRECTORIO_FUENTE,
    DIRECTORIO_PROCESADOS,
    DIRECTORIO_REPORTES,
    DIRECTORIO_REPORTES_DIARIOS,
)

# Archivos planos legacy en ArchivosProcesados/ (pre-Fase 4)
_LEGACY_PROCESADO_PLANO: dict[str, str] = {
    "ION_Testigo_IUSA1.csv": "ION.csv",
    "ION_Testigo_IUSA1_Filtrado.csv": "ION_Filtrado.csv",
    "Banco_1.csv": "Banco1.csv",
    "Banco_1_Filtrado.csv": "Banco1_Filtrado.csv",
    "BESS_NORTE.csv": "BESS.csv",
    "BESS_NORTE_Filtrado.csv": "BESS_Filtrado.csv",
    "ION_TESTIGO_IUSA2.csv": "ION_IUSA2.csv",
    "ION_TESTIGO_IUSA2_Filtrado.csv": "ION_IUSA2_Filtrado.csv",
    "BESS_SUR.csv": "BESS_IUSA2.csv",
    "BESS_SUR_Filtrado.csv": "BESS_IUSA2_Filtrado.csv",
    "BESS_IUSA_1.csv": "BESS.csv",
    "BESS_IUSA_1_Filtrado.csv": "BESS_Filtrado.csv",
    "BESS_IUSA_2.csv": "BESS_IUSA2.csv",
    "BESS_IUSA_2_Filtrado.csv": "BESS_IUSA2_Filtrado.csv",
    "Generacion_IUSA_2.csv": "GRANJA_IUSA2.csv",
    "Generacion_IUSA_2_Filtrado.csv": "GRANJA_IUSA2_Filtrado.csv",
}


def resolver_ruta_procesado(ruta_nueva: Path) -> Path:
    """Nueva ruta por subestación; si no existe, busca CSV plano legacy."""
    if ruta_nueva.exists():
        return ruta_nueva
    legado = _LEGACY_PROCESADO_PLANO.get(ruta_nueva.name)
    if legado:
        plano = DIRECTORIO_PROCESADOS / legado
        if plano.exists():
            return plano
    return ruta_nueva


def dir_subestacion(base: Path, subestacion: str) -> Path:
    return base / subestacion


def nombre_archivo_medidor(nombre: str) -> str:
    return f"{nombre}.csv"


def nombre_archivo_filtrado(nombre: str) -> str:
    return f"{nombre}_Filtrado.csv"


def nombre_bess_subestacion(subestacion: str) -> str:
    return f"BESS_{subestacion}.csv"


def nombre_bess_subestacion_filtrado(subestacion: str) -> str:
    return f"BESS_{subestacion}_Filtrado.csv"


def nombre_generacion_subestacion(subestacion: str) -> str:
    return f"Generacion_{subestacion}.csv"


def nombre_generacion_subestacion_filtrado(subestacion: str) -> str:
    return f"Generacion_{subestacion}_Filtrado.csv"


def nombre_combinado_minuto(nombre_medidor: str, subestacion: str) -> str:
    return f"COMBINADO_POR_MINUTO_{nombre_medidor}_{subestacion}.csv"


def nombre_energia_por_dia(nombre_medidor: str, subestacion: str) -> str:
    return f"ENERGIA_{nombre_medidor}_{subestacion}_POR_DIA.csv"


def nombre_acumulados(nombre_medidor: str, subestacion: str) -> str:
    return f"ACUMULADOS_{nombre_medidor}_{subestacion}.csv"


def nombre_energia_bess_por_dia(subestacion: str) -> str:
    return f"ENERGIA_BESS_{subestacion}_POR_DIA.csv"


def nombre_pdf_diario(nombre_medidor: str, fecha: datetime) -> str:
    return f"{nombre_medidor}_{fecha.strftime('%d_%m_%Y')}.pdf"


def ruta_fuente(subestacion: str, nombre_archivo: str) -> Path:
    return dir_subestacion(DIRECTORIO_FUENTE, subestacion) / nombre_archivo


def ruta_procesado(subestacion: str, nombre_archivo: str) -> Path:
    return dir_subestacion(DIRECTORIO_PROCESADOS, subestacion) / nombre_archivo


def ruta_reporte(subestacion: str, nombre_archivo: str) -> Path:
    return dir_subestacion(DIRECTORIO_REPORTES, subestacion) / nombre_archivo


def ruta_pdf_diario(subestacion: str, nombre_archivo: str) -> Path:
    return dir_subestacion(DIRECTORIO_REPORTES_DIARIOS, subestacion) / nombre_archivo


def ruta_fuente_medidor(nombre: str, subestacion: str) -> Path:
    return ruta_fuente(subestacion, nombre_archivo_medidor(nombre))


def ruta_procesado_medidor(nombre: str, subestacion: str, *, filtrado: bool = False) -> Path:
    archivo = nombre_archivo_filtrado(nombre) if filtrado else nombre_archivo_medidor(nombre)
    return ruta_procesado(subestacion, archivo)


def ruta_bess_subestacion(subestacion: str, *, filtrado: bool = False) -> Path:
    archivo = (
        nombre_bess_subestacion_filtrado(subestacion)
        if filtrado
        else nombre_bess_subestacion(subestacion)
    )
    return ruta_procesado(subestacion, archivo)


def ruta_generacion_subestacion(subestacion: str, *, filtrado: bool = False) -> Path:
    archivo = (
        nombre_generacion_subestacion_filtrado(subestacion)
        if filtrado
        else nombre_generacion_subestacion(subestacion)
    )
    return ruta_procesado(subestacion, archivo)


def ruta_combinado_minuto(nombre_medidor: str, subestacion: str) -> Path:
    return ruta_reporte(
        subestacion,
        nombre_combinado_minuto(nombre_medidor, subestacion),
    )


def ruta_energia_por_dia(nombre_medidor: str, subestacion: str) -> Path:
    return ruta_reporte(
        subestacion,
        nombre_energia_por_dia(nombre_medidor, subestacion),
    )


def ruta_acumulados(nombre_medidor: str, subestacion: str) -> Path:
    return ruta_reporte(subestacion, nombre_acumulados(nombre_medidor, subestacion))


def ruta_energia_bess_por_dia(subestacion: str) -> Path:
    return ruta_reporte(subestacion, nombre_energia_bess_por_dia(subestacion))


def ruta_fuente_por_nombre_archivo(nombre_archivo: str) -> Path | None:
    """Resuelve ArchivosFuente/{Subestacion}/{Nombre}.csv desde el nombre del archivo."""
    from bess.config.catalog import obtener_catalogo

    nombre = nombre_archivo.strip()
    if not nombre.lower().endswith(".csv"):
        nombre = f"{nombre}.csv"
    stem = nombre[:-4]
    if stem.endswith("_Filtrado"):
        return None
    cat = obtener_catalogo()
    for m in cat.medidores:
        if m.nombre == stem:
            return ruta_fuente_medidor(m.nombre, m.subestacion_nombre)
    return None


def asegurar_carpetas_subestaciones(subestaciones: list[str]) -> None:
    for sub in subestaciones:
        for base in (
            DIRECTORIO_FUENTE,
            DIRECTORIO_PROCESADOS,
            DIRECTORIO_REPORTES,
            DIRECTORIO_REPORTES_DIARIOS,
        ):
            dir_subestacion(base, sub).mkdir(parents=True, exist_ok=True)


def asegurar_carpetas_desde_catalogo() -> None:
    from bess.config.catalog import obtener_catalogo

    cat = obtener_catalogo()
    asegurar_carpetas_subestaciones([s.nombre for s in cat.subestaciones])
