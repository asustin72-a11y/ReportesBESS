"""Verificación de archivos fuente."""

from __future__ import annotations

import os
import shutil
import sys
from datetime import timedelta

import pandas as pd

from bess.config import rutas as rutas_mod
from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS
from bess.config.catalog import obtener_catalogo
from bess.config.subestaciones import SUBESTACIONES, archivos_fuente_subestacion
from bess.data.pipeline.bess_consolidate import consolidar_bess_subestacion
from bess.core.console import crear_barra, imprimir_progreso as _imprimir_progreso, log
from bess.data.ingest.identify import identificar_y_renombrar_archivos
from bess.data.ingest.readers import leer_archivo_perfil

print = log

_PRIMER_INTERVALO_DIA = (0, 5)
# Solo ION (Modbus). BESS, Banco 1 y granja (API) deben conservar/rellenar 00:00.
_ARCHIVOS_SALTAR_MEDIANOCHE_ION = frozenset(
    rutas_mod.nombre_archivo_medidor(m.nombre)
    for m in obtener_catalogo().medidores
    if m.descarga == "ION"
)


def _saltar_slot_medianoche_opcional(esperada, siguiente_en_archivo) -> bool:
    """
    Al rellenar huecos: tras 23:55 el reloj cae en 00:00, pero el medidor puede
    empezar el día en 00:05. No insertar un cero en 00:00 si ya viene 00:05.
    Si el medidor sí trae 00:00 con datos, ese registro se conserva sin saltar.
    """
    if esperada.hour != 0 or esperada.minute != 0:
        return False
    if siguiente_en_archivo <= esperada:
        return False
    if siguiente_en_archivo.date() != esperada.date():
        return False
    return (
        siguiente_en_archivo.hour == _PRIMER_INTERVALO_DIA[0]
        and siguiente_en_archivo.minute == _PRIMER_INTERVALO_DIA[1]
    )


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


def procesar_archivo_verificacion(ruta_origen, ruta_destino, nombre_archivo):
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
        usar_salto_medianoche = nombre_archivo in _ARCHIVOS_SALTAR_MEDIANOCHE_ION
        
        while x < num_registros:
            fecha_archivo = perfil_sin_duplicados.iloc[x, 0]
            
            if fecha_archivo != Fecha_Correcta:
                if usar_salto_medianoche and _saltar_slot_medianoche_opcional(
                    Fecha_Correcta, fecha_archivo
                ):
                    Fecha_Correcta = fecha_archivo
                    continue

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
            nombres.append("Cogeneración")
        partes.append(f"{sub.nombre}: {', '.join(nombres)}")

    mensaje = "Verificación completada — " + "; ".join(partes) if partes else (
        f"Verificación OK ({len(verificados)} archivo(s)): {', '.join(verificados)}"
    )
    if omitidos:
        mensaje += f". Sin archivo en fuente: {', '.join(omitidos)}"
    return mensaje
