"""Pruebas de Filtrar incremental (Fase 4 del plan CSV->SQLite).

`_escribir_filtrado()` es la pieza nueva: dado el conjunto ya calculado de
fechas aceptadas (interseccion BESS/medidor, sin cambios respecto a antes)
decide si puede *anexar* solo el tramo nuevo (cursor sobre la ultima Fecha
ya escrita en el destino) o si tiene que recalcular y reescribir completo
(primera vez, o cambio de formato de columnas). Se prueba aislada, igual
que `consolidar_bess_subestacion`/`_sumar_marcos` en Fase 3, mas una prueba
de integracion contra los datos reales del repo para confirmar que una
segunda corrida sin datos nuevos es no-op.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import bess.data.pipeline.filter as filter_mod
from bess.data.pipeline.filter import _escribir_filtrado, _filtrar_datos_impl


def _df(fechas, seed_a=1, seed_b=2, kvarh=False):
    datos = {
        "Fecha": pd.to_datetime(fechas),
        "KWH_REC": np.round(np.random.default_rng(seed_a).random(len(fechas)) * 100, 3),
        "KWH_ENT": np.round(np.random.default_rng(seed_b).random(len(fechas)) * 10, 3),
    }
    if kvarh:
        datos["KVARH_Q1"] = np.round(np.random.default_rng(seed_a + 1).random(len(fechas)) * 5, 3)
    return pd.DataFrame(datos)


def test_escribir_filtrado_primera_vez_modo_completo(tmp_path):
    fechas = pd.date_range("2026-01-01 00:05:00", "2026-01-01 06:00:00", freq="5min")
    df = _df(fechas)
    destino = tmp_path / "salida.csv"

    filas = _escribir_filtrado(df, set(df["Fecha"]), str(destino))

    assert filas == len(fechas)
    resultado = pd.read_csv(destino, encoding="utf-8-sig")
    assert len(resultado) == len(fechas)


def test_escribir_filtrado_incremental_equivale_a_completo(tmp_path):
    fechas = pd.date_range("2026-01-01 00:05:00", "2026-01-03 00:00:00", freq="5min")
    df = _df(fechas)
    mitad = len(fechas) // 2

    destino_inc = tmp_path / "incremental.csv"
    # 1a corrida: solo la primera mitad de fechas ya está "aceptada".
    _escribir_filtrado(df, set(df["Fecha"][:mitad]), str(destino_inc))
    # 2a corrida: el conjunto aceptado crece a todas las fechas (simula que
    # llegaron datos nuevos y ahora hay más fechas comunes).
    filas_nuevas = _escribir_filtrado(df, set(df["Fecha"]), str(destino_inc))

    assert filas_nuevas == len(fechas) - mitad

    destino_full = tmp_path / "completo.csv"
    _escribir_filtrado(df, set(df["Fecha"]), str(destino_full))

    df_inc = pd.read_csv(destino_inc, encoding="utf-8-sig")
    df_full = pd.read_csv(destino_full, encoding="utf-8-sig")
    assert df_inc.equals(df_full)
    assert len(df_inc) == len(fechas)


def test_escribir_filtrado_sin_novedades_es_no_op(tmp_path):
    fechas = pd.date_range("2026-02-01", "2026-02-01 12:00:00", freq="5min")
    df = _df(fechas)
    destino = tmp_path / "salida.csv"

    _escribir_filtrado(df, set(df["Fecha"]), str(destino))
    contenido_antes = destino.read_bytes()

    filas = _escribir_filtrado(df, set(df["Fecha"]), str(destino))

    assert filas == 0
    assert destino.read_bytes() == contenido_antes


def test_escribir_filtrado_columnas_distintas_recalcula_completo(tmp_path):
    fechas = pd.date_range("2026-03-01", "2026-03-01 01:00:00", freq="5min")
    df_sin_kvarh = _df(fechas, kvarh=False)
    destino = tmp_path / "salida.csv"
    _escribir_filtrado(df_sin_kvarh, set(df_sin_kvarh["Fecha"]), str(destino))

    fechas2 = pd.date_range("2026-03-01", "2026-03-01 02:00:00", freq="5min")
    df_con_kvarh = _df(fechas2, kvarh=True)
    filas = _escribir_filtrado(df_con_kvarh, set(df_con_kvarh["Fecha"]), str(destino))

    # Cambió el formato de columnas (ahora trae KVARH_Q1): debe recalcular
    # completo, no intentar anexar con columnas distintas.
    assert filas == len(fechas2)
    resultado = pd.read_csv(destino, encoding="utf-8-sig")
    assert "KVARH_Q1" in resultado.columns
    assert len(resultado) == len(fechas2)


def test_escribir_filtrado_transformar_solo_sobre_lo_nuevo(tmp_path):
    fechas = pd.date_range("2026-04-01", "2026-04-01 01:00:00", freq="5min")
    df = _df(fechas)
    destino = tmp_path / "salida.csv"

    llamadas = []

    def transformar(sub_df):
        llamadas.append(len(sub_df))
        return sub_df

    _escribir_filtrado(df, set(df["Fecha"]), str(destino), transformar=transformar)
    assert llamadas == [len(fechas)]

    fechas2 = pd.date_range("2026-04-01", "2026-04-01 02:00:00", freq="5min")
    df2 = _df(fechas2)
    _escribir_filtrado(df2, set(df2["Fecha"]), str(destino), transformar=transformar)

    # La segunda llamada de transformar solo debe recibir el tramo nuevo
    # (12 filas de 01:05 a 02:00), no las 13 ya escritas antes.
    assert llamadas[-1] == len(fechas2) - len(fechas)


def test_escribir_filtrado_incremental_equivale_a_completo_datos_reales(tmp_path):
    """Misma prueba que test_escribir_filtrado_incremental_equivale_a_completo
    pero con datos reales de IUSA_1 (ION ∩ BESS), no sintéticos."""
    from bess.data.ingest.readers import leer_archivo_perfil

    df_ion = leer_archivo_perfil(
        "data/ArchivosProcesados/IUSA_1/ION_Testigo_IUSA1.csv", "ION_Testigo_IUSA1.csv"
    )
    df_bess = leer_archivo_perfil(
        "data/ArchivosProcesados/IUSA_1/BESS_IUSA_1.csv", "BESS_IUSA_1.csv"
    )
    fechas_comunes = set(df_ion["Fecha"]).intersection(set(df_bess["Fecha"]))
    assert len(fechas_comunes) > 100, "se esperaban fechas comunes reales de sobra"

    fechas_ordenadas = sorted(fechas_comunes)
    mitad = fechas_ordenadas[len(fechas_ordenadas) // 2]

    destino_inc = tmp_path / "incremental.csv"
    _escribir_filtrado(df_ion, {f for f in fechas_comunes if f <= mitad}, str(destino_inc))
    filas_nuevas = _escribir_filtrado(df_ion, fechas_comunes, str(destino_inc))
    assert filas_nuevas == len([f for f in fechas_comunes if f > mitad])

    destino_full = tmp_path / "completo.csv"
    _escribir_filtrado(df_ion, fechas_comunes, str(destino_full))

    df_inc = pd.read_csv(destino_inc, encoding="utf-8-sig")
    df_full = pd.read_csv(destino_full, encoding="utf-8-sig")
    assert df_inc.equals(df_full)
    assert len(df_inc) == len(fechas_comunes)


def test_filtrar_datos_segunda_corrida_sin_datos_nuevos_es_no_op(monkeypatch):
    """Corre _filtrar_datos_impl() dos veces seguidas contra los datos
    reales del repo (mismos que usa tests/test_filter_conserva_fuente.py).
    Sin datos fuente nuevos entre medio, la segunda corrida no debe cambiar
    ni un byte de los *_Filtrado.csv ya escritos por la primera."""
    llamadas = []
    monkeypatch.setattr(
        filter_mod, "limpiar_archivos_fuente", lambda: llamadas.append(1)
    )

    exito, _ = _filtrar_datos_impl()
    assert exito

    import bess.config.subestaciones as subs_mod

    rutas_a_verificar = []
    for sub in subs_mod.SUBESTACIONES:
        for med in sub.medidores_consumo:
            rutas_a_verificar.append(med.ruta_consumo(filtrado=True))
        rutas_a_verificar.append(sub.ruta_bess(filtrado=True))

    contenidos_antes = {
        str(r): r.read_bytes() for r in rutas_a_verificar if r.exists()
    }
    assert contenidos_antes, "se esperaba al menos un archivo *_Filtrado.csv real"

    exito2, _ = _filtrar_datos_impl()
    assert exito2

    for ruta, contenido in contenidos_antes.items():
        assert contenido == open(ruta, "rb").read(), f"{ruta} cambió sin datos nuevos"

    assert llamadas == []
