"""Verificación de archivos fuente."""

from __future__ import annotations

import csv
import os
import shutil

import pandas as pd

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.config.subestaciones import SUBESTACIONES, archivos_fuente_subestacion
from bess.data.pipeline.bess_consolidate import consolidar_bess_subestacion
from bess.core.console import log
from bess.data.ingest.identify import identificar_y_renombrar_archivos
from bess.data.ingest.readers import leer_archivo_perfil

print = log

# El origen (ArchivosFuente) puede traer, en corridas sucesivas, valores
# actualizados para fechas que ya se habian verificado ese mismo dia --
# tipicamente porque export_csv.py reexporta una ventana de los ultimos
# dias en cada corrida para reflejar correcciones de la API ISOL sobre el
# dia en curso (ver bess/data/ingest/ion/export_csv.py). Si aqui solo se
# miraran filas estrictamente posteriores al cursor, esas actualizaciones
# nunca se volverian a leer del origen. Por eso el modo incremental no
# anexa solo lo nuevo: siempre vuelve a verificar y sobrescribir una
# ventana de los ultimos `_MARGEN_REEXPORTAR_DIAS` dias, preservando
# intacto todo lo anterior a esa ventana.
_MARGEN_REEXPORTAR_DIAS = 1


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


def _leer_previas_a_ventana(
    ruta_destino: str,
    inicio_ventana: "pd.Timestamp",
) -> "list[list[str]] | None":
    """Filas crudas (via csv.reader, SIN reparsear los valores numericos)
    ya procesadas en `ruta_destino` con Fecha anterior a `inicio_ventana`
    -- se preservan tal cual estaban al recalcular la ventana.

    Deliberadamente NO se devuelve un DataFrame: reparsear una columna
    numerica ya escrita (p.ej. "193.33090209960932", un valor real de ION)
    y volver a serializarla via pandas puede producir una representacion
    de texto ligeramente distinta para el mismo float64 (p.ej.
    "193.3309020996093") -- un cambio de bytes sin sentido en datos que ya
    estaban cerrados. Igual que export_csv.py, se preservan las filas
    crudas y solo se reparsea/reformatea la ventana que realmente se
    recalcula.

    Devuelve None si el archivo no existe o no tiene una columna Fecha en
    la primera posicion; quien llama debe caer al modo completo en ese
    caso (no debería ocurrir aquí porque _columnas_compatibles() ya se
    validó antes de llamar, pero es la misma defensa que el resto del
    módulo usa ante un formato inesperado).
    """
    if not os.path.exists(ruta_destino):
        return None
    try:
        with open(ruta_destino, 'r', newline='', encoding='utf-8-sig') as f:
            lector = csv.reader(f)
            encabezado = next(lector, None)
            if not encabezado or encabezado[0] != 'Fecha':
                return None
            filas = [fila for fila in lector if fila]
    except OSError:
        return None
    if not filas:
        return []
    fechas = pd.to_datetime([fila[0] for fila in filas], errors='coerce')
    return [
        fila for fila, fecha in zip(filas, fechas)
        if pd.notna(fecha) and fecha < inicio_ventana
    ]


def _guardar_ventana_procesada(
    filas_previas: "list[list[str]]",
    perfil_ventana: pd.DataFrame,
    ruta_destino: str,
    nombre_archivo: str,
) -> bool:
    """Escribe ruta_destino completo: `filas_previas` (crudas, preservadas
    tal cual via _leer_previas_a_ventana) + `perfil_ventana` (la ventana
    reverificada, formateada igual que _guardar_perfil_procesado) --
    reemplaza lo que hubiera para las fechas de la ventana, sin tocar el
    formato de lo anterior.

    A diferencia de _guardar_perfil_procesado, no crea backup: esto corre
    en cada sincronizacion incremental normal (no solo al reprocesar todo
    el historico), y el lock del pipeline ya garantiza que nadie mas
    escribe este archivo al mismo tiempo.
    """
    os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
    salida = perfil_ventana.copy()
    salida['Fecha'] = salida['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S')
    try:
        # Sin newline='' aqui (a diferencia de la lectura): con
        # newline=None (el default), Python traduce cada '\n' escrito al
        # separador de linea del sistema (os.linesep) -- exactamente lo
        # mismo que hace pandas.to_csv() internamente (usado en el modo
        # completo, y el que escribio originalmente el archivo
        # existente). Con newline='' el '\n' se escribiria literal sin
        # traducir, y en Windows (donde corre este pipeline en
        # produccion, os.linesep='\r\n') eso desalinearia el fin de linea
        # de la ventana reescrita contra el resto del archivo.
        with open(ruta_destino, 'w', encoding='utf-8-sig') as f:
            writer = csv.writer(f, lineterminator='\n')
            writer.writerow(list(salida.columns))
            for fila in filas_previas:
                writer.writerow(fila)
            for row in salida.itertuples(index=False):
                writer.writerow(row)
    except OSError as e:
        print(
            f"❌ No se pudo guardar {nombre_archivo}: {e}. "
            "Cierre Excel u otro programa que tenga abierto el CSV en ArchivosProcesados."
        )
        return False
    print(f"✅ Ventana reverificada guardada: {ruta_destino}")
    print(f"📊 Registros finales: {len(filas_previas) + len(salida)}")
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


