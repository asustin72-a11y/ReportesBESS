"""Validación de medidores tras sincronización (columna Validado)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bess.config.catalog import marcar_grupo_generacion_validado, marcar_medidor_validado
from bess.data.ingest.ion import db
from bess.data.ingest.medidor_ids import MEDIDOR_GENERACION_IUSA2


@dataclass
class ResultadoValidacionSync:
    exito: bool
    mensaje: str
    marcados: list[str] = field(default_factory=list)
    pendientes_ion: list[str] = field(default_factory=list)


def _item_sin_error(item: dict[str, Any] | None) -> bool:
    return bool(item) and "error" not in item


def _primer_error_api(api_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in api_items:
        if "error" in item:
            return item
    return None


def detectar_fallo_sync(
    *,
    api_items: list[dict[str, Any]],
    granja_item: dict[str, Any] | None,
    incluir_api: bool = True,
    incluir_granja: bool = True,
) -> str | None:
    """Mensaje de aviso si API/granja fallaron (soft-fail: el sync puede seguir a export)."""
    if incluir_api:
        err = _primer_error_api(api_items)
        if err:
            med = err.get("medidor", "?")
            return f"API: aviso — {med} — {err.get('error', 'error API')}"
    if incluir_granja and granja_item and "error" in granja_item:
        med = granja_item.get("medidor", MEDIDOR_GENERACION_IUSA2)
        return f"Granja: aviso — {med} — {granja_item.get('error', 'error granja')}"
    return None


def aplicar_validacion_post_sync(
    *,
    ion_no_disponible: bool,
    ion_iusa2_no_disponible: bool,
    api_items: list[dict[str, Any]],
    granja_item: dict[str, Any] | None,
    export_ok: bool,
    incluir_ion: bool = True,
    incluir_ion_iusa2: bool = True,
    incluir_api: bool = True,
    incluir_granja: bool = True,
) -> ResultadoValidacionSync:
    """
    Tras sync + export OK, escribe Validado en Medidores.csv.
    ION/API/granja no disponibles: no marca esos medidores pero no invalida el resto
    (soft-fail: el export ya corrió).
    """
    if not export_ok:
        return ResultadoValidacionSync(
            False,
            "Exportación a ArchivosFuente falló; no se actualizó Validado.",
        )

    marcados: list[str] = []
    pendientes_ion: list[str] = []
    avisos: list[str] = []

    if incluir_ion:
        if ion_no_disponible:
            pendientes_ion.append(db.MEDIDOR_ION)
        else:
            if marcar_medidor_validado(db.MEDIDOR_ION):
                marcados.append(db.MEDIDOR_ION)

    if incluir_ion_iusa2:
        if ion_iusa2_no_disponible:
            pendientes_ion.append(db.MEDIDOR_ION_IUSA2)
        else:
            if marcar_medidor_validado(db.MEDIDOR_ION_IUSA2):
                marcados.append(db.MEDIDOR_ION_IUSA2)

    if incluir_api:
        err_api = _primer_error_api(api_items)
        if err_api:
            avisos.append(
                f"API pendiente ({err_api.get('medidor', '?')}): "
                f"{err_api.get('error', 'error')}"
            )
        for item in api_items:
            if _item_sin_error(item):
                nombre = str(item.get("medidor", ""))
                if nombre and marcar_medidor_validado(nombre):
                    marcados.append(nombre)

    if incluir_granja:
        if granja_item and "error" in granja_item:
            avisos.append(
                f"Granja pendiente: {granja_item.get('error', 'error')}"
            )
        elif _item_sin_error(granja_item):
            for nombre in marcar_grupo_generacion_validado("Generacion_IUSA_2"):
                if nombre not in marcados:
                    marcados.append(nombre)

    mensaje = f"Validado actualizado ({len(marcados)} medidor(es))."
    if pendientes_ion:
        mensaje += f" ION sin conexión (pendiente): {', '.join(pendientes_ion)}."
    if avisos:
        mensaje += " " + " · ".join(avisos)
    return ResultadoValidacionSync(True, mensaje, marcados=marcados, pendientes_ion=pendientes_ion)
