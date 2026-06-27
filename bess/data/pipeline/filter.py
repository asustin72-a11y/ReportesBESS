"""Filtrado y limpieza de archivos fuente."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.core.console import crear_barra, log
from bess.data.ingest.readers import leer_archivo_perfil
from bess.data.pipeline.clean import generar_archivo_limpio

print = log

def filtrar_datos():
    """
    Función principal de filtrado de datos.
    Lee los archivos procesados, encuentra fechas comunes entre los 3 archivos
    y genera archivos filtrados con solo los registros coincidentes.
    """
    print("=" * 70)
    print("📊 PREPROCESADOR DE DATOS - FILTRADO POR FECHAS COMUNES")
    print("=" * 70)
    print(f"📁 Carpeta de trabajo: {DIRECTORIO_PROCESADOS}")
    print("=" * 70)
    
    if not os.path.exists(DIRECTORIO_PROCESADOS):
        print(f"❌ Error: No existe la carpeta {DIRECTORIO_PROCESADOS}")
        return False, f"No existe la carpeta {DIRECTORIO_PROCESADOS}"
    
    archivos = {
        'BESS.csv': 'BESS_Filtrado.csv',
        'ION.csv': 'ION_Filtrado.csv',
        'Banco1.csv': 'Banco1_Filtrado.csv'
    }
    
    dfs = {}
    
    # Leer archivos
    for archivo_origen, archivo_destino in archivos.items():
        ruta_origen = os.path.join(DIRECTORIO_PROCESADOS, archivo_origen)
        ruta_destino = os.path.join(DIRECTORIO_PROCESADOS, archivo_destino)
        
        if not os.path.exists(ruta_origen):
            return False, f"No se puede continuar sin el archivo {archivo_origen}"
        
        intercambiar = (archivo_origen == 'Banco1.csv')
        df = leer_archivo_perfil(ruta_origen, archivo_origen,intercambiar)
        if df is None:
            return False, f"Error al leer {archivo_origen}"
        
        dfs[archivo_origen] = df
    
    # Encontrar fechas comunes entre los 3 archivos
    print("\n" + "="*70)
    print("🔍 ENCONTRANDO FECHAS COMUNES ENTRE LOS 3 ARCHIVOS")
    print("="*70)
    
    fechas_bess = set(dfs['BESS.csv']['Fecha'])
    fechas_ion = set(dfs['ION.csv']['Fecha'])
    fechas_banco = set(dfs['Banco1.csv']['Fecha'])
    
    print(f"📊 Registros BESS: {len(fechas_bess)}")
    print(f"📊 Registros ION: {len(fechas_ion)}")
    print(f"📊 Registros Banco1: {len(fechas_banco)}")
    
    fechas_comunes = fechas_bess.intersection(fechas_ion).intersection(fechas_banco)
    
    print(f"\n📊 Fechas comunes entre los 3 archivos: {len(fechas_comunes)}")
    
    if len(fechas_comunes) == 0:
        return False, "No se encontraron fechas coincidentes entre los 3 archivos"
    
    # Mostrar rango de fechas de cada archivo
    print("\n📅 Rangos de fechas:")
    for nombre, df in dfs.items():
        print(f"   {nombre}: {df['Fecha'].min()} a {df['Fecha'].max()} ({len(df)} registros)")
    
    # Filtrar y guardar solo las fechas comunes
    print("\n" + "="*70)
    print("📊 GENERANDO ARCHIVOS FILTRADOS")
    print("="*70)
    
    for archivo_origen, archivo_destino in archivos.items():
        df_filtrado = dfs[archivo_origen][dfs[archivo_origen]['Fecha'].isin(fechas_comunes)].copy()
        df_filtrado = df_filtrado.sort_values('Fecha').reset_index(drop=True)
        ruta_destino = os.path.join(DIRECTORIO_PROCESADOS, archivo_destino)
        generar_archivo_limpio(df_filtrado, ruta_destino)
    
    # Limpiar archivos fuente después de procesar
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
    print(f"📊 Archivos filtrados generados con {len(fechas_comunes)} registros coincidentes")
    
    mensaje_eliminacion = f" - {len(archivos_eliminados)} archivos fuente eliminados"
    return True, f"Procesados {len(fechas_comunes)} registros comunes entre los 3 archivos{mensaje_eliminacion}"

# ========== FUNCIONES DE GENERACIÓN DE REPORTES ==========


def limpiar_archivos_fuente():
    """
    Elimina todos los archivos CSV del directorio ArchivosFuente
    después de que los datos han sido procesados.
    """
    archivos_eliminados = []
    errores = []
    
    if not os.path.exists(DIRECTORIO_FUENTE):
        return [], ["El directorio de archivos fuente no existe"]
    
    for archivo in os.listdir(DIRECTORIO_FUENTE):
        if archivo.lower().endswith('.csv'):
            ruta_archivo = os.path.join(DIRECTORIO_FUENTE, archivo)
            try:
                os.remove(ruta_archivo)
                archivos_eliminados.append(archivo)
                print(f"🗑️ Archivo fuente eliminado: {archivo}")
            except Exception as e:
                errores.append(f"Error al eliminar {archivo}: {str(e)}")
    
    return archivos_eliminados, errores
