"""Orquestación del pipeline de reportes."""

from __future__ import annotations

import os

from datetime import datetime, timedelta

import pandas as pd

from bess.config.paths import DIRECTORIO_FUENTE, DIRECTORIO_PROCESADOS, DIRECTORIO_REPORTES
from bess.core.console import imprimir_progreso
from bess.core.kvarh import columnas_kvarh as _columnas_kvarh
from bess.cfe.periods import agregar_periodo, obtener_periodo_por_hora
from bess.data.aggregates.accumulated import generar_acumulados
from bess.data.aggregates.bess_daily import generar_bess_diario
from bess.data.aggregates.combined import generar_combinado_por_minuto
from bess.data.aggregates.daily import generar_diarios_con_demandas
from bess.data.ingest.readers import leer_y_agrupar_por_hora

from bess.core.console import log
print = log

def procesar_grupo(ruta_bess, ruta_medidor, prefijo, nombre_medidor, generar_bess_general=False):
    """Procesa un grupo de archivos (BESS + Medidor)"""
    print("\n" + "=" * 70)
    print(f"PROCESANDO GRUPO: BESS vs {nombre_medidor}")
    print("=" * 70)
    
    if not os.path.exists(ruta_bess):
        print(f"ERROR: No se encuentra el archivo BESS: {ruta_bess}")
        return False, f"No se encuentra archivo BESS"
    
    if not os.path.exists(ruta_medidor):
        print(f"ERROR: No se encuentra el archivo {nombre_medidor}: {ruta_medidor}")
        return False, f"No se encuentra archivo {nombre_medidor}"
    
    print(f"\n--- LECTURA Y AGRUPACION POR HORA ({prefijo}) ---")
    df_bess_hora = leer_y_agrupar_por_hora(ruta_bess, f'BESS_{prefijo}')
    df_medidor_hora = leer_y_agrupar_por_hora(ruta_medidor, nombre_medidor)
    
    if len(df_bess_hora) == 0 or len(df_medidor_hora) == 0:
        return False, f"No se pudieron cargar datos validos para {prefijo}"
    
    print(f"\n--- AGREGANDO PERIODO ({prefijo}) ---")
    df_bess_hora_con_periodo = agregar_periodo(df_bess_hora.copy())
    df_medidor_hora_con_periodo = agregar_periodo(df_medidor_hora.copy())
    
    print(f"\n--- GENERANDO ARCHIVOS DE ENERGIA POR HORA ({prefijo}) ---")
    
    df_bess_output = df_bess_hora_con_periodo[['FECHA', 'HORA', 'KWH_REC', 'KWH_ENT', 'PERIODO']].copy()
    nombre_bess_hora = f'ENERGIA_BESS_POR_HORA_{prefijo}.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_bess_hora)
    df_bess_output.to_csv(ruta_salida, index=False)
    print(f"OK {nombre_bess_hora} - {len(df_bess_output)} registros")
    
    if generar_bess_general:
        ruta_general = os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_HORA.csv')
        df_bess_output.to_csv(ruta_general, index=False)
        print(f"OK ENERGIA_BESS_POR_HORA.csv - {len(df_bess_output)} registros (archivo general)")
    
    df_medidor_output = df_medidor_hora_con_periodo[
        ['FECHA', 'HORA', 'FECHA_HORA', 'KWH_REC', 'KWH_ENT', 'PERIODO']
        + _columnas_kvarh(df_medidor_hora_con_periodo)
    ].copy()
    nombre_med_hora = f'ENERGIA_{prefijo}_POR_HORA.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_med_hora)
    df_medidor_output.to_csv(ruta_salida, index=False)
    print(f"OK {nombre_med_hora} - {len(df_medidor_output)} registros")
    
    print(f"\n--- GENERANDO COMBINADO_POR_HORA_{prefijo}.csv ---")
    df_combinado_hora = pd.merge(
        df_bess_hora[['FECHA_HORA', 'KWH_REC', 'KWH_ENT']],
        df_medidor_hora[['FECHA_HORA', 'KWH_REC', 'KWH_ENT']],
        on='FECHA_HORA',
        suffixes=('_BESS', f'_{prefijo}'),
        how='inner'
    )
    
    horas = []
    periodos = []
    for idx, row in df_combinado_hora.iterrows():
        fecha_hora = datetime.strptime(row['FECHA_HORA'], '%d/%m/%Y %H:%M')
        hora = fecha_hora.hour
        if hora == 0:
            hora = 24
        horas.append(hora)
        fecha_periodo = fecha_hora
        if fecha_hora.hour == 0 and fecha_hora.minute == 0:
            fecha_periodo = fecha_periodo - timedelta(days=1)
        periodo = obtener_periodo_por_hora(fecha_periodo, hora)
        periodos.append(periodo)
    
    df_combinado_hora['HORA'] = horas
    df_combinado_hora['PERIODO'] = periodos
    df_combinado_hora['BESS_REC_kW'] = df_combinado_hora['KWH_REC_BESS'] * 12
    df_combinado_hora['BESS_ENT_kW'] = df_combinado_hora['KWH_ENT_BESS'] * 12
    df_combinado_hora[f'{prefijo}_REC_kW'] = df_combinado_hora[f'KWH_REC_{prefijo}'] * 12
    df_combinado_hora[f'{prefijo}_ENT_kW'] = df_combinado_hora[f'KWH_ENT_{prefijo}'] * 12
    df_combinado_hora[f'IUSA_CON_BESS_{prefijo}_kW'] = df_combinado_hora[f'{prefijo}_REC_kW']
    df_combinado_hora[f'IUSA_SIN_BESS_{prefijo}_kW'] = df_combinado_hora[f'{prefijo}_REC_kW'] - df_combinado_hora['BESS_REC_kW'] + df_combinado_hora['BESS_ENT_kW']
    df_combinado_hora['BESS_NETO_kWh'] = df_combinado_hora['KWH_REC_BESS'] - df_combinado_hora['KWH_ENT_BESS']
    df_combinado_hora[f'{prefijo}_NETO_kWh'] = df_combinado_hora[f'KWH_REC_{prefijo}'] - df_combinado_hora[f'KWH_ENT_{prefijo}']
    df_combinado_hora[f'Mejora_BESS_{prefijo}_kWh'] = df_combinado_hora[f'{prefijo}_NETO_kWh'] - df_combinado_hora['BESS_NETO_kWh']
    df_combinado_hora[f'Mejora_BESS_{prefijo}_kW'] = df_combinado_hora[f'Mejora_BESS_{prefijo}_kWh'] * 12
    
    columnas_hora = ['FECHA_HORA', 'HORA', 'PERIODO', 'KWH_REC_BESS', 'KWH_ENT_BESS', 'BESS_REC_kW', 'BESS_ENT_kW',
                     f'KWH_REC_{prefijo}', f'KWH_ENT_{prefijo}', f'{prefijo}_REC_kW', f'{prefijo}_ENT_kW',
                     'BESS_NETO_kWh', f'{prefijo}_NETO_kWh', f'Mejora_BESS_{prefijo}_kWh', f'Mejora_BESS_{prefijo}_kW',
                     f'IUSA_CON_BESS_{prefijo}_kW', f'IUSA_SIN_BESS_{prefijo}_kW']
    
    nombre_comb_hora = f'COMBINADO_POR_HORA_{prefijo}.csv'
    ruta_salida = os.path.join(DIRECTORIO_REPORTES, nombre_comb_hora)
    df_combinado_hora[columnas_hora].to_csv(ruta_salida, index=False)
    print(f"OK {nombre_comb_hora} - {len(df_combinado_hora)} registros")
    
    generar_combinado_por_minuto(ruta_bess, ruta_medidor, prefijo)
    generar_diarios_con_demandas(prefijo)
    generar_acumulados(prefijo)
    
    print(f"\nOK Grupo {prefijo} procesado exitosamente")
    return True, f"Grupo {prefijo} procesado exitosamente"

