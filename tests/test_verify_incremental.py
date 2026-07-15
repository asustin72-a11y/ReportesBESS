"""Pruebas de equivalencia para el modo incremental de verify.py.

procesar_archivo_verificacion() ahora, si ya existe un CSV procesado,
solo verifica (dedup + relleno de huecos) las filas nuevas desde el
cursor (ultima Fecha ya escrita) y las anexa, en vez de releer y
reprocesar todo el historico en cada sincronizacion. Estas pruebas
comprueban que varias sincronizaciones incrementales sucesivas
producen exactamente el mismo CSV final que una sola corrida completa
sobre el dataset combinado -- esa equivalencia es la propiedad que no
se puede romper: es la que garantiza que el cambio no altera los datos
que alimentan la facturacion.

Regla de negocio: el dia opera de 00:05 a 00:00 del dia siguiente (288
perfiles/dia); el 00:00 es el cierre del dia anterior, no el inicio del
entrante. Por eso cualquier 00:00 que falte *dentro* del rango real de
datos es un hueco como cualquier otro y se rellena con cero -- sin
excepcion por fuente (antes ION tenia una excepcion aqui; se alineo con
esta regla para que los 288 perfiles/dia se cumplan siempre que el dia
completo este en rango).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bess.data.pipeline.verify import procesar_archivo_verificacion


def _escribir_csv(path, fechas, seed_a, seed_b):
    df = pd.DataFrame({
        'Fecha': fechas.strftime('%Y-%m-%d %H:%M:%S'),
        'KWH_REC': np.round(np.random.default_rng(seed_a).random(len(fechas)) * 100, 3),
        'KWH_ENT': np.round(np.random.default_rng(seed_b).random(len(fechas)) * 10, 3),
    })
    df.to_csv(path, index=False, encoding='utf-8-sig')


def _correr_incremental_vs_completo(tmp_path, nombre_archivo, fechas_reales, cortes):
    """Corre N sincronizaciones incrementales sucesivas y una corrida completa
    equivalente sobre el dataset final; devuelve (df_incremental, df_completo)."""
    origen = tmp_path / 'fuente'
    dest_inc = tmp_path / 'proc_incremental'
    dest_full = tmp_path / 'proc_completo'
    for d in (origen, dest_inc, dest_full):
        d.mkdir()

    for i, corte in enumerate(cortes, 1):
        subset = fechas_reales[fechas_reales <= corte]
        _escribir_csv(origen / nombre_archivo, subset, seed_a=1, seed_b=2)
        ok = procesar_archivo_verificacion(str(origen), str(dest_inc), nombre_archivo)
        assert ok, f"sync incremental {i} fallo"

    _escribir_csv(origen / nombre_archivo, fechas_reales, seed_a=1, seed_b=2)
    ok = procesar_archivo_verificacion(str(origen), str(dest_full), nombre_archivo)
    assert ok, "corrida completa fallo"

    df_inc = pd.read_csv(dest_inc / nombre_archivo, encoding='utf-8-sig')
    df_full = pd.read_csv(dest_full / nombre_archivo, encoding='utf-8-sig')
    return df_inc, df_full


def test_incremental_equivale_a_completo_con_huecos(tmp_path):
    """Archivo con huecos aleatorios, verificado en 3 sincronizaciones."""
    rng = np.random.default_rng(42)
    fechas_completas = pd.date_range('2026-01-01 00:05:00', '2026-01-11 00:00:00', freq='5min')
    fechas_reales = fechas_completas[rng.random(len(fechas_completas)) > 0.05]
    cortes = [
        pd.Timestamp('2026-01-04 23:55:00'),
        pd.Timestamp('2026-01-07 12:00:00'),
        fechas_reales.max(),
    ]

    df_inc, df_full = _correr_incremental_vs_completo(
        tmp_path, 'ARCHIVO_CONSUMO.csv', fechas_reales, cortes
    )

    assert df_inc.equals(df_full)
    # El relleno de huecos debio actuar: mas filas que las "reales" originales.
    assert len(df_inc) > len(fechas_reales)


def test_incremental_rellena_medianoche_faltante_dentro_del_rango(tmp_path):
    """Si falta el 00:00 de un dia que si esta en rango (no el primero del
    historico), se rellena con cero como cualquier otro hueco -- para
    cualquier archivo, ION incluido (ya no hay excepcion por fuente)."""
    fechas_completas = pd.date_range('2026-02-01 00:05:00', '2026-02-08 00:00:00', freq='5min')
    # Quitar especificamente el 00:00 del 2026-02-04 (dia intermedio, con
    # datos antes y despues dentro del mismo rango) para simular el hueco.
    medianoche_faltante = pd.Timestamp('2026-02-04 00:00:00')
    fechas_reales = fechas_completas[fechas_completas != medianoche_faltante]

    cortes = [
        pd.Timestamp('2026-02-03 23:55:00'),
        pd.Timestamp('2026-02-06 10:00:00'),
        fechas_reales.max(),
    ]

    df_inc, df_full = _correr_incremental_vs_completo(
        tmp_path, 'ION_Testigo_IUSA1.csv', fechas_reales, cortes
    )

    assert df_inc.equals(df_full)
    fila = df_inc[df_inc['Fecha'] == '2026-02-04 00:00:00']
    assert len(fila) == 1
    assert (fila[['KWH_REC', 'KWH_ENT']] == 0).all(axis=None)


def test_sync_sin_datos_nuevos_es_no_op(tmp_path):
    """Un segundo sync sin filas nuevas no debe modificar el CSV procesado."""
    fechas_reales = pd.date_range('2026-03-01', '2026-03-03 23:55:00', freq='5min')
    origen = tmp_path / 'fuente'
    dest = tmp_path / 'procesado'
    origen.mkdir()
    dest.mkdir()
    nombre = 'ARCHIVO_NOOP.csv'

    _escribir_csv(origen / nombre, fechas_reales, seed_a=1, seed_b=2)
    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)
    contenido_antes = (dest / nombre).read_bytes()

    # Mismo archivo fuente (sin datos nuevos) -- debe detectarse como no-op.
    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)
    contenido_despues = (dest / nombre).read_bytes()

    assert contenido_antes == contenido_despues


def test_incremental_deduplica_filas_repetidas_en_la_fuente(tmp_path):
    """Si la fuente trae filas repetidas en el rango nuevo, no deben duplicarse
    en el CSV procesado (mismo criterio que el modo completo: keep='first')."""
    fechas_reales = pd.date_range('2026-04-01', '2026-04-02 23:55:00', freq='5min')
    origen = tmp_path / 'fuente'
    dest = tmp_path / 'procesado'
    origen.mkdir()
    dest.mkdir()
    nombre = 'ARCHIVO_DUP.csv'

    primera_mitad = fechas_reales[:200]
    _escribir_csv(origen / nombre, primera_mitad, seed_a=1, seed_b=2)
    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)

    # Segunda sincronizacion: incluye filas ya procesadas (duplicadas) + nuevas.
    df_base = pd.DataFrame({
        'Fecha': fechas_reales.strftime('%Y-%m-%d %H:%M:%S'),
        'KWH_REC': np.round(np.random.default_rng(1).random(len(fechas_reales)) * 100, 3),
        'KWH_ENT': np.round(np.random.default_rng(2).random(len(fechas_reales)) * 10, 3),
    })
    duplicadas = df_base.iloc[195:200]
    df_con_dup = pd.concat([df_base, duplicadas], ignore_index=True)
    df_con_dup.to_csv(origen / nombre, index=False, encoding='utf-8-sig')

    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)

    df_resultado = pd.read_csv(dest / nombre, encoding='utf-8-sig')
    assert df_resultado['Fecha'].is_unique
    assert len(df_resultado) == len(fechas_reales)


def test_primera_verificacion_usa_modo_completo(tmp_path):
    """Sin CSV procesado previo, debe usar el camino completo (no incremental)
    y el resultado debe cubrir todo el rango, igual que antes de este cambio."""
    fechas_reales = pd.date_range('2026-05-01', '2026-05-01 12:00:00', freq='5min')
    origen = tmp_path / 'fuente'
    dest = tmp_path / 'procesado'
    origen.mkdir()
    dest.mkdir()
    nombre = 'ARCHIVO_PRIMERA_VEZ.csv'

    _escribir_csv(origen / nombre, fechas_reales, seed_a=1, seed_b=2)
    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)

    df = pd.read_csv(dest / nombre, encoding='utf-8-sig')
    assert len(df) == len(fechas_reales)
    assert list(df.columns) == ['Fecha', 'KWH_REC', 'KWH_ENT']


def test_primer_dia_no_exige_medianoche_fuera_de_rango(tmp_path):
    """El 00:00 del dia anterior al primer registro real no existe en el
    origen (pertenece a un dia fuera de rango) y no debe contarse como
    hueco -- ni en modo completo ni incremental."""
    # Primer registro real: 2026-06-01 00:05 (no hay 2026-06-01 00:00: ese
    # perfil cerraria el 2026-05-31, que no esta en los datos).
    fechas_reales = pd.date_range('2026-06-01 00:05:00', '2026-06-02 00:00:00', freq='5min')
    origen = tmp_path / 'fuente'
    dest = tmp_path / 'procesado'
    origen.mkdir()
    dest.mkdir()
    nombre = 'ARCHIVO_PRIMER_DIA.csv'

    _escribir_csv(origen / nombre, fechas_reales, seed_a=1, seed_b=2)
    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)

    df = pd.read_csv(dest / nombre, encoding='utf-8-sig')
    # 288 perfiles exactos: ni de mas (no se inserto un 2026-05-31 23:55 o
    # 2026-06-01 00:00 fantasma) ni de menos.
    assert len(df) == 288
    assert df['Fecha'].iloc[0] == '2026-06-01 00:05:00'
    assert df['Fecha'].iloc[-1] == '2026-06-02 00:00:00'


def test_verify_dia_abierto_recoge_actualizacion_de_la_fuente(tmp_path):
    """El caso real que motivo este cambio: el origen (ArchivosFuente)
    puede traer, en corridas sucesivas, un valor actualizado para una
    fecha que ya se habia verificado ese mismo dia -- tipicamente porque
    export_csv.py reexporta la ventana abierta con un valor real que antes
    era cero (ver bess/data/ingest/ion/export_csv.py). La siguiente
    verificacion incremental debe reflejar ese valor, no quedarse pegada
    en lo que ya se habia escrito para esa fecha."""
    fechas_reales = pd.date_range('2026-07-15 00:05:00', '2026-07-15 23:55:00', freq='5min')
    origen = tmp_path / 'fuente'
    dest = tmp_path / 'procesado'
    origen.mkdir()
    dest.mkdir()
    nombre = 'ARCHIVO_DIA_ABIERTO.csv'

    df = pd.DataFrame({
        'Fecha': fechas_reales.strftime('%Y-%m-%d %H:%M:%S'),
        'KWH_REC': 0.0,
        'KWH_ENT': 0.0,
    })
    df.to_csv(origen / nombre, index=False, encoding='utf-8-sig')
    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)
    df1 = pd.read_csv(dest / nombre, encoding='utf-8-sig')
    assert (df1['KWH_REC'] == 0).all()

    # El origen se actualiza con un valor real para una hora ya "verificada".
    df.loc[df['Fecha'] == '2026-07-15 12:15:00', 'KWH_REC'] = 129.6
    df.to_csv(origen / nombre, index=False, encoding='utf-8-sig')

    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)
    df2 = pd.read_csv(dest / nombre, encoding='utf-8-sig')
    fila = df2[df2['Fecha'] == '2026-07-15 12:15:00']
    assert len(fila) == 1, "la fila se duplico o se perdio al reverificar la ventana"
    assert fila.iloc[0]['KWH_REC'] == 129.6
    assert len(df2) == len(df1), "la cantidad de filas no debia cambiar, solo el valor"


def test_verify_dias_cerrados_no_se_tocan_al_recalcular_ventana(tmp_path):
    """Un dia bien anterior a la ventana de reverificacion no debe verse
    afectado por cambios en el origen fuera de esa ventana (p.ej. una
    correccion o purga de un dia viejo en ArchivosFuente) -- solo los
    ultimos `_MARGEN_REEXPORTAR_DIAS` dias se vuelven a leer y sobrescribir
    en cada corrida incremental."""
    fechas_reales = pd.date_range('2026-08-01 00:05:00', '2026-08-10 00:00:00', freq='5min')
    origen = tmp_path / 'fuente'
    dest = tmp_path / 'procesado'
    origen.mkdir()
    dest.mkdir()
    nombre = 'ARCHIVO_DIAS_CERRADOS.csv'

    _escribir_csv(origen / nombre, fechas_reales, seed_a=1, seed_b=2)
    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)
    df1 = pd.read_csv(dest / nombre, encoding='utf-8-sig')

    # "Corromper" el origen para un dia bien cerrado, fuera de la ventana
    # de reverificacion -- no debe propagarse al archivo procesado.
    df_origen = pd.read_csv(origen / nombre, encoding='utf-8-sig')
    mask = df_origen['Fecha'].str.startswith('2026-08-02')
    df_origen.loc[mask, 'KWH_REC'] = 999.0
    df_origen.to_csv(origen / nombre, index=False, encoding='utf-8-sig')

    assert procesar_archivo_verificacion(str(origen), str(dest), nombre)
    df2 = pd.read_csv(dest / nombre, encoding='utf-8-sig')
    dia2_antes = df1[df1['Fecha'].str.startswith('2026-08-02')].reset_index(drop=True)
    dia2_despues = df2[df2['Fecha'].str.startswith('2026-08-02')].reset_index(drop=True)
    assert dia2_despues.equals(dia2_antes)
    assert not (dia2_despues['KWH_REC'] == 999.0).any()
