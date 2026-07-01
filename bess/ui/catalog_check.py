"""Validación del catálogo CSV al arrancar la aplicación."""

from __future__ import annotations

import streamlit as st

from bess.config.catalog import CatalogError, invalidar_cache_catalogo, obtener_catalogo


def validar_catalogo_al_arranque() -> bool:
    """
    Carga y valida Medidores/Subestaciones/Tipo_Medidor.
    Muestra errores en pantalla y devuelve False si el catálogo es inválido.
    """
    try:
        obtener_catalogo()
        return True
    except CatalogError as exc:
        st.error("Configuración de medidores inválida (data/Tarifas/*.csv)")
        for msg in exc.errores:
            st.markdown(f"- {msg}")
        st.caption(
            "Corrija los CSV en `data/Tarifas/` y recargue la aplicación. "
            "Vea `Medidores.csv`, `Subestaciones.csv` y `Tipo_Medidor.csv`."
        )
        return False


def medidores_pendientes_validacion() -> list[str]:
    """Nombres de medidores ION/API sin fecha Validado (sync OK)."""
    try:
        catalogo = obtener_catalogo()
    except CatalogError:
        return []
    return [m.nombre for m in catalogo.medidores_sin_validar()]


def puede_generar_reportes() -> tuple[bool, str]:
    """Bloquea generación hasta que todos los medidores tengan Validado."""
    pendientes = medidores_pendientes_validacion()
    if not pendientes:
        return True, ""
    lista = ", ".join(pendientes[:8])
    extra = f" (+{len(pendientes) - 8} más)" if len(pendientes) > 8 else ""
    return (
        False,
        "Todos los medidores deben estar validados (columna Validado en Medidores.csv) "
        f"antes de generar reportes. Pendientes: {lista}{extra}. "
        "Ejecute **Sincronizar** con validación exitosa.",
    )
