"""Filtrar ya no debe borrar ArchivosFuente.

Antes, _filtrar_datos_impl() llamaba a limpiar_archivos_fuente() al final
de cada corrida exitosa. Desde que export_csv.py exporta de forma
incremental (Fase 2 del plan CSV->SQLite: cursor sobre la última Fecha ya
exportada), ese borrado anulaba el beneficio incremental -- el cron de 15
minutos encadena Sincronizar -> Verificar -> Filtrar -> Reportes en una
sola corrida (`--procesar`), así que ArchivosFuente se borraba antes de
que el siguiente ciclo pudiera aprovechar el cursor, forzando una
exportación completa cada vez pese al cambio de Fase 2.

Esta prueba corre _filtrar_datos_impl() de verdad (contra los datos reales
ya procesados del repo -- regenerar *_Filtrado.csv es su comportamiento
normal e idempotente) y confirma que limpiar_archivos_fuente() ya no se
invoca automáticamente.
"""

from __future__ import annotations

import bess.data.pipeline.filter as filter_mod


def test_filtrar_no_llama_limpiar_archivos_fuente(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        filter_mod, 'limpiar_archivos_fuente', lambda: llamadas.append(1)
    )

    exito, _mensaje = filter_mod._filtrar_datos_impl()

    assert exito, "la corrida real de Filtrar debia tener exito con los datos ya procesados del repo"
    assert llamadas == [], "limpiar_archivos_fuente() no debe llamarse automaticamente"


def test_limpiar_archivos_fuente_sigue_disponible():
    """La función sigue existiendo para limpieza manual futura, solo se quitó
    la llamada automática -- no se eliminó la capacidad."""
    assert callable(filter_mod.limpiar_archivos_fuente)
