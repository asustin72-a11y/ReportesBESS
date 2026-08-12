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
from bess.config.paths import (
    DIRECTORIO_PROCESADOS,
    DIRECTORIO_REPORTES,
    DIRECTORIO_REPORTES_DIARIOS,
    RUTA_BD_PERFILES,
)
from bess.config.subestaciones import subestacion_por_id
from bess.data.ingest.ion.export_csv import exportar
from bess.data.ingest.medidor_ids import (
    MEDIDOR_GENERACION_IUSA2,
    destinos_export_bd,
)


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


def _archivos_cadena_granja(sub_id: str = "IUSA_2") -> list[Path]:
    """CSV derivados del agregado Generacion_{sub} (granja / MEGAs)."""
    sub = subestacion_por_id(sub_id)
    if not sub or not sub.granja_bd:
        return []
    prefijo = sub.granja_bd
    return [
        sub.ruta_generacion(filtrado=False),
        sub.ruta_generacion(filtrado=True),
        rutas_mod.ruta_procesado_medidor(prefijo, sub_id, filtrado=False),
        rutas_mod.ruta_procesado_medidor(prefijo, sub_id, filtrado=True),
        rutas_mod.ruta_reporte(sub_id, f"COMBINADO_POR_MINUTO_{prefijo}.csv"),
        rutas_mod.ruta_energia_por_dia(prefijo, sub_id),
        rutas_mod.ruta_reporte(sub_id, f"ENERGIA_Generacion_{sub_id}_POR_DIA.csv"),
    ]