# ========== REPORTE PDF — ESTILOS Y HELPERS ==========
_PDF = {
    'primary': '#1a5276',
    'secondary': '#2e86c1',
    'base': '#2980b9',
    'intermedio': '#b7950b',
    'punta': '#c0392b',
    'success': '#27ae60',
    'carga': '#27ae60',
    'descarga': '#e74c3c',
    'iusa': '#2e86c1',
    'bg_light': '#f4f7f9',
    'bg_row': '#f8fafb',
    'bg_arbitraje': '#eafaf1',
    'border': '#d5dce3',
    'text_muted': '#7f8c8d',
    'text_dark': '#2c3e50',
    'content_width_in': 10.35,
    'chart_height_in': 3.85,
    # Ancho tabla = título sección (Periodo + Base + Intermedio + Punta + Total)
    'table_cols_in': (1.68, 0.86, 0.86, 0.86, 0.98),
    'logo_width_in': 1.3125,
    'logo_max_height_in': 0.725,
    'logo_col_in': 1.44,
    'gap_chart_table_in': 0.28,
}


def _validar_archivos_filtrados():
    """Comprueba que existan los CSV filtrados antes de generar reportes."""
    requeridos = {
        'BESS_Filtrado.csv': os.path.join(DIRECTORIO_PROCESADOS, 'BESS_Filtrado.csv'),
        'ION_Filtrado.csv': os.path.join(DIRECTORIO_PROCESADOS, 'ION_Filtrado.csv'),
        'Banco1_Filtrado.csv': os.path.join(DIRECTORIO_PROCESADOS, 'Banco1_Filtrado.csv'),
    }
    faltantes = [nombre for nombre, ruta in requeridos.items() if not os.path.exists(ruta)]
    if faltantes:
        return False, (
            f"Faltan archivos filtrados: {', '.join(faltantes)}. "
            "Ejecute Filtrar antes de Generar reportes."
        )
    return True, ""


