# bess_core.py
"""
BESS - Fachada de compatibilidad.
Re-exporta el pipeline de datos, CFE, tarifas y reportes PDF desde bess.*.
"""

import warnings

warnings.filterwarnings("ignore")

# ========== CONFIGURACIÓN GLOBAL (bess.config + bess.core) ==========
from bess.config.constants import ARCHIVO_TARIFAS, TIPOS_TARIFA
from bess.config.paths import (
    DIRECTORIO_BASE,
    DIRECTORIO_FUENTE,
    DIRECTORIO_PROCESADOS,
    DIRECTORIO_REPORTES,
    DIRECTORIO_REPORTES_DIARIOS,
    DIRECTORIO_TARIFAS,
)
from bess.core.kvarh import (
    COLUMNAS_KVARH as _COLUMNAS_KVARH,
    columnas_kvarh as _columnas_kvarh,
    columnas_kvarh_prefijo as _columnas_kvarh_prefijo,
    kvarh_total as _kvarh_total,
    normalizar_columnas_kvarh as _normalizar_columnas_kvarh,
)
from bess.core.numbers import (
    a_num as _a_num,
    fmt_kwh,
    kwh_para_calculo,
    redondear_arriba_kw,
    redondear_arriba_mxn,
    redondear_kwh,
    redondear_mxn_energia,
    sumar_energia,
)

# ========== CONSOLA Y UTILIDADES (bess.core) ==========
from bess.core.console import crear_barra, imprimir_progreso as _imprimir_progreso, log as print
from bess.core.dates import normalizar_fecha, validar_y_convertir_fecha

# ========== PERIODOS CFE (bess.cfe) ==========
from bess.cfe.periods import (
    agregar_periodo,
    es_festivo,
    obtener_periodo_por_fecha_hora,
    obtener_periodo_por_hora,
    obtener_temporada,
)

# ========== PIPELINE DE DATOS (bess.data) ==========
from bess.data.ingest.identify import identificar_y_renombrar_archivos
from bess.data.ingest.readers import leer_archivo_perfil, leer_sin_agrupar, leer_y_agrupar_por_hora
from bess.data.pipeline.clean import generar_archivo_limpio
from bess.data.pipeline.filter import filtrar_datos, limpiar_archivos_fuente
from bess.data.pipeline.verify import procesar_archivo_verificacion, verificar_datos_fuente
from bess.data.aggregates.accumulated import generar_acumulados
from bess.data.aggregates.bess_daily import generar_bess_diario
from bess.data.aggregates.combined import generar_combinado_por_minuto
from bess.data.aggregates.daily import generar_diarios_con_demandas
from bess.data.orchestrator import (
    _validar_archivos_filtrados,
    procesar_grupo,
    reporte_bess,
)

# ========== TARIFAS, COSTOS CFE Y PDF (bess.tariffs, bess.cfe, bess.reports) ==========
from bess.tariffs.loader import cargar_tarifas
from bess.cfe.arbitrage import calcular_arbitraje_dia
from bess.cfe.daily_data import (
    energia_diaria_tiene_sin_bess,
    fila_por_fecha_csv as _fila_por_fecha_csv,
    obtener_bess_energia_dia,
)
from bess.cfe.energy import calcular_costo_energia_dia
from bess.reports.assets import buscar_logo, formatear_fecha_espanol
from bess.reports.daily_pdf import generar_reporte_pdf
