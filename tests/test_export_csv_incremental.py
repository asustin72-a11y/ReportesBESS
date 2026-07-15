"""Pruebas de exportación incremental (Fase 2): export_csv.py.

exportar() ahora, si no se piden `desde`/`hasta` explícitos y ya existe un
CSV exportado para el medidor, solo consulta y anexa las filas de
perfil_carga posteriores al cursor (última Fecha ya exportada), en vez de
reexportar el histórico completo en cada sincronización. Estas pruebas
comprueban que varias exportaciones incrementales sucesivas producen
exactamente el mismo CSV que una sola exportación completa sobre el mismo
estado de la base -- tanto para medidores ION (sin relleno de medianoche)
como para medidores API/Granja (con relleno de medianoche vía gaps.py, que
ahora también debe funcionar cuando el corte de la exportación cae a media
tabla en vez de al inicio del histórico).

Usa medidores reales del catálogo (MEDIDOR_ION, MEDIDOR_GENERACION_IUSA2)
porque exportar() llama a db.init_db(), que registra el catálogo real de
medidores en la base de prueba -- no vale la pena simularlo aparte.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bess.data.ingest.ion import db
from bess.data.ingest.ion.export_csv import exportar
from bess.data.ingest.medidor_ids import MEDIDOR_GENERACION_IUSA2, MEDIDOR_ION


def _insertar_perfil(ruta_bd, medidor_id, fechas, seed=1):
    if len(fechas) == 0:
        return
    rng = np.random.default_rng(seed)
    filas = [
        (
            medidor_id,
            fecha.strftime('%Y-%m-%d %H:%M:%S'),
            round(float(rng.random() * 100), 3),
            round(float(rng.random() * 10), 3),
        )
        for fecha in fechas
    ]
    with db.conectar_bd(ruta_bd) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO perfil_carga
                (medidor_id, fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4, fuente)
            VALUES (?, ?, ?, ?, 0, 0, 0, 0, 'test')
            """,
            filas,
        )
        conn.commit()


def test_export_incremental_equivale_a_completo_ion(tmp_path):
    """Medidor ION (sin relleno de medianoche): 2 exportaciones incrementales
    sucesivas deben terminar igual que una exportación completa del mismo
    estado final de la base."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)

    fechas = pd.date_range('2026-01-01 00:05:00', '2026-01-03 00:00:00', freq='5min')
    mitad = len(fechas) // 2

    _insertar_perfil(ruta_bd, MEDIDOR_ION, fechas[:mitad])
    salida_inc = tmp_path / 'inc' / 'ION.csv'
    assert exportar(ruta_bd, MEDIDOR_ION, salida_inc) == 0

    _insertar_perfil(ruta_bd, MEDIDOR_ION, fechas[mitad:])
    assert exportar(ruta_bd, MEDIDOR_ION, salida_inc) == 0

    salida_full = tmp_path / 'full' / 'ION.csv'
    assert exportar(ruta_bd, MEDIDOR_ION, salida_full) == 0

    df_inc = pd.read_csv(salida_inc, encoding='utf-8-sig')
    df_full = pd.read_csv(salida_full, encoding='utf-8-sig')
    assert df_inc.equals(df_full)
    assert len(df_inc) == len(fechas)


def test_export_incremental_equivale_a_completo_api_con_medianoche(tmp_path):
    """Medidor API/Granja (con relleno de medianoche): el corte incremental
    cae a media tabla (no al inicio del histórico), y aun así el resultado
    debe coincidir con una exportación completa -- ejercita el contexto
    previo (contexto_previo_bd) que la exportación incremental necesita
    para detectar el salto 23:55->00:05 a través del corte."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)

    # Fechas reales sin 00:00 (como si la API saltara ese slot cada día);
    # rellenar_slots_medianoche_api() debe reinsertarlo con ceros.
    fechas_completas = pd.date_range('2026-02-01 00:05:00', '2026-02-04 00:00:00', freq='5min')
    fechas_reales = fechas_completas[
        ~((fechas_completas.hour == 0) & (fechas_completas.minute == 0))
    ]
    mitad = len(fechas_reales) // 2

    _insertar_perfil(ruta_bd, MEDIDOR_GENERACION_IUSA2, fechas_reales[:mitad])
    salida_inc = tmp_path / 'inc' / 'GEN.csv'
    assert exportar(ruta_bd, MEDIDOR_GENERACION_IUSA2, salida_inc) == 0

    _insertar_perfil(ruta_bd, MEDIDOR_GENERACION_IUSA2, fechas_reales[mitad:])
    assert exportar(ruta_bd, MEDIDOR_GENERACION_IUSA2, salida_inc) == 0

    salida_full = tmp_path / 'full' / 'GEN.csv'
    assert exportar(ruta_bd, MEDIDOR_GENERACION_IUSA2, salida_full) == 0

    df_inc = pd.read_csv(salida_inc, encoding='utf-8-sig')
    df_full = pd.read_csv(salida_full, encoding='utf-8-sig')
    assert df_inc.equals(df_full)
    assert df_inc['Fecha'].is_unique


