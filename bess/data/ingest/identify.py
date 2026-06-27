"""Identificación y renombrado de archivos fuente."""

from __future__ import annotations

import os
import shutil

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS

from bess.core.console import log
print = log

def identificar_y_renombrar_archivos():
    """
    Identifica archivos en DIRECTORIO_FUENTE por patrones en el nombre
    y los renombra a los nombres estándar: ION.csv, BESS.csv, Banco1.csv
    """
    # Patrones de búsqueda para cada archivo
    patrones = {
        'ION': ['IUSA1', 'IUSA', 'ION'],
        'BESS': ['CS3878', 'BESS'],
        'Banco1': ['CS1996', 'BANCO1', 'Banco1']
    }
    
    renombrados = {}
    errores = []
    
    if not os.path.exists(DIRECTORIO_FUENTE):
        os.makedirs(DIRECTORIO_FUENTE, exist_ok=True)
        return {'renombrados': {}, 'errores': ['Directorio fuente no existe, se creó vacío']}
    
    archivos = os.listdir(DIRECTORIO_FUENTE)
    
    print("\n" + "=" * 70)
    print("🔍 IDENTIFICANDO ARCHIVOS POR PATRÓN")
    print("=" * 70)
    print(f"📁 Archivos encontrados en {DIRECTORIO_FUENTE}:")
    for a in archivos:
        print(f"   - {a}")
    print("=" * 70)
    
    for nombre_estandar, patrones_busqueda in patrones.items():
        archivo_encontrado = None
        
        for archivo in archivos:
            archivo_lower = archivo.lower()
            for patron in patrones_busqueda:
                if patron.lower() in archivo_lower:
                    archivo_encontrado = archivo
                    break
            if archivo_encontrado:
                break
        
        if archivo_encontrado:
            ruta_origen = os.path.join(DIRECTORIO_FUENTE, archivo_encontrado)
            nombre_destino = f'{nombre_estandar}.csv'
            ruta_destino = os.path.join(DIRECTORIO_FUENTE, nombre_destino)

            # Ya está con el nombre estándar (p. ej. ION.csv → ION.csv)
            if os.path.normcase(ruta_origen) == os.path.normcase(ruta_destino):
                renombrados[nombre_estandar] = {
                    'origen': archivo_encontrado,
                    'destino': nombre_destino,
                }
                print(f'✅ {archivo_encontrado} (nombre estándar, sin cambios)')
                continue

            try:
                # Si el archivo destino ya existe, hacer backup
                if os.path.exists(ruta_destino):
                    backup_path = ruta_destino.replace('.csv', '_backup.csv')
                    shutil.move(ruta_destino, backup_path)
                    print(f'💾 Backup creado: {os.path.basename(backup_path)}')

                os.rename(ruta_origen, ruta_destino)
                renombrados[nombre_estandar] = {
                    'origen': archivo_encontrado,
                    'destino': nombre_destino,
                }
                print(f'✅ {archivo_encontrado} → {nombre_destino}')
            except Exception as e:
                errores.append(f'Error al renombrar {archivo_encontrado}: {str(e)}')
        else:
            errores.append(f"⚠️ No se encontró archivo que coincida con los patrones de {nombre_estandar}")
    
    print("=" * 70)
    if renombrados:
        print("📋 Archivos renombrados:")
        for nombre, info in renombrados.items():
            print(f"   ✅ {info['origen']} → {info['destino']}")
    if errores:
        print("⚠️ Errores/Advertencias:")
        for error in errores:
            print(f"   {error}")
    print("=" * 70)
    
    return {'renombrados': renombrados, 'errores': errores}

# ========== FUNCIONES DE LECTURA DE ARCHIVOS ==========
