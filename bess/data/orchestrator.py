"""Orquestación del pipeline de reportes."""

from __future__ import annotations

import os

from bess.config.constants import etiqueta_medidor
from bess.config.paths import DIRECTORIO_PROCESADOS, DIRECTORIO_REPORTES
from bess.config.subestaciones import SUBESTACIONES, medidor_consumo_por_prefijo
from bess.core.consumo import usa_consumo_neto
from bess.data.aggregates.accumulated import generar_acumulados
from bess.data.aggregates.bess_daily import generar_bess_diario, generar_bess_diario_prefijo
from bess.data.aggregates.combined import generar_combinado_por_minuto
from bess.data.aggregates.granja import generar_reportes_granja
from bess.data.aggregates.daily import generar_diarios_con_demandas
from bess.data.ingest.readers import leer_sin_agrupar

from bess.core.console import log

print = log


def procesar_grupo(ruta_bess, ruta_medidor, prefijo, nombre_medidor):
    """Procesa BESS + medidor: combinado 5 min → diario → acumulados."""
    med = medidor_consumo_por_prefijo(prefijo)
    sub = next(
        (s for s in SUBESTACIONES if any(m.prefijo == prefijo for m in s.medidores_consumo)),
        None,
    )
    if sub and med:
        etiqueta = f"{sub.nombre} · {med.etiqueta}"
    else:
        etiqueta = etiqueta_medidor(prefijo)

    print("\n" + "=" * 70)
    print(f"PROCESANDO {etiqueta}")
    print("=" * 70)

    if not os.path.exists(ruta_bess):
        print(f"ERROR: No se encuentra el archivo BESS: {ruta_bess}")
        return False, "No se encuentra archivo BESS"

    if not os.path.exists(ruta_medidor):
        print(f"ERROR: No se encuentra el archivo de consumo: {ruta_medidor}")
        return False, f"No se encuentra archivo de consumo ({etiqueta})"

    df_bess = leer_sin_agrupar(ruta_bess)
    df_medidor = leer_sin_agrupar(ruta_medidor, prefijo_consumo=prefijo)
    if len(df_bess) == 0 or len(df_medidor) == 0:
        return False, f"No se pudieron cargar datos validos para {etiqueta}"

    if usa_consumo_neto(prefijo):
        print(f"  {prefijo}: energía con KWH_NETO por intervalo de 5 min")

    print(f"  BESS: {len(df_bess)} registros · {prefijo}: {len(df_medidor)} registros")

    df_combinado = generar_combinado_por_minuto(ruta_bess, ruta_medidor, prefijo)
    if df_combinado is None or len(df_combinado) == 0:
        return False, f"No se genero combinado por minuto para {etiqueta}"

    if generar_diarios_con_demandas(prefijo) is None:
        return False, f"No se genero archivo diario para {etiqueta}"

    generar_acumulados(prefijo)

    print(f"\nOK {etiqueta} procesada exitosamente")
    return True, f"{etiqueta} procesada exitosamente"


def _validar_archivos_filtrados():
    """Comprueba que existan los CSV filtrados de cada subestación."""
    faltantes: list[str] = []
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            ruta = os.path.join(DIRECTORIO_PROCESADOS, med.consumo_filtrado)
            if not os.path.exists(ruta):
                faltantes.append(med.consumo_filtrado)
        ruta_bess = os.path.join(DIRECTORIO_PROCESADOS, sub.bess_filtrado)
        if not os.path.exists(ruta_bess):
            faltantes.append(sub.bess_filtrado)
    if faltantes:
        return False, (
            f"Faltan archivos filtrados: {', '.join(faltantes)}. "
            "Ejecute Filtrar antes de Generar reportes."
        )
    return True, ""


def reporte_bess():
    """Genera reportes CSV para todas las subestaciones."""
    print("=" * 60)
    print("PROCESAMIENTO DE DATOS DE ENERGIA - SUBESTACIONES IUSA")
    print("=" * 60)

    ok, msg = _validar_archivos_filtrados()
    if not ok:
        print(f"ERROR: {msg}")
        return False, {"_error": msg}

    print(f"\nDirectorio de archivos procesados: {DIRECTORIO_PROCESADOS}")
    print(f"Directorio de reportes: {DIRECTORIO_REPORTES}")

    mensajes: dict[str, str] = {}
    resultados: list[bool] = []

    for sub in SUBESTACIONES:
        ruta_bess = os.path.join(DIRECTORIO_PROCESADOS, sub.bess_filtrado)
        for med in sub.medidores_consumo:
            ruta_consumo = os.path.join(DIRECTORIO_PROCESADOS, med.consumo_filtrado)
            exito, mensaje = procesar_grupo(
                ruta_bess,
                ruta_consumo,
                med.prefijo,
                med.consumo_lectura,
            )
            mensajes[med.prefijo] = mensaje
            resultados.append(exito)

    print("\n" + "=" * 60)
    print("GENERANDO ARCHIVOS DIARIOS DEL BESS")
    print("=" * 60)

    if os.path.exists(os.path.join(DIRECTORIO_REPORTES, "COMBINADO_POR_MINUTO_ION.csv")):
        generar_bess_diario()
    else:
        print("No se encontro COMBINADO_POR_MINUTO_ION.csv")

    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            if med.prefijo.upper() in ("ION", "BANCO"):
                continue
            ruta_minuto = os.path.join(
                DIRECTORIO_REPORTES, f"COMBINADO_POR_MINUTO_{med.prefijo}.csv"
            )
            if os.path.exists(ruta_minuto):
                generar_bess_diario_prefijo(med.prefijo)
            else:
                print(f"No se encontro COMBINADO_POR_MINUTO_{med.prefijo}.csv")
            break

    print("\n" + "=" * 60)
    print("GENERANDO REPORTES GRANJA (solo energía)")
    print("=" * 60)
    for sub in SUBESTACIONES:
        if not sub.granja_filtrado or not sub.granja_bd:
            continue
        ruta_granja = os.path.join(DIRECTORIO_PROCESADOS, sub.granja_filtrado)
        if os.path.exists(ruta_granja):
            generar_reportes_granja(ruta_granja, sub.granja_bd)
        else:
            print(f"⚠️ {sub.nombre}: sin {sub.granja_filtrado} (omitido)")

    print("\n" + "=" * 60)
    print("RESUMEN DEL PROCESO")
    print("=" * 60)
    idx = 0
    for sub in SUBESTACIONES:
        for med in sub.medidores_consumo:
            exito = resultados[idx] if idx < len(resultados) else False
            idx += 1
            estado = "✅ Éxito" if exito else "❌ Falló"
            print(f"{sub.nombre} · {med.etiqueta}: {estado}")
    print("\n" + "=" * 60)
    print("=== FIN DEL PROCESO ===")

    return all(resultados), mensajes
