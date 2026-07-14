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

_ARCHIVOS_SALTAR_MEDIANOCHE_ION se calcula al importar bess.data.pipeline.verify
consultando el catalogo real (SQLite). Aqui se sustituye obtener_catalogo()
por un catalogo falso ANTES de importar verify, para que la prueba no
dependa de la base de datos real ni de su disponibilidad.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import bess.config.catalog as catalog_mod


class _FakeCatalogo:
    medidores = [SimpleNamespace(nombre="ION_TEST", descarga="ION")]


catalog_mod.obtener_catalogo = lambda: _FakeCatalogo()

from bess.config import rutas as rutas_mod  # noqa: E402
from bess.data.pipeline.verify import (  # noqa: E402
    _ARCHIVOS_SALTAR_MEDIANOCHE_ION,
    procesar_archivo_verificacion,
)

NOMBRE_ION = rutas_mod.nombre_archivo_medidor("ION_TEST")


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


def test_catalogo_falso_aplicado():
    # Confirma que el import de verify.py uso el catalogo falso (frozenset
    # con un solo medidor ION) y no el catalogo real -- si esto falla, el
    # resto de las pruebas de este archivo no son confiables.
    assert _ARCHIVOS_SALTAR_MEDIANOCHE_ION == frozenset({NOMBRE_ION})


def test_incremental_equivale_a_completo_con_huecos(tmp_path):
    """Archivo NO-ION con huecos aleatorios, verificado en 3 sincronizaciones."""
    rng = np.random.default_rng(42)
    fechas_completas = pd.date_range('2026-01-01 00:00:00', '2026-01-10 23:55:00', freq='5min')
    fechas_reales = fechas_completas[rng.random(len(fechas_completas)) > 0.05]
    cortes = [
        pd.Timestamp('2026-01-04 23:55:00'),
        pd.Timestamp('2026-01-07 12:00:00'),
        fechas_reales.max(),
    ]

    df_inc, df_full = _correr_incremental_vs_completo(
        tmp_path, 'ARCHIVO_NOION.csv', fechas_reales, cortes
    )

    assert df_inc.equals(df_full)
    # El relleno de huecos debio actuar: mas filas que las "reales" originales.
    assert len(df_inc) > len(fechas_reales)


def test_incremental_equivale_a_completo_con_salto_medianoche_ion(tmp_path):
    """Archivo ION (con salto de 00:00 real) verificado en 3 sincronizaciones."""
    fechas_reales = pd.date_range('2026-02-01 00:05:00', '2026-02-08 23:55:00', freq='5min')
    cortes = [
        pd.Timestamp('2026-02-03 23:55:00'),
        pd.Timestamp('2026-02-06 10:00:00'),
        fechas_reales.max(),
    ]

    df_inc, df_full = _correr_incremental_vs_completo(
        tmp_path, NOMBRE_ION, fechas_reales, cortes
    )

    assert df_inc.equals(df_full)
    # La regla ION solo permite saltar una medianoche si tampoco esta en los
    # datos reales; aqui la unica ausente de verdad es la del primer dia
    # (fechas_reales arranca en 00:05). Las demas medianoches del rango si
    # vienen en fechas_reales (el paso fijo de 5 min las genera de forma
    # natural) y deben seguir presentes -- no se debio insertar de mas ni
    # de menos.
    assert '2026-02-01 00:00:00' not in set(df_inc['Fecha'])
    assert '2026-02-02 00:00:00' in set(df_inc['Fecha'])


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
    mtime_antes = (dest / nombre).stat().st_mtime_ns

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