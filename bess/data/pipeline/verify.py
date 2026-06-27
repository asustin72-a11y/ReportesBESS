"""Verificación de archivos fuente."""

from __future__ import annotations

import os
import shutil
import sys
from datetime import timedelta

import pandas as pd

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.core.console import crear_barra, imprimir_progreso as _imprimir_progreso, log
from bess.data.ingest.identify import identificar_y_renombrar_archivos
from bess.data.ingest.readers import leer_archivo_perfil

print = log

def procesar_archivo_verificacion(ruta_origen, ruta_destino, nombre_archivo, intercambiar=False):
    """
    Procesa un archivo CSV verificando duplicados y registros faltantes
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
        
        # Eliminar duplicados
        perfil_sin_duplicados = perfil.drop_duplicates(subset=['Fecha'], keep='first')
        renglones_duplicados = len(perfil) - len(perfil_sin_duplicados)
        print(f"🗑️ Renglones duplicados eliminados: {renglones_duplicados}")
        
        perfil_sin_duplicados = perfil_sin_duplicados.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
        
        # Verificar registros faltantes
        num_registros = len(perfil_sin_duplicados)
        fi = perfil_sin_duplicados.iloc[0, 0]
        ff = perfil_sin_duplicados.iloc[num_registros - 1, 0]
        dias = (ff - fi).days + 1
        registros_esperados = dias * 288
        
        print(f"📅 Fecha inicial: {fi.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 Fecha final: {ff.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Registros esperados: {registros_esperados}")
        print(f"📊 Registros actuales: {num_registros}")
        
        # Insertar registros faltantes
        Fecha_Correcta = fi
        x = 0
        Faltantes = 0
        Perfiles_faltantes = None
        primera_vez = 0
        Frecuencia_Perfil_MIN = 5
        columnas = perfil.columns.tolist()
        
        print("\n⏳ Verificando registros faltantes...")
        
        while x < num_registros:
            fecha_archivo = perfil_sin_duplicados.iloc[x, 0]
            
            if fecha_archivo != Fecha_Correcta:
                nuevo_registro = {'Fecha': Fecha_Correcta}
                for col in columnas[1:]:
                    nuevo_registro[col] = 0
                
                if primera_vez == 0:
                    Perfiles_faltantes = pd.DataFrame([nuevo_registro])
                    primera_vez = 1
                else:
                    Perfiles_faltantes = pd.concat([Perfiles_faltantes, pd.DataFrame([nuevo_registro])], ignore_index=True)
                
                x = x - 1
                Faltantes = Faltantes + 1
            
            x = x + 1
            Fecha_Correcta = Fecha_Correcta + timedelta(minutes=Frecuencia_Perfil_MIN)
            
            porcentaje = (x / num_registros) * 100
            barra = crear_barra(porcentaje, 40)
            _imprimir_progreso(f"{barra} {porcentaje:.1f}%")
        
        if getattr(sys.stdout, 'isatty', lambda: False)():
            print()
        print("✅ Verificación completada")
        print(f"📝 Registros faltantes insertados: {Faltantes}")
        
        if Faltantes != 0:
            perfil_completo = pd.concat([perfil_sin_duplicados, Perfiles_faltantes], ignore_index=True)
        else:
            perfil_completo = perfil_sin_duplicados
        
        perfil_completo = perfil_completo.sort_values(by='Fecha', ascending=True).reset_index(drop=True)
        
        os.makedirs(ruta_destino, exist_ok=True)
        ruta_guardado = os.path.join(ruta_destino, nombre_archivo)
        
        if os.path.exists(ruta_guardado):
            backup_path = ruta_guardado.replace('.csv', '_backup.csv')
            shutil.copy2(ruta_guardado, backup_path)
            print(f"💾 Backup creado: {os.path.basename(backup_path)}")
        
        # Guardar con formato de fecha estandarizado
        perfil_completo['Fecha'] = perfil_completo['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S')
        try:
            perfil_completo.to_csv(ruta_guardado, index=False, encoding='utf-8-sig')
        except OSError as e:
            print(
                f"❌ No se pudo guardar {nombre_archivo}: {e}. "
                "Cierre Excel u otro programa que tenga abierto el CSV en ArchivosProcesados."
            )
            return False
        print(f"✅ Archivo procesado guardado: {ruta_guardado}")
        print(f"📊 Registros finales: {len(perfil_completo)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al procesar {nombre_archivo}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verificar_datos_fuente():
    """Función principal de verificación de datos fuente. Retorna (éxito, mensaje)."""
    
    # PASO 1: Identificar y renombrar archivos
    identificar_y_renombrar_archivos()
    
    # PASO 2: Procesar archivos estándar
    archivos = ['Banco1.csv', 'BESS.csv', 'ION.csv']
    
    print("\n" + "="*70)
    print("🔍 VERIFICADOR DE PERFILES DE CARGA")
    print("="*70)
    print(f"📁 Carpeta origen: {DIRECTORIO_FUENTE}")
    print(f"📁 Carpeta destino: {DIRECTORIO_PROCESADOS}")
    print("="*70)
    
    if not os.path.exists(DIRECTORIO_FUENTE):
        print(f"❌ Error: No existe la carpeta {DIRECTORIO_FUENTE}")
        os.makedirs(DIRECTORIO_FUENTE, exist_ok=True)
        print(f"✅ Carpeta creada: {DIRECTORIO_FUENTE}")
        return False, f"No existía la carpeta {DIRECTORIO_FUENTE}. Coloque ION.csv, BESS.csv y Banco1.csv ahí."
    
    archivos_encontrados = []
    for archivo in archivos:
        ruta_completa = os.path.join(DIRECTORIO_FUENTE, archivo)
        if os.path.exists(ruta_completa):
            archivos_encontrados.append(archivo)
    
    if not archivos_encontrados:
        print(f"❌ No se encontraron archivos en {DIRECTORIO_FUENTE}")
        return False, (
            "No se encontraron archivos en ArchivosFuente. "
            "Copie ION.csv, BESS.csv y Banco1.csv en data/ArchivosFuente."
        )
    
    print(f"\n📋 Archivos encontrados: {', '.join(archivos_encontrados)}")
    
    resultados = {}
    for archivo in archivos:
        if os.path.exists(os.path.join(DIRECTORIO_FUENTE, archivo)):
            intercambiar = (archivo == 'Banco1.csv')
            resultados[archivo] = procesar_archivo_verificacion(
                DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, archivo, intercambiar
            )
        else:
            print(f"\n⚠️ Archivo no encontrado: {archivo} (omitido)")
            resultados[archivo] = False
    
    print("\n" + "="*70)
    print("📊 RESUMEN FINAL VERIFICACIÓN")
    print("="*70)
    for archivo, exito in resultados.items():
        estado = "✅ Éxito" if exito else "❌ Falló"
        print(f"   {archivo}: {estado}")
    
    if all(resultados.values()):
        return True, "Verificación completada para ION, BESS y Banco1."

    faltantes = [a for a in archivos if not os.path.exists(os.path.join(DIRECTORIO_FUENTE, a))]
    fallidos = [a for a, ok in resultados.items() if not ok]
    partes = []
    if faltantes:
        partes.append(f"faltan en fuente: {', '.join(faltantes)}")
    if fallidos:
        partes.append(f"error al procesar: {', '.join(fallidos)}")
    detalle = '; '.join(partes)
    return False, (
        f"Verificación incompleta ({detalle}). "
        "Cierre Excel u otros programas que tengan abiertos los CSV en ArchivosProcesados."
    )