def test_export_sin_datos_nuevos_es_no_op(tmp_path):
    """Una segunda exportación sin filas nuevas en la BD no debe tocar el CSV."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)

    fechas = pd.date_range('2026-03-01', '2026-03-01 12:00:00', freq='5min')
    _insertar_perfil(ruta_bd, MEDIDOR_ION, fechas)

    salida = tmp_path / 'ION.csv'
    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 0
    contenido_antes = salida.read_bytes()

    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 0
    contenido_despues = salida.read_bytes()

    assert contenido_antes == contenido_despues


def test_export_desde_hasta_explicito_ignora_cursor(tmp_path):
    """Un desde/hasta explícito debe seguir sobrescribiendo el archivo
    completo con ese rango, igual que antes -- no debe activarse el modo
    incremental aunque ya exista un CSV previo."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)

    fechas = pd.date_range('2026-04-01', '2026-04-03 23:55:00', freq='5min')
    _insertar_perfil(ruta_bd, MEDIDOR_ION, fechas)

    salida = tmp_path / 'ION.csv'
    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 0
    df_completo = pd.read_csv(salida, encoding='utf-8-sig')
    assert len(df_completo) == len(fechas)

    # Pedir explícitamente solo el 2026-04-02 debe sobrescribir con un
    # archivo mucho más chico, no anexar.
    assert exportar(ruta_bd, MEDIDOR_ION, salida, desde='2026-04-02', hasta='2026-04-02') == 0
    df_rango = pd.read_csv(salida, encoding='utf-8-sig')
    assert len(df_rango) < len(df_completo)
    assert df_rango['Fecha'].str.startswith('2026-04-02').all()


def test_primera_exportacion_usa_modo_completo(tmp_path):
    """Sin CSV previo, exportar() debe escribir completo con encabezado,
    igual que antes de este cambio."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)

    fechas = pd.date_range('2026-05-01', '2026-05-01 06:00:00', freq='5min')
    _insertar_perfil(ruta_bd, MEDIDOR_ION, fechas)

    salida = tmp_path / 'ION.csv'
    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 0

    df = pd.read_csv(salida, encoding='utf-8-sig')
    assert len(df) == len(fechas)
    assert list(df.columns) == ['Fecha', 'KWH_REC', 'KWH_ENT', 'KVARH_Q1', 'KVARH_Q2', 'KVARH_Q3', 'KVARH_Q4']


def test_export_sin_registros_en_bd_devuelve_error(tmp_path):
    """Un medidor sin ninguna fila en perfil_carga (nunca sincronizado) debe
    seguir devolviendo 1 (error/omitido), no confundirse con el no-op
    incremental (que devuelve 0)."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)

    salida = tmp_path / 'ION.csv'
    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 1
    assert not salida.exists()