def _archivos_cadena_medidor(medidor_id: str, sub_id: str, tipo: int | None) -> list[Path]:
    """CSV derivados a borrar para forzar reproceso completo del tramo."""
    if medidor_id == MEDIDOR_GENERACION_IUSA2:
        return _archivos_cadena_granja("IUSA_2")

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
    elif tipo == TIPO_COGENERACION or any(
        g.nombre == medidor_id for g in sub.medidores_gen_individual
    ):
        gen = next(
            (g for g in sub.medidores_gen_individual if g.nombre == medidor_id),
            None,
        )
        if gen is None and sub.cogeneracion_nombre:
            gen_nombre = sub.cogeneracion_nombre
        elif gen is not None:
            gen_nombre = gen.nombre
        else:
            gen_nombre = None
        if gen_nombre:
            rutas.append(
                rutas_mod.ruta_procesado_medidor(gen_nombre, sub_id, filtrado=False)
            )
            rutas.append(
                rutas_mod.ruta_procesado_medidor(gen_nombre, sub_id, filtrado=True)
            )
            rutas.append(
                rutas_mod.ruta_reporte(sub_id, f"COMBINADO_POR_MINUTO_{gen_nombre}.csv")
            )
            rutas.append(rutas_mod.ruta_energia_por_dia(gen_nombre, sub_id))
            rutas.append(
                rutas_mod.ruta_reporte(
                    sub_id, f"ENERGIA_Generacion_{sub_id}_POR_DIA.csv"
                )
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


def _listar_csv_derivados_globales() -> list[Path]:
    """Todos los CSV bajo Procesados / Reporte / ReportesDiarios."""
    encontrados: list[Path] = []
    for raiz in (DIRECTORIO_PROCESADOS, DIRECTORIO_REPORTES, DIRECTORIO_REPORTES_DIARIOS):
        if not raiz.is_dir():
            continue
        encontrados.extend(sorted(raiz.rglob("*.csv")))
    return encontrados


def plan_rebuild_csv(medidor_id: str, desde: date | str) -> PlanRebuildCsv:
    """Arma el plan de rebuild (no escribe ni borra)."""
    desde_txt = desde.isoformat() if isinstance(desde, date) else str(desde).strip()
    desde_txt = desde_txt[:10]

    cat = obtener_catalogo()
    med = cat.medidor_por_nombre(medidor_id)
    if medidor_id == MEDIDOR_GENERACION_IUSA2:
        sub_id = "IUSA_2"
        tipo = None
    else:
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


def plan_rebuild_csv_todos(desde: date | str) -> dict:
    """Vista previa del rebuild total (todos los medidores exportables)."""
    desde_txt = desde.isoformat() if isinstance(desde, date) else str(desde).strip()
    desde_txt = desde_txt[:10]
    medidores = [mid for mid, _ in destinos_export_bd(RUTA_BD_PERFILES)]
    planes = [plan_rebuild_csv(mid, desde_txt) for mid in medidores]
    csv_globales = _listar_csv_derivados_globales()
    return {
        "desde": desde_txt,
        "medidores": medidores,
        "n_medidores": len(medidores),
        "n_csv_derivados_a_borrar": len(csv_globales),
        "csv_derivados_muestra": [str(p) for p in csv_globales[:40]],
        "avisos": [
            "SQLite solo lectura.",
            f"Reexporta {len(medidores)} medidor(es) a ArchivosFuente desde {desde_txt}.",
            "Borra TODOS los CSV de ArchivosProcesados, ArchivosReporte y ReportesDiarios.",
            "Luego ejecuta Verificar → Filtrar → Generar reportes (completo).",
            "Puede tardar varios minutos según el histórico en BD.",
        ],
        "planes": [
            {
                "medidor": p.medidor_id,
                "subestacion": p.subestacion_id,
                "ruta_fuente": str(p.ruta_fuente),
            }
            for p in planes
        ],
    }


def _correr_pipeline() -> dict:
    from bess_core import filtrar_datos, reporte_bess, verificar_datos_fuente

    print("\n=== Verificar ===")
    ok_v, msg_v = verificar_datos_fuente()
    print(f"Verificar: {'OK' if ok_v else 'ERROR'} — {msg_v}")
    if not ok_v:
        return {
            "verificar_ok": False,
            "verificar_msg": msg_v,
            "filtrar_ok": False,
            "reportes_ok": False,
        }

    print("\n=== Filtrar ===")
    ok_f, msg_f = filtrar_datos()
    print(f"Filtrar: {'OK' if ok_f else 'ERROR'} — {msg_f}")
    if not ok_f:
        return {
            "verificar_ok": True,
            "verificar_msg": msg_v,
            "filtrar_ok": False,
            "filtrar_msg": msg_f,
            "reportes_ok": False,
        }

    print("\n=== Reportes ===")
    ok_r, msgs_r = reporte_bess()
    print(f"Reportes: {'OK' if ok_r else 'PARCIAL/ERROR'}")
    return {
        "verificar_ok": True,
        "verificar_msg": msg_v,
        "filtrar_ok": True,
        "filtrar_msg": msg_f,
        "reportes_ok": ok_r,
        "reportes_msgs": msgs_r,
    }


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
            pipeline = _correr_pipeline()
            resultado.update(pipeline)
            if not pipeline.get("reportes_ok"):
                resultado["log"] = log.getvalue()
                return resultado

    resultado["ok"] = True
    resultado["log"] = log.getvalue()
    return resultado


def ejecutar_rebuild_csv_todos(
    desde: date | str,
    *,
    procesar: bool = True,
) -> dict:
    """
    Rebuild total: reexporta TODOS los medidores exportables desde `desde`,
    borra CSV derivados globales y regenera Verificar → Filtrar → Reportes.
    SQLite no se modifica.
    """
    desde_txt = desde.isoformat() if isinstance(desde, date) else str(desde).strip()
    desde_txt = desde_txt[:10]
    destinos = destinos_export_bd(RUTA_BD_PERFILES)
    log = io.StringIO()
    resultado: dict = {
        "ok": False,
        "desde": desde_txt,
        "medidores": [mid for mid, _ in destinos],
        "exportados_ok": [],
        "exportados_sin_datos": [],
        "borrados": [],
        "log": "",
    }

    with redirect_stdout(log):
        print(f"=== Rebuild TOTAL desde BD · desde {desde_txt} ===")
        print(f"Medidores: {len(destinos)}")
        print("(SQLite: solo lectura)")

        for medidor_id, ruta_fuente in destinos:
            print(f"\n--- Export {medidor_id} → {ruta_fuente.name} ---")
            rc = exportar(
                RUTA_BD_PERFILES,
                medidor_id,
                ruta_fuente,
                desde=desde_txt,
                quiet=False,
            )
            if rc == 0:
                resultado["exportados_ok"].append(medidor_id)
            else:
                print(f"  (omitido / sin datos: rc={rc})")
                resultado["exportados_sin_datos"].append(medidor_id)

        print("\n=== Borrando CSV derivados (Procesados / Reporte / ReportesDiarios) ===")
        borrados: list[str] = []
        for ruta in _listar_csv_derivados_globales():
            try:
                ruta.unlink()
                borrados.append(str(ruta))
                print(f"  borrado: {ruta}")
            except OSError as exc:
                print(f"  no se pudo borrar {ruta}: {exc}")
        resultado["borrados"] = borrados
        print(f"Total borrados: {len(borrados)}")

        if not resultado["exportados_ok"]:
            print("ERROR: ningún medidor se exportó; abortado sin pipeline.")
            resultado["log"] = log.getvalue()
            return resultado

        if procesar:
            pipeline = _correr_pipeline()
            resultado.update(pipeline)
            resultado["ok"] = bool(pipeline.get("reportes_ok"))
        else:
            resultado["ok"] = True
            print("Pipeline omitido (procesar=False).")

    resultado["log"] = log.getvalue()
    return resultado
