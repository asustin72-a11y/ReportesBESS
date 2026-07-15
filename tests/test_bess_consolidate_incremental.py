"""Pruebas de consolidado BESS incremental (Fase 3 del plan CSV->SQLite).

consolidar_bess_subestacion() suma los medidores BESS tipo 3 del catálogo
en BESS_{Subestacion}.csv. Antes reescribía ese archivo completo en cada
corrida de Verificar; ahora, si ya existe un consolidado con cursor
legible (última Fecha) y columnas compatibles, solo suma y anexa las
filas nuevas de cada medidor BESS.

_sumar_marcos() (la suma por outer-join de varios medidores BESS) se
prueba aparte como función pura, porque en el catálogo real de este
despliegue cada subestación tiene un solo medidor BESS -- la suma de
varios nunca se ejercita con datos reales. El resto de las pruebas usa
una subestación real del catálogo (IUSA_1, un solo medidor BESS:
BESS_NORTE) con las rutas de ArchivosProcesados redirigidas a un
directorio temporal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import bess.config.rutas as rutas_mod
from bess.config.catalog import TIPO_BESS, obtener_catalogo
from bess.config.subestaciones import SUBESTACIONES
from bess.data.pipeline.bess_consolidate import _sumar_marcos, consolidar_bess_subestacion

SUB_IUSA_1 = next(s for s in SUBESTACIONES if s.id == "IUSA_1")


def _nombre_medidor_bess(sub) -> str:
    return next(
        m.nombre for m in obtener_catalogo().medidores
        if m.subestacion_nombre == sub.id and m.tipo_medidor == TIPO_BESS
    )


def _escribir_procesado(ruta, fechas, seed_a=1, seed_b=2):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        'Fecha': fechas.strftime('%Y-%m-%d %H:%M:%S'),
        'KWH_REC': np.round(np.random.default_rng(seed_a).random(len(fechas)) * 100, 3),
        'KWH_ENT': np.round(np.random.default_rng(seed_b).random(len(fechas)) * 10, 3),
    })
    df.to_csv(ruta, index=False, encoding='utf-8-sig')


def test_sumar_marcos_suma_columnas_coincidentes():
    """Función pura: dos medidores BESS con fechas parcialmente distintas
    deben sumarse por outer-join, tratando lo ausente como cero."""
    df_a = pd.DataFrame({
        'Fecha': pd.to_datetime(['2026-01-01 00:05:00', '2026-01-01 00:10:00']),
        'KWH_REC': [10.0, 20.0],
        'KWH_ENT': [1.0, 2.0],
    })
    df_b = pd.DataFrame({
        'Fecha': pd.to_datetime(['2026-01-01 00:05:00', '2026-01-01 00:15:00']),
        'KWH_REC': [5.0, 7.0],
        'KWH_ENT': [0.5, 0.7],
    })

    resultado = _sumar_marcos([df_a, df_b])

    fila_0005 = resultado[resultado['Fecha'] == pd.Timestamp('2026-01-01 00:05:00')].iloc[0]
    fila_0010 = resultado[resultado['Fecha'] == pd.Timestamp('2026-01-01 00:10:00')].iloc[0]
    fila_0015 = resultado[resultado['Fecha'] == pd.Timestamp('2026-01-01 00:15:00')].iloc[0]

    assert fila_0005['KWH_REC'] == 15.0  # 10 + 5, ambos medidores tienen este slot
    assert fila_0010['KWH_REC'] == 20.0  # solo df_a
    assert fila_0015['KWH_REC'] == 7.0   # solo df_b
    assert len(resultado) == 3
    assert list(resultado['Fecha']) == sorted(resultado['Fecha'])


def test_consolidar_incremental_equivale_a_completo(tmp_path, monkeypatch):
    nombre_bess = _nombre_medidor_bess(SUB_IUSA_1)
    fechas = pd.date_range('2026-01-01 00:05:00', '2026-01-03 00:00:00', freq='5min')
    mitad = len(fechas) // 2

    dir_inc = tmp_path / 'inc'
    monkeypatch.setattr(rutas_mod, 'DIRECTORIO_PROCESADOS', dir_inc)
    ruta_medidor = dir_inc / SUB_IUSA_1.id / f'{nombre_bess}.csv'

    # 1a corrida de Verificar: solo la primera mitad procesada.
    _escribir_procesado(ruta_medidor, fechas[:mitad])
    assert consolidar_bess_subestacion(SUB_IUSA_1) is True

    # 2a corrida: se agrega el resto.
    _escribir_procesado(ruta_medidor, fechas)
    assert consolidar_bess_subestacion(SUB_IUSA_1) is True

    destino_inc = dir_inc / SUB_IUSA_1.id / f'BESS_{SUB_IUSA_1.id}.csv'
    df_inc = pd.read_csv(destino_inc, encoding='utf-8-sig')

    # Comparar contra una corrida completa independiente (destino nuevo).
    dir_full = tmp_path / 'full'
    monkeypatch.setattr(rutas_mod, 'DIRECTORIO_PROCESADOS', dir_full)
    ruta_medidor_full = dir_full / SUB_IUSA_1.id / f'{nombre_bess}.csv'
    _escribir_procesado(ruta_medidor_full, fechas)
    assert consolidar_bess_subestacion(SUB_IUSA_1) is True
    destino_full = dir_full / SUB_IUSA_1.id / f'BESS_{SUB_IUSA_1.id}.csv'
    df_full = pd.read_csv(destino_full, encoding='utf-8-sig')

    assert df_inc.equals(df_full)
    assert len(df_inc) == len(fechas)


def test_consolidar_sin_datos_nuevos_es_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(rutas_mod, 'DIRECTORIO_PROCESADOS', tmp_path)
    nombre_bess = _nombre_medidor_bess(SUB_IUSA_1)

    ruta_medidor = tmp_path / SUB_IUSA_1.id / f'{nombre_bess}.csv'
    fechas = pd.date_range('2026-02-01', '2026-02-01 12:00:00', freq='5min')
    _escribir_procesado(ruta_medidor, fechas)

    assert consolidar_bess_subestacion(SUB_IUSA_1) is True
    destino = tmp_path / SUB_IUSA_1.id / f'BESS_{SUB_IUSA_1.id}.csv'
    contenido_antes = destino.read_bytes()

    # Sin cambios en el medidor individual: segunda corrida debe ser no-op.
    assert consolidar_bess_subestacion(SUB_IUSA_1) is True
    contenido_despues = destino.read_bytes()

    assert contenido_antes == contenido_despues


def test_consolidar_primera_vez_modo_completo(tmp_path, monkeypatch):
    monkeypatch.setattr(rutas_mod, 'DIRECTORIO_PROCESADOS', tmp_path)
    nombre_bess = _nombre_medidor_bess(SUB_IUSA_1)

    ruta_medidor = tmp_path / SUB_IUSA_1.id / f'{nombre_bess}.csv'
    fechas = pd.date_range('2026-03-01', '2026-03-01 06:00:00', freq='5min')
    _escribir_procesado(ruta_medidor, fechas)

    assert consolidar_bess_subestacion(SUB_IUSA_1) is True

    destino = tmp_path / SUB_IUSA_1.id / f'BESS_{SUB_IUSA_1.id}.csv'
    df = pd.read_csv(destino, encoding='utf-8-sig')
    assert len(df) == len(fechas)