def reporte_bess():
    """Función principal de ReporteBESS"""
    print("=" * 60)
    print("PROCESAMIENTO DE DATOS DE ENERGIA - REGION CENTRAL")
    print("PROCESAMIENTO DE DOS GRUPOS: BESS vs ION y BESS vs BANCO1")
    print("=" * 60)

    ok, msg = _validar_archivos_filtrados()
    if not ok:
        print(f"ERROR: {msg}")
        return False, msg, msg

    RUTA_BESS = os.path.join(DIRECTORIO_PROCESADOS, 'BESS_Filtrado.csv')
    RUTA_ION = os.path.join(DIRECTORIO_PROCESADOS, 'ION_Filtrado.csv')
    RUTA_BANCO = os.path.join(DIRECTORIO_PROCESADOS, 'Banco1_Filtrado.csv')
    
    print(f"\nDirectorio de archivos fuente: {DIRECTORIO_PROCESADOS}")
    print(f"Directorio de reportes: {DIRECTORIO_REPORTES}")
    
    resultado_ion, msg_ion = procesar_grupo(RUTA_BESS, RUTA_ION, 'ION', 'ION', generar_bess_general=True)
    resultado_banco, msg_banco = procesar_grupo(RUTA_BESS, RUTA_BANCO, 'BANCO', 'Banco1', generar_bess_general=False)
    
    print("\n" + "=" * 60)
    print("GENERANDO ARCHIVOS GENERALES DEL BESS")
    print("=" * 60)
    
    if os.path.exists(os.path.join(DIRECTORIO_REPORTES, 'ENERGIA_BESS_POR_HORA.csv')):
        generar_bess_diario()
    else:
        print("No se encontro ENERGIA_BESS_POR_HORA.csv")
    
    print("\n" + "=" * 60)
    print("RESUMEN DEL PROCESO")
    print("=" * 60)
    print("\nGRUPO 1: BESS vs ION - " + ("✅ Éxito" if resultado_ion else "❌ Falló"))
    print("GRUPO 2: BESS vs BANCO1 - " + ("✅ Éxito" if resultado_banco else "❌ Falló"))
    print("\n" + "=" * 60)
    print("=== FIN DEL PROCESO ===")
    
    return resultado_ion and resultado_banco, msg_ion, msg_banco
