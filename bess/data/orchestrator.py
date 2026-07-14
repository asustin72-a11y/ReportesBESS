"""Orquestación del pipeline de reportes."""

from __future__ import annotations

import os

from bess.config.constants import etiqueta_medidor
from bess.config.subestaciones import (
    SUBESTACIONES,
    medidor_consumo_por_prefijo,
    recurso_generacion_subestacion,
    ruta_combinado_por_prefijo,
)
from bess.core.consumo import usa_consumo_neto
from bess.core.ui_progress import emit_ui_progress, ui_progress_habilitado
from bess.data.aggregates.accumulated import generar_acumulados
from bess.data.aggregates.bess_daily import generar_bess_diario_subestacion
from bess.data.aggregates.combined import generar_combinado_por_minuto
from bess.data.aggregates.granja import generar_reportes_generacion
from bess.data.aggregates.daily import generar_diarios_con_demandas
from bess.data.ingest.readers import leer_sin_agrupar

from bess.core.console import log

print = log


def _reporte_ui_total() -> int:
    n_grupos = sum(len(s.medidores_consumo) for s in SUBESTACIONES)
    n_gen = sum(1 for s in SUBESTACIONES if recurso_generacion_subestacion(s.id))
    # validar + grupos + BESS diario + generación + cierre
    return 2 + n_grupos + n_gen


def _reporte_ui(step: int, total: int, label: str) -> None:
    if ui_progress_habilitado():
        emit_ui_progress(step, total, label)


def procesar_grupo(ruta_bess, ruta_medidor, prefijo, nombre_medidor, esquema_tarifa_id=None):
    """Procesa BESS + medidor: combinado 5 min → diario → acumulados."""
    med = medidor_consumo_por_prefijo(prefijo)
    sub = next(
        (s for s in SUBESTACIONES if any(m.prefijo == prefijo for m in s.medidores_consumo)),
        None,
    )
    if sub and med:
        etiqueta = f"{sub.nombre} · {med.etiqueta}"
    else:
        etiqueta = etiqueta_medidor(prefijo)

    print("\n" + "=" * 70)
    print(f"PROCESANDO {etiqueta}")
    print("=" * 70)

    if not os.path.exists(ruta_bess):
        print(f"ERROR: No se encuentra el archivo BESS: {ruta_bess}")
        return False, "No se encuentra archivo BESS"

    if not os.path.exists(ruta_medidor):
        print(f"ERROR: No se encuentra el archivo de consumo: {ruta_medidor}")
        return False, f"No se encuentra archivo de consumo ({etiqueta})"

    df_bess = leer_sin_agrupar(ruta_bess)
    df_medidor = leer_sin_agrupar(ruta_medidor, prefijo_consumo=prefijo)
    if len(df_bess) == 0 or len(df_medidor) == 0:
        return False, f"No se pudieron cargar datos validos para {etiqueta}"

    if usa_consumo_neto(prefijo):
        print(f"  {prefijo}: energía con KWH_NETO por intervalo de 5 min")

    print(f"  BESS: {len(df_bess)} registros · {prefijo}: {len(df_medidor)} registros")

    df_combinado = generar_combinado_por_minuto(
        ruta_bess, ruta_medidor, prefijo, esquema_tarifa_id=esquema_tarifa_id,
    )
    if df_combinado is None or len(df_combinado) == 0:
        return False, f"No se genero combinado por minuto para {etiqueta}"

    if generar_diarios_con_demandas(prefijo, esquema_tarifa_id=esquema_tarifa_id) is None:
        return False, f"No se genero archivo diario para {etiqueta}"

    generar_acumulados(prefijo)

    print(f"\nOK {etiqueta} procesada exitosamente")
    return True, f"{etiqueta} procesada exitosamente"


def _validar_archivos_filtrados():
    """Comprueba que existan los CSV filtrados de cada subestación."""
    faltantes: list[str] = []
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            ruta = str(med.ruta_consumo_lectura(filtrado=True))
            if not os.path.exists(ruta):
                faltantes.append(f"{sub.id}/{med.consumo_filtrado}")
        ruta_bess = str(sub.ruta_bess_lectura(filtrado=True))
        if not os.path.exists(ruta_bess):
            faltantes.append(f"{sub.id}/{sub.bess_filtrado}")
    if faltantes:
        return False, (
            f"Faltan archivos filtrados: {', '.join(faltantes)}. "
            "Ejecute Filtrar antes de Generar reportes."
        )
    return True, ""