def _primera_fecha_procesada(ruta_destino: str) -> "pd.Timestamp | None":
    """Primera Fecha ya escrita en el CSV procesado, o None si no existe/esta vacio.

    Solo lee la columna Fecha, igual que _cursor_procesado. Se usa para
    acotar la ventana de reverificacion: si `inicio_ventana` cae antes
    del inicio real del historico (archivo recien agregado, a menos de
    `_MARGEN_REEXPORTAR_DIAS` dias de su primer registro), no hay que
    fabricar un dia que nunca existio -- ver procesar_archivo_verificacion.
    """
    if not os.path.exists(ruta_destino):
        return None
    try:
        fechas = pd.read_csv(
            ruta_destino, usecols=['Fecha'], encoding='utf-8-sig'
        )['Fecha']
    except (ValueError, KeyError):
        return None
    fechas = pd.to_datetime(fechas, errors='coerce').dropna()
    if fechas.empty:
        return None
    return fechas.min()


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
    verifica (dedup + relleno de huecos) una ventana de los ultimos
    `_MARGEN_REEXPORTAR_DIAS` dias del origen (no solo lo estrictamente
    posterior al cursor), y esa ventana reemplaza lo que hubiera en el
    archivo procesado para esas fechas -- en vez de releer y reescribir
    todo el historico en cada sincronizacion. Esto recoge actualizaciones
    que el origen trae para fechas ya verificadas (p.ej. la API ISOL, via
    export_csv.py, completando con valores reales un dia que ya se habia
    exportado en cero). Lo anterior a la ventana se preserva crudo
    (_leer_previas_a_ventana), sin reparsear sus valores numéricos, para
    no arriesgar diferencias de redondeo en datos ya cerrados. La primera
    vez (o si el formato no coincide) se procesa completo, igual que
    antes.
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
            inicio_ventana = cursor.normalize() - pd.Timedelta(days=_MARGEN_REEXPORTAR_DIAS)
            print(f"📌 Cursor: ya verificado hasta {cursor.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🔁 Ventana a reverificar: desde {inicio_ventana.strftime('%Y-%m-%d %H:%M:%S')}")

            nuevos = perfil[perfil['Fecha'] >= inicio_ventana]
            nuevos = nuevos.drop_duplicates(subset=['Fecha'], keep='first')
            renglones_duplicados = len(perfil[perfil['Fecha'] >= inicio_ventana]) - len(nuevos)
            if renglones_duplicados:
                print(f"🗑️ Renglones duplicados eliminados: {renglones_duplicados}")

            if nuevos.empty:
                print("ℹ️ Sin registros nuevos desde la última verificación")
                return True

            nuevos = nuevos.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
            # Acotar fi para no fabricar un dia que nunca existio: si el
            # archivo tiene menos de _MARGEN_REEXPORTAR_DIAS dias de
            # historia (recien agregado), inicio_ventana puede caer antes
            # del primer registro real (tanto el ya procesado como el que
            # trae ahora el origen) -- en ese caso fi es ese primer
            # registro real, igual que en el modo completo.
            primera_conocida = nuevos['Fecha'].min()
            primera_destino = _primera_fecha_procesada(ruta_completa_destino)
            if primera_destino is not None:
                primera_conocida = min(primera_conocida, primera_destino)
            fi = max(inicio_ventana, primera_conocida)
            ff = nuevos['Fecha'].max()

            print(f"📅 Rango a reverificar: {fi.strftime('%Y-%m-%d %H:%M:%S')} a {ff.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📊 Registros en ventana (origen): {len(nuevos)}")

            perfil_completo, faltantes = _completar_rango(
                nuevos, fi, ff, columnas, Frecuencia_Perfil_MIN
            )
            print(f"📝 Registros faltantes insertados: {faltantes}")

            previas = _leer_previas_a_ventana(ruta_completa_destino, inicio_ventana)
            if previas is None:
                previas = []
            return _guardar_ventana_procesada(
                previas, perfil_completo, ruta_completa_destino, nombre_archivo
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
