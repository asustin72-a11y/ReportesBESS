"""Filtrado y limpieza de archivos fuente."""

from __future__ import annotations

import os

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.config.subestaciones import SUBESTACIONES
from bess.core.consumo import orientar_kwh_consumo
from bess.core.console import log
from bess.data.ingest.readers import leer_archivo_perfil
from bess.data.pipeline.bess_consolidate import consolidar_bess_subestacion
from bess.data.pipeline.clean import generar_archivo_limpio

print = log


def _leer_perfil(ruta_origen: str, archivo_origen: str):
    if not os.path.exists(ruta_origen):
        return None, f"No se puede continuar sin el archivo {archivo_origen}"
    df = leer_archivo_perfil(ruta_origen, archivo_origen)
    if df is None:
        return None, f"Error al leer {archivo_origen}"
    return df, None


def filtrar_datos():
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

            df_filtrado = df_consumo[df_consumo["Fecha"].isin(fechas_comunes)].copy()
            df_filtrado = df_filtrado.sort_values("Fecha").reset_index(drop=True)
            if med.intercambiar_consumo:
                antes = df_filtrado[["KWH_REC", "KWH_ENT"]].copy()
                df_filtrado = orientar_kwh_consumo(df_filtrado, forzar=True)
                if not df_filtrado[["KWH_REC", "KWH_ENT"]].equals(antes):
                    print(
                        f"🔄 {med.consumo_filtrado}: Intercambiando KWH_REC ↔ KWH_ENT "
                        f"(solo en archivo filtrado)"
                    )
            ruta_destino = str(med.ruta_consumo(filtrado=True))
            generar_archivo_limpio(df_filtrado, ruta_destino)

            if fechas_bess_filtradas is None:
                fechas_bess_filtradas = fechas_comunes
            else:
                fechas_bess_filtradas &= fechas_comunes

        print(f"📊 Registros BESS ({sub.bess_csv}): {len(fechas_bess)}")
        if fechas_bess_filtradas:
            df_bess_out = df_bess[df_bess["Fecha"].isin(fechas_bess_filtradas)].copy()
            df_bess_out = df_bess_out.sort_values("Fecha").reset_index(drop=True)
            generar_archivo_limpio(
                df_bess_out,
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
                df_granja_out = df_granja[df_granja["Fecha"].isin(fechas_bess_filtradas)].copy()
                df_granja_out = df_granja_out.sort_values("Fecha").reset_index(drop=True)
                generar_archivo_limpio(
                    df_granja_out,
                    str(sub.ruta_generacion(filtrado=True)),
                )
                print(
                    f"📊 Granja ({sub.granja_csv}): {len(df_granja)} registros "
                    f"→ {sub.granja_filtrado}: {len(df_granja_out)}"
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
                df_cogen_out = df_cogen[df_cogen["Fecha"].isin(fechas_bess_filtradas)].copy()
                df_cogen_out = df_cogen_out.sort_values("Fecha").reset_index(drop=True)
                generar_archivo_limpio(
                    df_cogen_out,
                    str(sub.ruta_cogeneracion(filtrado=True)),
                )
                print(
                    f"📊 Generación ({sub.cogeneracion_csv}): {len(df_cogen)} registros "
                    f"→ {sub.cogeneracion_filtrado}: {len(df_cogen_out)}"
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

    print("\n" + "=" * 70)
    print("🗑️ LIMPIANDO ARCHIVOS FUENTE")
    print("=" * 70)
    archivos_eliminados, errores = limpiar_archivos_fuente()

    if archivos_eliminados:
        print(f"✅ {len(archivos_eliminados)} archivos fuente eliminados:")
        for archivo in archivos_eliminados:
            print(f"   - {archivo}")
    else:
        print("ℹ️ No había archivos fuente para eliminar")

    if errores:
        for error in errores:
            print(f"⚠️ {error}")

    print("\n" + "=" * 70)
    print("✅ PREPROCESAMIENTO COMPLETADO EXITOSAMENTE")
    print("=" * 70)

    mensaje_eliminacion = (
        f" - {len(archivos_eliminados)} archivos fuente eliminados"
        if archivos_eliminados
        else ""
    )
    mensaje_omitidas = (
        f" · omitidas: {', '.join(subs_omitidas)}"
        if subs_omitidas
        else ""
    )
    return True, (
        f"Procesadas {subestaciones_ok} subestaciones "
        f"({total_fechas} fechas comunes en total){mensaje_eliminacion}{mensaje_omitidas}"
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