def reporte_bess():
    """Genera reportes CSV, adquiriendo antes el lock del pipeline.

    Ver bess.data.pipeline_lock: evita que esta etapa corra al mismo
    tiempo que otra (sync/verificar/filtrar/reportes).
    """
    from filelock import Timeout

    from bess.data.pipeline_lock import MENSAJE_PIPELINE_OCUPADO, lock_pipeline

    lock = lock_pipeline()
    try:
        lock.acquire()
    except Timeout:
        return False, {"_error": MENSAJE_PIPELINE_OCUPADO}
    try:
        return _reporte_bess_impl()
    finally:
        lock.release()


def _reporte_bess_impl():
    """Genera reportes CSV para todas las subestaciones."""
    total = _reporte_ui_total()
    paso = 0

    print("=" * 60)
    print("PROCESAMIENTO DE DATOS DE ENERGIA - SUBESTACIONES IUSA")
    print("=" * 60)

    paso += 1
    _reporte_ui(paso, total, "Validar archivos filtrados")
    ok, msg = _validar_archivos_filtrados()
    if not ok:
        print(f"ERROR: {msg}")
        return False, {"_error": msg}

    mensajes: dict[str, str] = {}
    resultados: list[bool] = []

    for sub in SUBESTACIONES:
        ruta_bess = str(sub.ruta_bess_lectura(filtrado=True))
        for med in sub.medidores_consumo:
            paso += 1
            _reporte_ui(
                paso,
                total,
                f"Combinado y energía · {sub.nombre} · {med.etiqueta}",
            )
            ruta_consumo = str(med.ruta_consumo_lectura(filtrado=True))
            exito, mensaje = procesar_grupo(
                ruta_bess,
                ruta_consumo,
                med.prefijo,
                med.consumo_lectura,
                esquema_tarifa_id=sub.esquema_tarifa_id,
            )
            mensajes[med.prefijo] = mensaje
            resultados.append(exito)

    paso += 1
    _reporte_ui(paso, total, "Energía BESS por día")
    print("\n" + "=" * 60)
    print("GENERANDO ARCHIVOS DIARIOS DEL BESS")
    print("=" * 60)

    for sub in SUBESTACIONES:
        med_fact = sub.medidor_facturacion
        if not med_fact:
            continue
        ruta_comb = ruta_combinado_por_prefijo(med_fact.prefijo)
        if ruta_comb and ruta_comb.exists():
            generar_bess_diario_subestacion(sub)
        else:
            print(f"No se encontro combinado para BESS diario · {sub.id}")

    print("\n" + "=" * 60)
    print("GENERANDO REPORTES GENERACIÓN")
    print("=" * 60)
    for sub in SUBESTACIONES:
        recurso = recurso_generacion_subestacion(sub.id)
        if recurso is None:
            continue
        paso += 1
        _reporte_ui(paso, total, f"Generación · {sub.nombre}")
        if recurso.tipo == "granja":
            ruta_gen = str(sub.ruta_generacion_lectura(filtrado=True))
        else:
            ruta_gen = str(sub.ruta_cogeneracion_lectura(filtrado=True) or "")
        if ruta_gen and os.path.exists(ruta_gen):
            generar_reportes_generacion(
                ruta_gen,
                sub.id,
                recurso.prefijo_reporte,
                columna_kwh=recurso.columna_kwh,
                esquema_tarifa_id=sub.esquema_tarifa_id,
            )
        else:
            print(f"⚠️ {sub.nombre}: sin {recurso.csv_filtrado} (omitido)")

    paso += 1
    _reporte_ui(paso, total, "Finalizando reportes")
    print("\n" + "=" * 60)
    print("RESUMEN DEL PROCESO")
    print("=" * 60)
    idx = 0
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            exito = resultados[idx] if idx < len(resultados) else False
            idx += 1
            estado = "✅ Éxito" if exito else "❌ Falló"
            print(f"{sub.nombre} · {med.etiqueta}: {estado}")
    print("\n" + "=" * 60)
    print("=== FIN DEL PROCESO ===")

    return all(resultados), mensajes
