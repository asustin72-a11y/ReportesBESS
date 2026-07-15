"""Pruebas de exportación incremental (Fase 2): export_csv.py.

exportar() ahora, si no se piden `desde`/`hasta` explícitos y ya existe un
CSV exportado para el medidor, consulta desde el inicio de una ventana de
`_MARGEN_REEXPORTAR_DIAS` días antes del cursor (última Fecha ya exportada)
en adelante -- no solo filas estrictamente nuevas -- y esa ventana
reemplaza lo que hubiera en el archivo para esas fechas, en vez de
reexportar el histórico completo en cada sincronización. Esto es necesario
porque la API ISOL rellena el día en curso con ceros desde temprano y lo va
completando con valores reales conforme pasan las horas (mismo margen que
usa bess/data/ingest/iusasol/sync_db.py); un cursor estrictamente "fecha >
X" dejaría esas actualizaciones encerradas en SQLite para siempre. Estas
pruebas comprueban que varias exportaciones incrementales sucesivas
producen exactamente el mismo CSV que una sola exportación completa sobre
el mismo estado de la base -- tanto para medidores ION (sin relleno de
medianoche) como para medidores API/Granja (con relleno de medianoche vía
gaps.py, que ahora también debe funcionar cuando el corte de la
exportación cae a media tabla en vez de al inicio del histórico) -- y que
una actualización de un valor dentro de la ventana sí se propaga, mientras
que un cambio fuera de la ventana (un día ya cerrado) no afecta al
archivo.

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


def _upsert_valor(ruta_bd, medidor_id, fecha_txt, kwh_rec):
    with db.conectar_bd(ruta_bd) as conn:
        conn.execute(
            """
            INSERT INTO perfil_carga
                (medidor_id, fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4, fuente)
            VALUES (?, ?, ?, 0, 0, 0, 0, 0, 'test')
            ON CONFLICT(medidor_id, fecha) DO UPDATE SET kwh_rec = excluded.kwh_rec
            """,
            (medidor_id, fecha_txt, kwh_rec),
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


def test_export_dia_abierto_recoge_actualizacion_posterior(tmp_path):
    """El caso real que motivó este cambio: la API ISOL rellena el día
    completo con ceros desde temprano (horas que aún no pasan); export() ya
    escribió ese día con esos ceros. Más tarde SQLite recibe un valor real
    para una hora que ya ocurrió (p.ej. vía el solapamiento de 1 día del
    sync -- bess/data/ingest/iusasol/sync_db.py). La siguiente exportación
    incremental debe reflejar ese valor real, no quedarse pegada en el cero
    que ya se había exportado ese mismo día."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)

    fechas_hoy = pd.date_range('2026-07-15 00:05:00', '2026-07-15 23:55:00', freq='5min')
    with db.conectar_bd(ruta_bd) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO perfil_carga
                (medidor_id, fecha, kwh_rec, kwh_ent, kvarh_q1, kvarh_q2, kvarh_q3, kvarh_q4, fuente)
            VALUES (?, ?, 0, 0, 0, 0, 0, 0, 'iusasol')
            """,
            [(MEDIDOR_ION, f.strftime('%Y-%m-%d %H:%M:%S')) for f in fechas_hoy],
        )
        conn.commit()

    salida = tmp_path / 'ION.csv'
    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 0
    df1 = pd.read_csv(salida, encoding='utf-8-sig')
    assert (df1['KWH_REC'] == 0).all()

    _upsert_valor(ruta_bd, MEDIDOR_ION, '2026-07-15 12:15:00', 129.6)

    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 0
    df2 = pd.read_csv(salida, encoding='utf-8-sig')
    fila = df2[df2['Fecha'] == '2026-07-15 12:15:00']
    assert len(fila) == 1, "la fila se duplicó o se perdió al reexportar la ventana"
    assert fila.iloc[0]['KWH_REC'] == 129.6
    assert len(df2) == len(df1), "la cantidad de filas no debía cambiar, solo el valor"


def test_export_dias_cerrados_no_se_tocan_al_recalcular_ventana(tmp_path):
    """Un día bien anterior a la ventana de reexportación no debe verse
    afectado por cambios en SQLite fuera de esa ventana (p.ej. una purga de
    un día viejo) -- solo los últimos `_MARGEN_REEXPORTAR_DIAS` días se
    vuelven a pedir y sobrescribir en cada corrida incremental."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)

    fechas = pd.date_range('2026-06-01 00:05:00', '2026-06-10 00:00:00', freq='5min')
    _insertar_perfil(ruta_bd, MEDIDOR_ION, fechas)
    salida = tmp_path / 'ION.csv'
    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 0
    df1 = pd.read_csv(salida, encoding='utf-8-sig')

    with db.conectar_bd(ruta_bd) as conn:
        conn.execute(
            "DELETE FROM perfil_carga WHERE medidor_id = ? AND fecha LIKE '2026-06-02%'",
            (MEDIDOR_ION,),
        )
        conn.commit()
    _upsert_valor(ruta_bd, MEDIDOR_ION, '2026-06-10 00:05:00', 55.5)

    assert exportar(ruta_bd, MEDIDOR_ION, salida) == 0
    df2 = pd.read_csv(salida, encoding='utf-8-sig')
    dia2_antes = df1[df1['Fecha'].str.startswith('2026-06-02')]
    dia2_despues = df2[df2['Fecha'].str.startswith('2026-06-02')]
    assert len(dia2_despues) == len(dia2_antes), (
        "un día cerrado (fuera de la ventana) se vio afectado por un cambio "
        "en SQLite que no le corresponde"
    )
