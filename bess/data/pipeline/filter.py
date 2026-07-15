"""Filtrado y limpieza de archivos fuente."""

from __future__ import annotations

import os
from typing import Callable

import pandas as pd

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.config.subestaciones import SUBESTACIONES
from bess.core.consumo import orientar_kwh_consumo
from bess.core.console import log
from bess.core.kvarh import columnas_kvarh
from bess.data.ingest.readers import leer_archivo_perfil
from bess.data.pipeline.bess_consolidate import consolidar_bess_subestacion
from bess.data.pipeline.clean import (
    MARGEN_REEXPORTAR_DIAS,
    columnas_archivo_limpio,
    cursor_archivo_limpio,
    escribir_ventana_archivo_limpio,
    generar_archivo_limpio,
    leer_previas_a_ventana,
)

print = log


def _leer_perfil(ruta_origen: str, archivo_origen: str):
    if not os.path.exists(ruta_origen):
        return None, f"No se puede continuar sin el archivo {archivo_origen}"
    df = leer_archivo_perfil(ruta_origen, archivo_origen)
    if df is None:
        return None, f"Error al leer {archivo_origen}"
    return df, None


def _escribir_filtrado(
    df_fuente: pd.DataFrame,
    fechas_aceptadas: set,
    ruta_destino: str,
    *,
    transformar: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> int:
    """Escribe en `ruta_destino` las filas de `df_fuente` cuya Fecha está en
    `fechas_aceptadas` (el resultado de la intersección de fechas, ya
    calculado por quien llama).

    Incremental: si `ruta_destino` ya tiene un cursor legible (última Fecha
    escrita en una corrida anterior) y columnas compatibles, se recalcula
    una ventana de los últimos `MARGEN_REEXPORTAR_DIAS` días (no solo lo
    estrictamente posterior al cursor) y esa ventana reemplaza lo que
    hubiera en el archivo para esas fechas, preservando intacto todo lo
    anterior -- en vez de reescribir el archivo completo. Esto recoge
    actualizaciones que Verificar (y, más atrás, export_csv.py) traen para
    fechas ya filtradas (ver bess/data/pipeline/clean.py). Lo anterior a la
    ventana se preserva crudo (leer_previas_a_ventana), sin reparsear sus
    valores numéricos, para no arriesgar diferencias de redondeo en datos
    ya cerrados. La primera vez (o si cambia el formato de columnas)
    recalcula y reescribe completo, igual que antes de esta fase.

    `fechas_aceptadas` en sí siempre se calcula completo (a partir de los
    conjuntos de fechas de BESS/medidor ya leídos): lo único que se vuelve
    incremental es qué tanto de ese resultado hace falta *reescribir*. Esto
    es seguro porque Verificar garantiza que cada CSV procesado no tiene
    huecos internos dentro de su propio rango -- la intersección de dos
    rangos sin huecos es a su vez un rango sin huecos, así que una fecha
    nunca queda "saltada" por quedar por debajo del cursor sin haber sido
    nunca escrita. Tampoco hay riesgo de fabricar fechas fantasma: aquí no
    se rellenan huecos con cero, solo se escribe lo que ya está en
    `fechas_aceptadas` (calculado por quien llama a partir de datos reales).

    Devuelve la cantidad de filas escritas en esta corrida (0 si la
    ventana no tenía nada que escribir).
    """
    cursor = cursor_archivo_limpio(ruta_destino)
    if cursor is not None:
        inicio_ventana = cursor.normalize() - pd.Timedelta(days=MARGEN_REEXPORTAR_DIAS)
        ventana = {f for f in fechas_aceptadas if f >= inicio_ventana}
        if not ventana:
            return 0
        df_nuevo = df_fuente[df_fuente["Fecha"].isin(ventana)].copy()
        df_nuevo = df_nuevo.sort_values("Fecha").reset_index(drop=True)
        if transformar is not None:
            df_nuevo = transformar(df_nuevo)
        columnas_nuevas = ["Fecha", "KWH_REC", "KWH_ENT"] + columnas_kvarh(df_nuevo)
        if columnas_archivo_limpio(ruta_destino) == columnas_nuevas:
            previas = leer_previas_a_ventana(ruta_destino, inicio_ventana)
            if previas is not None:
                escribir_ventana_archivo_limpio(previas, df_nuevo, ruta_destino)
                return len(df_nuevo)
        # Formato de columnas distinto al existente, o no se pudo leer lo
        # previo: cae al modo completo de abajo, recalculando sobre todo
        # `fechas_aceptadas`.

    df_completo = df_fuente[df_fuente["Fecha"].isin(fechas_aceptadas)].copy()
    df_completo = df_completo.sort_values("Fecha").reset_index(drop=True)
    if transformar is not None:
        df_completo = transformar(df_completo)
    generar_archivo_limpio(df_completo, ruta_destino)
    return len(df_completo)


def filtrar_datos():
    """Filtra datos, adquiriendo antes el lock del pipeline.

    Ver bess.data.pipeline_lock: evita que esta etapa corra al mismo
    tiempo que otra (sync/verificar/filtrar/reportes).
    """
    from filelock import Timeout

    from bess.data.pipeline_lock import MENSAJE_PIPELINE_OCUPADO, lock_pipeline

    lock = lock_pipeline()
    try:
        lock.acquire()
    except Timeout:
        return False, MENSAJE_PIPELINE_OCUPADO
    try:
        return _filtrar_datos_impl()
    finally:
        lock.release()


def _filtrar_datos_impl():
    """
    Filtra por fechas comunes dentro de cada subestación (consumo + BESS).
    """
    print("=" * 70)
    print("📊 PREPROCESADOR DE DATOS - FILTRADO POR SUBESTACIÓN")
    print("=" * 70)
    print(f"📁 Carpeta de trabajo: {DIRECTORIO_PROCESADOS}")
    print("=" * 70)

    if not os.path.exists(DIRECTORIO_PROCESADOS):
        print(f"❌ Error: No existe la carpeta {DIRECTORIO_PROCESADOS}")
        return False, f"No existe la carpeta {DIRECTORIO_PROCESADOS}"

    total_fechas = 0
    subestaciones_ok = 0
    subs_omitidas: list[str] = []

    for sub in SUBESTACIONES:
        print("\n" + "=" * 70)
        print(f"🔍 {sub.nombre}")
        print("=" * 70)

        ruta_bess = str(sub.ruta_bess_lectura())
        if not os.path.exists(ruta_bess):
            if consolidar_bess_subestacion(sub, filtrado=False):
                ruta_bess = str(sub.ruta_bess_lectura())
        if not os.path.exists(ruta_bess):
            print(f"⚠️ Omitido: falta {sub.bess_csv} verificado en ArchivosProcesados/{sub.id}")
            subs_omitidas.append(sub.nombre)
            continue

        df_bess, err = _leer_perfil(ruta_bess, sub.bess_csv)
        if err:
            return False, f"{sub.nombre}: {err}"

        fechas_bess = set(df_bess["Fecha"])
        fechas_bess_filtradas: set | None = None

        for med in sub.medidores_consumo:
            ruta_consumo = str(med.ruta_consumo_lectura())
            if not os.path.exists(ruta_consumo):
                return False, (
                    f"{sub.nombre} ({med.etiqueta}): falta {med.consumo_csv} verificado. "
                    "Ejecute Verificar antes de Filtrar."
                )
            df_consumo, err = _leer_perfil(ruta_consumo, med.consumo_csv)
            if err:
                return False, f"{sub.nombre} ({med.etiqueta}): {err}"

            fechas_consumo = set(df_consumo["Fecha"])
            fechas_comunes = fechas_consumo.intersection(fechas_bess)

            print(f"📊 Registros {med.etiqueta} ({med.consumo_csv}): {len(fechas_consumo)}")
            print(f"📊 Fechas comunes {med.etiqueta} ∩ BESS: {len(fechas_comunes)}")

            if len(fechas_comunes) == 0:
                return False, (
                    f"{sub.nombre} ({med.etiqueta}): no hay fechas coincidentes entre "
                    f"{med.consumo_csv} y {sub.bess_csv}"
                )

            transformar = None
            if med.intercambiar_consumo:
                def transformar(df, _med=med):
                    antes = df[["KWH_REC", "KWH_ENT"]].copy()
                    salida = orientar_kwh_consumo(df, forzar=True)
                    if not salida[["KWH_REC", "KWH_ENT"]].equals(antes):
                        print(
                            f"🔄 {_med.consumo_filtrado}: Intercambiando KWH_REC ↔ KWH_ENT "
                            f"(solo en archivo filtrado)"
                        )
                    return salida

            ruta_destino = str(med.ruta_consumo(filtrado=True))
            _escribir_filtrado(df_consumo, fechas_comunes, ruta_destino, transformar=transformar)

            if fechas_bess_filtradas is None:
                fechas_bess_filtradas = fechas_comunes
            else:
                fechas_bess_filtradas &= fechas_comunes

        print(f"📊 Registros BESS ({sub.bess_csv}): {len(fechas_bess)}")
        if fechas_bess_filtradas:
            _escribir_filtrado(
                df_bess,
                fechas_bess_filtradas,
                str(sub.ruta_bess(filtrado=True)),
            )
            total_fechas += len(fechas_bess_filtradas)
            subestaciones_ok += 1

        if sub.granja_csv and sub.granja_filtrado and fechas_bess_filtradas:
            ruta_granja = str(sub.ruta_generacion_lectura())
            if os.path.exists(ruta_granja):
                df_granja, err = _leer_perfil(ruta_granja, sub.granja_csv)
                if err:
                    return False, f"{sub.nombre} (granja): {err}"
                filas_escritas = _escribir_filtrado(
                    df_granja,
                    fechas_bess_filtradas,
                    str(sub.ruta_generacion(filtrado=True)),
                )
                print(
                    f"📊 Granja ({sub.granja_csv}): {len(df_granja)} registros "
                    f"→ {sub.granja_filtrado}: {len(fechas_bess_filtradas)} en total"
                    + (f" ({filas_escritas} nuevo(s))" if filas_escritas else "")
                )
            else:
                print(
                    f"⚠️ Granja omitida: falta {sub.granja_csv} en ArchivosProcesados. "
                    f"Verifique {sub.granja_csv} en ArchivosFuente y ejecute Verificar."
                )

        if sub.cogeneracion_csv and sub.cogeneracion_filtrado and fechas_bess_filtradas:
            ruta_cogen = str(sub.ruta_cogeneracion_lectura() or "")
            if ruta_cogen and os.path.exists(ruta_cogen):
                df_cogen, err = _leer_perfil(ruta_cogen, sub.cogeneracion_csv)
                if err:
                    return False, f"{sub.nombre} (generación): {err}"
                filas_escritas = _escribir_filtrado(
                    df_cogen,
                    fechas_bess_filtradas,
                    str(sub.ruta_cogeneracion(filtrado=True)),
                )
                print(
                    f"📊 Generación ({sub.cogeneracion_csv}): {len(df_cogen)} registros "
                    f"→ {sub.cogeneracion_filtrado}: {len(fechas_bess_filtradas)} en total"
                    + (f" ({filas_escritas} nuevo(s))" if filas_escritas else "")
                )
            else:
                print(
                    f"⚠️ Generación omitida: falta {sub.cogeneracion_csv} en ArchivosProcesados. "
                    f"Verifique {sub.cogeneracion_csv} en ArchivosFuente y ejecute Verificar."
                )

    if subestaciones_ok == 0:
        return False, (
            "Ninguna subestación pudo filtrarse. "
            "Ejecute Verificar antes de Filtrar."
        )

    # No se limpia ArchivosFuente aquí: desde que export_csv.py exporta de
    # forma incremental (cursor sobre la última Fecha ya exportada), ese
    # archivo necesita persistir entre corridas para que el cursor sirva de
    # algo. Borrarlo al final de cada Filtrar (como se hacía antes) anulaba
    # el beneficio incremental de la exportación en el cron de 15 min, que
    # encadena Sincronizar -> Verificar -> Filtrar -> Reportes en una sola
    # corrida (ver bess/PLAN_MIGRACION_SQLITE.md, Fase 2).
    # limpiar_archivos_fuente() sigue disponible para limpieza manual si
    # alguna vez hace falta liberar espacio.

    print("\n" + "=" * 70)
    print("✅ PREPROCESAMIENTO COMPLETADO EXITOSAMENTE")
    print("=" * 70)

    mensaje_omitidas = (
        f" · omitidas: {', '.join(subs_omitidas)}"
        if subs_omitidas
        else ""
    )
    return True, (
        f"Procesadas {subestaciones_ok} subestaciones "
        f"({total_fechas} fechas comunes en total){mensaje_omitidas}"
    )


def limpiar_archivos_fuente():
    """
    Elimina todos los archivos CSV del directorio ArchivosFuente
    después de que los datos han sido procesados.
    """
    archivos_eliminados = []
    errores = []

    if not os.path.exists(DIRECTORIO_FUENTE):
        return [], ["El directorio de archivos fuente no existe"]

    for sub in SUBESTACIONES:
        carpeta_sub = DIRECTORIO_FUENTE / sub.id
        if not carpeta_sub.is_dir():
            continue
        for archivo in carpeta_sub.glob("*.csv"):
            try:
                os.remove(archivo)
                archivos_eliminados.append(f"{sub.id}/{archivo.name}")
                print(f"🗑️ Archivo fuente eliminado: {sub.id}/{archivo.name}")
            except Exception as e:
                errores.append(f"Error al eliminar {sub.id}/{archivo.name}: {e}")

    return archivos_eliminados, errores
