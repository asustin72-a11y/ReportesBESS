"""Verificación de archivos fuente."""

from __future__ import annotations

import os
import shutil
from datetime import timedelta

import pandas as pd

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.config.subestaciones import SUBESTACIONES, archivos_fuente_subestacion
from bess.data.pipeline.bess_consolidate import consolidar_bess_subestacion
from bess.core.console import log
from bess.data.ingest.identify import identificar_y_renombrar_archivos
from bess.data.ingest.readers import leer_archivo_perfil

print = log


def _guardar_perfil_procesado(
    perfil: pd.DataFrame,
    ruta_destino: str,
    nombre_archivo: str,
) -> bool:
    os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
    if os.path.exists(ruta_destino):
        backup_path = ruta_destino.replace('.csv', '_backup.csv')
        shutil.copy2(ruta_destino, backup_path)
        print(f"💾 Backup creado: {os.path.basename(backup_path)}")

    salida = perfil.copy()
    salida['Fecha'] = salida['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S')
    try:
        salida.to_csv(ruta_destino, index=False, encoding='utf-8-sig')
    except OSError as e:
        print(
            f"❌ No se pudo guardar {nombre_archivo}: {e}. "
            "Cierre Excel u otro programa que tenga abierto el CSV en ArchivosProcesados."
        )
        return False
    print(f"✅ Archivo procesado guardado: {ruta_destino}")
    print(f"📊 Registros finales: {len(salida)}")
    return True


def _anexar_perfil_procesado(
    perfil_nuevo: pd.DataFrame,
    ruta_destino: str,
    nombre_archivo: str,
) -> bool:
    """Agrega filas nuevas al final de un CSV ya procesado (sin reescribirlo).

    A diferencia de _guardar_perfil_procesado, no toca las filas existentes
    ni crea backup: el archivo ya estaba verificado hasta el cursor y solo
    se le suma lo nuevo. El lock del pipeline (bess.data.pipeline_lock)
    ya garantiza que nadie mas escribe este archivo al mismo tiempo.
    """
    salida = perfil_nuevo.copy()
    salida['Fecha'] = salida['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S')
    try:
        salida.to_csv(
            ruta_destino, index=False, header=False, mode='a', encoding='utf-8-sig'
        )
    except OSError as e:
        print(
            f"❌ No se pudo anexar a {nombre_archivo}: {e}. "
            "Cierre Excel u otro programa que tenga abierto el CSV en ArchivosProcesados."
        )
        return False
    print(f"✅ {len(salida)} registro(s) nuevo(s) anexado(s) a: {ruta_destino}")
    return True


def _cursor_procesado(ruta_destino: str) -> "pd.Timestamp | None":
    """Ultima Fecha ya escrita en el CSV procesado, o None si no existe/esta vacio.

    Solo lee la columna Fecha (no el archivo completo) para que consultar
    el cursor sea barato incluso en historiales largos.
    """
    if not os.path.exists(ruta_destino):
        return None
    try:
        fechas = pd.read_csv(
            ruta_destino, usecols=['Fecha'], encoding='utf-8-sig'
        )['Fecha']
    except (ValueError, KeyError):
        # Encabezado inesperado (formato viejo, columna distinta, etc.):
        # no hay cursor confiable, se reprocesa completo como antes.
        return None
    fechas = pd.to_datetime(fechas, errors='coerce').dropna()
    if fechas.empty:
        return None
    return fechas.max()


def _columnas_compatibles(ruta_destino: str, columnas_nuevas: list[str]) -> bool:
    """True si el CSV ya procesado tiene exactamente las mismas columnas."""
    try:
        columnas_existentes = pd.read_csv(
            ruta_destino, nrows=0, encoding='utf-8-sig'
        ).columns.tolist()
    except (ValueError, KeyError):
        return False
    return columnas_existentes == columnas_nuevas


def _completar_rango(
    datos: pd.DataFrame,
    fi: "pd.Timestamp",
    ff: "pd.Timestamp",
    columnas: list[str],
    frecuencia_min: int = 5,
) -> tuple[pd.DataFrame, int]:
    """Rellena huecos de `datos` (ya sin duplicados) entre fi y ff inclusive.

    Regla de negocio: el dia opera de 00:05 a 00:00 del dia siguiente
    (288 perfiles/dia); el 00:00 es el perfil de cierre del dia anterior,
    no el inicio del dia entrante. Como `fi`/`ff` ya delimitan el rango
    real presente en el origen (nunca incluyen un 00:00 fuera de rango,
    p.ej. el del dia antes del primer registro), cualquier 00:00 que caiga
    *dentro* de [fi, ff] y falte en `datos` es un hueco real y se rellena
    con cero igual que cualquier otro slot -- sin excepcion por fuente
    (ION incluido).

    Vectorizado: calcula la rejilla completa de `frecuencia_min` y resta
    las fechas reales en una sola pasada (antes se armaba con un
    pd.concat por cada registro faltante dentro de un bucle, O(n^2) en
    perfiles largos). Devuelve (perfil_completo, cantidad_faltantes).
    """
    rango_completo = pd.date_range(fi, ff, freq=f'{frecuencia_min}min')
    fechas_faltantes = rango_completo.difference(pd.DatetimeIndex(datos['Fecha']))
    faltantes = len(fechas_faltantes)

    if faltantes:
        faltantes_df = pd.DataFrame({'Fecha': fechas_faltantes})
        for col in columnas[1:]:
            faltantes_df[col] = 0
        completo = pd.concat([datos, faltantes_df], ignore_index=True)
    else:
        completo = datos

    completo = completo.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
    return completo, faltantes


