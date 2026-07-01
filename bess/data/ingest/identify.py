"""Identificación y renombrado de archivos fuente."""

from __future__ import annotations

import os
import shutil

from bess.config.paths import DIRECTORIO_FUENTE

from bess.core.console import log
print = log

# Orden: patrones más específicos primero; cada archivo solo puede asignarse una vez.
_REGLAS_IDENTIFICACION: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("ION_IUSA2", ("ION_IUSA2", "205.203"), ("BESS", "GRANJA")),
    ("GRANJA_IUSA2", ("GRANJA_IUSA2", "MEGA_total", "GRANJA"), ()),
    ("BESS_IUSA2", ("BESS_IUSA2", "BESSIUSA2", "CS3190"), ()),
    ("Banco1", ("CS1996", "BANCO1", "Banco1"), ()),
    ("ION", ("IUSA1", "ION"), ("IUSA2", "BESS", "BANCO", "CS3190", "CS3878", "CS1996")),
    ("BESS", ("CS3878", "BESS"), ("IUSA2", "CS3190", "BANCO", "CS1996")),
)


def _coincide_patron(
    archivo: str,
    patrones_busqueda: tuple[str, ...],
    excluir: tuple[str, ...],
) -> bool:
    archivo_lower = archivo.lower()
    if any(ex.lower() in archivo_lower for ex in excluir):
        return False
    return any(patron.lower() in archivo_lower for patron in patrones_busqueda)


def identificar_y_renombrar_archivos():
    """
    Identifica archivos en DIRECTORIO_FUENTE por patrones en el nombre
    y los renombra a los nombres estándar de cada subestación.
    """
    renombrados = {}
    errores = []

    if not os.path.exists(DIRECTORIO_FUENTE):
        os.makedirs(DIRECTORIO_FUENTE, exist_ok=True)
        return {'renombrados': {}, 'errores': ['Directorio fuente no existe, se creó vacío']}

    archivos = [
        nombre for nombre in os.listdir(DIRECTORIO_FUENTE)
        if nombre.lower().endswith('.csv') and '_backup' not in nombre.lower()
    ]
    archivos_usados: set[str] = set()

    print("\n" + "=" * 70)
    print("🔍 IDENTIFICANDO ARCHIVOS POR PATRÓN")
    print("=" * 70)
    print(f"📁 Archivos encontrados en {DIRECTORIO_FUENTE}:")
    for a in archivos:
        print(f"   - {a}")
    print("=" * 70)

    for nombre_estandar, patrones_busqueda, excluir in _REGLAS_IDENTIFICACION:
        nombre_destino = f'{nombre_estandar}.csv'
        ruta_destino = os.path.join(DIRECTORIO_FUENTE, nombre_destino)

        # Priorizar el archivo que ya tiene el nombre estándar (p. ej. export SQLite).
        if nombre_destino in archivos and nombre_destino not in archivos_usados:
            archivos_usados.add(nombre_destino)
            renombrados[nombre_estandar] = {
                'origen': nombre_destino,
                'destino': nombre_destino,
            }
            print(f'✅ {nombre_destino} (nombre estándar, sin cambios)')
            continue

        archivo_encontrado = None

        for archivo in archivos:
            if archivo in archivos_usados:
                continue
            if _coincide_patron(archivo, patrones_busqueda, excluir):
                archivo_encontrado = archivo
                break

        if archivo_encontrado:
            archivos_usados.add(archivo_encontrado)
            ruta_origen = os.path.join(DIRECTORIO_FUENTE, archivo_encontrado)

            if os.path.normcase(ruta_origen) == os.path.normcase(ruta_destino):
                renombrados[nombre_estandar] = {
                    'origen': archivo_encontrado,
                    'destino': nombre_destino,
                }
                print(f'✅ {archivo_encontrado} (nombre estándar, sin cambios)')
                continue

            backup_path = ruta_destino.replace('.csv', '_backup.csv')
            try:
                if os.path.exists(ruta_destino):
                    shutil.move(ruta_destino, backup_path)
                    print(f'💾 Backup creado: {os.path.basename(backup_path)}')

                os.rename(ruta_origen, ruta_destino)
                renombrados[nombre_estandar] = {
                    'origen': archivo_encontrado,
                    'destino': nombre_destino,
                }
                print(f'✅ {archivo_encontrado} → {nombre_destino}')
            except OSError as e:
                if os.path.exists(backup_path) and not os.path.exists(ruta_destino):
                    shutil.move(backup_path, ruta_destino)
                    print(f'↩️ Restaurado {nombre_destino} tras error de renombrado')
                errores.append(f'Error al renombrar {archivo_encontrado}: {str(e)}')
        else:
            errores.append(
                f"⚠️ No se encontró archivo que coincida con los patrones de {nombre_estandar}"
            )

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
