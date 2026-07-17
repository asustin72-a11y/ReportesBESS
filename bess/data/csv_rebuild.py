"""Rebuild forzado de la cadena CSV desde SQLite (sin modificar la BD).

Caso de uso: el pipeline incremental (`_MARGEN_REEXPORTAR_DIAS = 1`) dejó
ceros o huecos congelados en Fuente/Procesados/COMBINADO mientras
`perfil_carga` ya tiene valores correctos. Este módulo:

1. Reexporta el medidor desde SQLite → ArchivosFuente (lectura BD).
2. Borra los CSV derivados (procesado, filtrado, consolidado BESS, reportes).
3. Opcionalmente corre verificar → filtrar → reportes.

No escribe en `perfil_carga` ni en `sync_state`.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from bess.config import rutas as rutas_mod
from bess.config.catalog import (
    TIPO_BESS,
    TIPO_COGENERACION,
    TIPO_FACTURACION,
    TIPO_TESTIGO,
    obtener_catalogo,
)
from bess.config.paths import RUTA_BD_PERFILES
from bess.config.subestaciones import subestacion_por_id
from bess.data.ingest.ion.export_csv import exportar
from bess.data.ingest.medidor_ids import destinos_export_bd


@dataclass
class PlanRebuildCsv:
    medidor_id: str
    subestacion_id: str
    tipo_medidor: int | None
    desde: str
    ruta_fuente: Path
    archivos_a_borrar: list[Path] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def resumen_borrado(self) -> list[str]:
        return [str(p) for p in self.archivos_a_borrar if p.exists()]


def _destino_fuente(medidor_id: str) -> Path | None:
    for mid, ruta in destinos_export_bd(RUTA_BD_PERFILES):
        if mid == medidor_id:
            return ruta
    return None


def _archivos_cadena_medidor(medidor_id: str, sub_id: str, tipo: int | None) -> list[Path]:
    """CSV derivados a borrar para forzar reproceso completo del tramo."""
    rutas: list[Path] = [
        rutas_mod.ruta_procesado_medidor(medidor_id, sub_id, filtrado=False),
        rutas_mod.ruta_procesado_medidor(medidor_id, sub_id, filtrado=True),
    ]

    sub = subestacion_por_id(sub_id)
    if sub is None:
        return rutas

    if tipo == TIPO_BESS:
        rutas.append(sub.ruta_bess(filtrado=False))
        rutas.append(sub.ruta_bess(filtrado=True))
        rutas.append(rutas_mod.ruta_energia_bess_por_dia(sub_id))
        for med in sub.medidores_consumo:
            rutas.append(med.ruta_combinado())
            rutas.append(med.ruta_energia_dia())
            rutas.append(med.ruta_acumulados())
    elif tipo in (TIPO_FACTURACION, TIPO_TESTIGO):
        for med in sub.medidores_consumo:
            if med.nombre == medidor_id:
                rutas.append(med.ruta_combinado())
                rutas.append(med.ruta_energia_dia())
                rutas.append(med.ruta_acumulados())
                break
        rutas.append(sub.ruta_bess(filtrado=True))
        rutas.append(rutas_mod.ruta_energia_bess_por_dia(sub_id))
    elif tipo == TIPO_COGENERACION or (
        sub.cogeneracion_nombre and medidor_id == sub.cogeneracion_nombre
    ):
        if sub.cogeneracion_nombre:
            rutas.append(
                rutas_mod.ruta_procesado_medidor(
                    sub.cogeneracion_nombre, sub_id, filtrado=False
                )
            )
            rutas.append(
                rutas_mod.ruta_procesado_medidor(
                    sub.cogeneracion_nombre, sub_id, filtrado=True
                )
            )
            rutas.append(
                rutas_mod.ruta_combinado_minuto(sub.cogeneracion_nombre, sub_id)
            )
            rutas.append(
                rutas_mod.ruta_energia_por_dia(sub.cogeneracion_nombre, sub_id)
            )

    vistos: set[str] = set()
    unicos: list[Path] = []
    for p in rutas:
        key = str(p)
        if key in vistos:
            continue
        vistos.add(key)
        unicos.append(p)
    return unicos


def plan_rebuild_csv(medidor_id: str, desde: date | str) -> PlanRebuildCsv:
    """Arma el plan de rebuild (no escribe ni borra)."""
    desde_txt = desde.isoformat() if isinstance(desde, date) else str(desde).strip()
    desde_txt = desde_txt[:10]

    cat = obtener_catalogo()
    med = cat.medidor_por_nombre(medidor_id)
    sub_id = med.subestacion_nombre if med else ""
    tipo = med.tipo_medidor if med else None

    ruta_fuente = _destino_fuente(medidor_id)
    avisos: list[str] = []
    if ruta_fuente is None:
        avisos.append(
            f"No hay destino de exportación para `{medidor_id}` en el catálogo."
        )
        ruta_fuente = Path(f"(sin destino)/{medidor_id}.csv")
    if not sub_id:
        avisos.append(f"Medidor `{medidor_id}` no encontrado en catálogo.")

    avisos.append(
        "SQLite no se modifica (solo lectura). "
        "La Fuente del medidor se reescribe completa desde la fecha indicada; "
        "filas CSV anteriores a esa fecha se pierden en ArchivosFuente."
    )
    avisos.append(
        "Se borran CSV derivados para saltar la ventana incremental de 1 día "
        "y forzar verify/filter/reportes completos en ese tramo."
    )

    archivos = _archivos_cadena_medidor(medidor_id, sub_id, tipo) if sub_id else []
    return PlanRebuildCsv(
        medidor_id=medidor_id,
        subestacion_id=sub_id or "?",
        tipo_medidor=tipo,
        desde=desde_txt,
        ruta_fuente=ruta_fuente,
        archivos_a_borrar=archivos,
        avisos=avisos,
    )


def ejecutar_rebuild_csv(
    medidor_id: str,
    desde: date | str,
    *,
    procesar: bool = True,
) -> dict:
    """Ejecuta export + borrado de CSV + (opcional) pipeline.

    Returns:
        dict con ok, export_rc, borrados, log, flags de procesar.
    """
    plan = plan_rebuild_csv(medidor_id, desde)
    log = io.StringIO()
    resultado: dict = {
        "ok": False,
        "medidor": medidor_id,
        "desde": plan.desde,
        "ruta_fuente": str(plan.ruta_fuente),
        "export_rc": None,
        "borrados": [],
        "avisos": list(plan.avisos),
        "log": "",
    }

    if _destino_fuente(medidor_id) is None:
        resultado["log"] = "Sin destino de exportación; abortado."
        return resultado

    with redirect_stdout(log):
        print(f"=== Rebuild CSV forzado: {medidor_id} desde {plan.desde} ===")
        print("(SQLite: solo lectura)")
        rc = exportar(
            RUTA_BD_PERFILES,
            medidor_id,
            plan.ruta_fuente,
            desde=plan.desde,
            quiet=False,
        )
        resultado["export_rc"] = rc
        if rc != 0:
            print(f"ERROR: export falló con código {rc}")
            resultado["log"] = log.getvalue()
            return resultado

        borrados: list[str] = []
        for ruta in plan.archivos_a_borrar:
            if ruta.exists():
                ruta.unlink()
                borrados.append(str(ruta))
                print(f"  borrado: {ruta}")
        resultado["borrados"] = borrados

        if procesar:
            print("\n=== Verificar ===")
            from bess_core import filtrar_datos, reporte_bess, verificar_datos_fuente

            ok_v, msg_v = verificar_datos_fuente()
            print(f"Verificar: {'OK' if ok_v else 'ERROR'} — {msg_v}")
            resultado["verificar_ok"] = ok_v
            resultado["verificar_msg"] = msg_v
            if not ok_v:
                resultado["log"] = log.getvalue()
                return resultado

            print("\n=== Filtrar ===")
            ok_f, msg_f = filtrar_datos()
            print(f"Filtrar: {'OK' if ok_f else 'ERROR'} — {msg_f}")
            resultado["filtrar_ok"] = ok_f
            resultado["filtrar_msg"] = msg_f
            if not ok_f:
                resultado["log"] = log.getvalue()
                return resultado

            print("\n=== Reportes ===")
            ok_r, msgs_r = reporte_bess()
            print(f"Reportes: {'OK' if ok_r else 'PARCIAL/ERROR'}")
            resultado["reportes_ok"] = ok_r
            resultado["reportes_msgs"] = msgs_r
            if not ok_r:
                resultado["log"] = log.getvalue()
                return resultado

    resultado["ok"] = True
    resultado["log"] = log.getvalue()
    return resultado