def procesar_archivo_verificacion(ruta_origen, ruta_destino, nombre_archivo):
    """
    Procesa un archivo CSV verificando duplicados y registros faltantes.

    Incremental: si ya existe un CSV procesado para este archivo, solo se
    verifican (dedup + relleno de huecos) las filas del origen posteriores
    al cursor (la ultima Fecha ya escrita), y se anexan al final en vez de
    releer y reescribir todo el historico en cada sincronizacion. La
    primera vez (o si el formato no coincide) se procesa completo, igual
    que antes.
    """
    ruta_completa_origen = os.path.join(ruta_origen, nombre_archivo)
    ruta_completa_destino = os.path.join(ruta_destino, nombre_archivo)
    
    if not os.path.exists(ruta_completa_origen):
        print(f"❌ Error: No se encuentra {ruta_completa_origen}")
        return False
    
    print(f"\n{'='*60}")
    print(f"📊 Procesando: {nombre_archivo}")
    print(f"{'='*60}")
    
    try:
        perfil = leer_archivo_perfil(ruta_completa_origen, nombre_archivo)
        if perfil is None:
            return False
        
        print(f"📁 Archivo original: {nombre_archivo}")
        print(f"📏 Registros originales: {len(perfil)}")

        columnas = perfil.columns.tolist()
        Frecuencia_Perfil_MIN = 5

        cursor = _cursor_procesado(ruta_completa_destino)
        modo_incremental = cursor is not None and _columnas_compatibles(
            ruta_completa_destino, columnas
        )

        if modo_incremental:
            print(f"📌 Cursor: ya verificado hasta {cursor.strftime('%Y-%m-%d %H:%M:%S')}")
            nuevos = perfil[perfil['Fecha'] > cursor]
            nuevos = nuevos.drop_duplicates(subset=['Fecha'], keep='first')
            renglones_duplicados = len(perfil[perfil['Fecha'] > cursor]) - len(nuevos)
            if renglones_duplicados:
                print(f"🗑️ Renglones duplicados eliminados: {renglones_duplicados}")

            if nuevos.empty:
                print("ℹ️ Sin registros nuevos desde la última verificación")
                return True

            nuevos = nuevos.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
            fi = cursor + timedelta(minutes=Frecuencia_Perfil_MIN)
            ff = nuevos['Fecha'].max()

            print(f"📅 Rango nuevo: {fi.strftime('%Y-%m-%d %H:%M:%S')} a {ff.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📊 Registros nuevos: {len(nuevos)}")

            perfil_completo, faltantes = _completar_rango(
                nuevos, fi, ff, columnas, Frecuencia_Perfil_MIN
            )
            print(f"📝 Registros faltantes insertados: {faltantes}")

            return _anexar_perfil_procesado(
                perfil_completo, ruta_completa_destino, nombre_archivo
            )

        # Modo completo: primera vez que se procesa este archivo, o el CSV
        # existente no tiene un cursor confiable (formato distinto).
        perfil_sin_duplicados = perfil.drop_duplicates(subset=['Fecha'], keep='first')
        renglones_duplicados = len(perfil) - len(perfil_sin_duplicados)
        print(f"🗑️ Renglones duplicados eliminados: {renglones_duplicados}")

        perfil_sin_duplicados = perfil_sin_duplicados.sort_values(
            by='Fecha', ascending=True
        ).reset_index(drop=True)

        num_registros = len(perfil_sin_duplicados)
        fi = perfil_sin_duplicados.iloc[0, 0]
        ff = perfil_sin_duplicados.iloc[num_registros - 1, 0]
        dias = (ff - fi).days + 1
        registros_esperados = dias * 288

        print(f"📅 Fecha inicial: {fi.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 Fecha final: {ff.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Registros esperados: {registros_esperados}")
        print(f"📊 Registros actuales: {num_registros}")
        print("\n⏳ Verificando registros faltantes...")

        perfil_completo, faltantes = _completar_rango(
            perfil_sin_duplicados, fi, ff, columnas,
            Frecuencia_Perfil_MIN,
        )

        print("✅ Verificación completada")
        print(f"📝 Registros faltantes insertados: {faltantes}")

        return _guardar_perfil_procesado(
            perfil_completo,
            ruta_completa_destino,
            nombre_archivo,
        )
        
    except Exception as e:
        print(f"❌ Error al procesar {nombre_archivo}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verificar_datos_fuente():
    """Verifica datos fuente, adquiriendo antes el lock del pipeline.

    Ver bess.data.pipeline_lock: evita que esta etapa corra al mismo
    tiempo que otra (sync/verificar/filtrar/reportes), sin importar si
    la dispara el cron, el boton "Procesar todo" o el paso individual.
    """
    from filelock import Timeout

    from bess.data.pipeline_lock import MENSAJE_PIPELINE_OCUPADO, lock_pipeline

    lock = lock_pipeline()
    try:
        lock.acquire()
    except Timeout:
        return False, MENSAJE_PIPELINE_OCUPADO
    try:
        return _verificar_datos_fuente_impl()
    finally:
        lock.release()


def _verificar_datos_fuente_impl():
    """Función principal de verificación de datos fuente. Retorna (éxito, mensaje)."""
    
    # PASO 1: Identificar y renombrar archivos
    identificar_y_renombrar_archivos()
    
    # PASO 2: Procesar archivos por subestación (consumo, BESS y granja)
    print("\n" + "=" * 70)
    print("🔍 VERIFICADOR DE PERFILES DE CARGA")
    print("=" * 70)
    print(f"📁 Carpeta origen: {DIRECTORIO_FUENTE}")
    print(f"📁 Carpeta destino: {DIRECTORIO_PROCESADOS}")
    print("=" * 70)

    if not os.path.exists(DIRECTORIO_FUENTE):
        print(f"❌ Error: No existe la carpeta {DIRECTORIO_FUENTE}")
        os.makedirs(DIRECTORIO_FUENTE, exist_ok=True)
        print(f"✅ Carpeta creada: {DIRECTORIO_FUENTE}")
        return False, (
            f"No existía la carpeta {DIRECTORIO_FUENTE}. "
            "Coloque los CSV de perfil ahí."
        )

    resultados: dict[str, bool | None] = {}

    for sub in SUBESTACIONES:
        print(f"\n{'=' * 70}")
        print(f"🔍 {sub.nombre}")
        print("=" * 70)
        for archivo in archivos_fuente_subestacion(sub):
            ruta_fuente_sub = os.path.join(DIRECTORIO_FUENTE, sub.id)
            ruta_completa = os.path.join(ruta_fuente_sub, archivo)
            if not os.path.exists(ruta_completa):
                print(f"\n⚠️ {sub.id}/{archivo} no está en ArchivosFuente (omitido)")
                resultados[archivo] = None
                continue
            resultados[archivo] = procesar_archivo_verificacion(
                ruta_fuente_sub,
                os.path.join(DIRECTORIO_PROCESADOS, sub.id),
                archivo,
            )

        if consolidar_bess_subestacion(sub):
            print(f"✅ BESS consolidado: {sub.bess_csv}")

    print("\n" + "=" * 70)
    print("📊 RESUMEN FINAL VERIFICACIÓN")
    print("=" * 70)
    for archivo, exito in resultados.items():
        if exito is None:
            estado = "⏭️ Omitido (no en fuente)"
        elif exito:
            estado = "✅ Éxito"
        else:
            estado = "❌ Falló"
        print(f"   {archivo}: {estado}")

    verificados = [a for a, ok in resultados.items() if ok is True]
    fallidos = [a for a, ok in resultados.items() if ok is False]
    omitidos = [a for a, ok in resultados.items() if ok is None]

    if not verificados:
        return False, (
            "No se verificó ningún archivo. "
            "Copie los CSV en data/ArchivosFuente y vuelva a intentar."
        )
    if fallidos:
        return False, (
            f"Error al verificar: {', '.join(fallidos)}. "
            "Cierre Excel u otros programas que tengan abiertos los CSV."
        )

    return True, _mensaje_verificacion_ok(verificados, omitidos)


def _mensaje_verificacion_ok(verificados: list[str], omitidos: list[str]) -> str:
    """Mensaje de éxito agrupado por subestación (incluye granja IUSA 2)."""
    partes: list[str] = []
    for sub in SUBESTACIONES:
        archivos_sub = archivos_fuente_subestacion(sub)
        ok_sub = [a for a in archivos_sub if a in verificados]
        if not ok_sub:
            continue
        nombres = []
        for med in sub.medidores_consumo:
            if med.consumo_csv in ok_sub:
                nombres.append(med.etiqueta)
        if sub.bess_csv in ok_sub:
            nombres.append("BESS")
        if sub.granja_csv and sub.granja_csv in ok_sub:
            nombres.append("Granja (20 MEGA)")
        if sub.cogeneracion_csv and sub.cogeneracion_csv in ok_sub:
            nombres.append("Generación")
        partes.append(f"{sub.nombre}: {', '.join(nombres)}")

    mensaje = "Verificación completada — " + "; ".join(partes) if partes else (
        f"Verificación OK ({len(verificados)} archivo(s)): {', '.join(verificados)}"
    )
    if omitidos:
        mensaje += f". Sin archivo en fuente: {', '.join(omitidos)}"
    return mensaje
