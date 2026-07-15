"""Pruebas de Filtrar incremental (Fase 4 del plan CSV->SQLite).

`_escribir_filtrado()` es la pieza nueva: dado el conjunto ya calculado de
fechas aceptadas (interseccion BESS/medidor, sin cambios respecto a antes)
decide si puede *recalcular una ventana* de los ultimos
`MARGEN_REEXPORTAR_DIAS` dias (cursor sobre la ultima Fecha ya escrita en
el destino, no solo lo estrictamente nuevo) o si tiene que recalcular y
reescribir completo (primera vez, o cambio de formato de columnas). La
ventana se recalcula -- no solo se anexa lo nuevo -- para recoger
actualizaciones que Verificar trae para fechas ya escritas (ver
bess/data/pipeline/clean.py y bess/data/pipeline/verify.py). Se prueba
aislada, igual que `consolidar_bess_subestacion`/`_sumar_marcos` en Fase 3,
mas una prueba de integracion contra los datos reales del repo para
confirmar que una segunda corrida sin datos nuevos es no-op.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import bess.data.pipeline.filter as filter_mod
from bess.data.pipeline.clean import MARGEN_REEXPORTAR_DIAS
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

    # La 2a corrida recalcula una ventana de MARGEN_REEXPORTAR_DIAS días
    # antes del cursor de la 1a corrida (no solo lo estrictamente nuevo).
    cursor_1a_corrida = df["Fecha"][:mitad].max()
    inicio_ventana_esperado = cursor_1a_corrida.normalize() - pd.Timedelta(days=MARGEN_REEXPORTAR_DIAS)
    esperado = len(df[df["Fecha"] >= inicio_ventana_esperado])
    assert filas_nuevas == esperado

    destino_full = tmp_path / "completo.csv"
    _escribir_filtrado(df, set(df["Fecha"]), str(destino_full))

    df_inc = pd.read_csv(destino_inc, encoding="utf-8-sig")
    df_full = pd.read_csv(destino_full, encoding="utf-8-sig")
    assert df_inc.equals(df_full)
    assert len(df_inc) == len(fechas)


def test_escribir_filtrado_sin_novedades_no_cambia_el_archivo(tmp_path):
    """Una segunda corrida con el mismo conjunto de fechas aceptadas
    recalcula la ventana (ya no es un no-op en el sentido de "no escribir
    nada"), pero el resultado debe ser byte-identico: mismos datos, misma
    escritura determinista."""
    fechas = pd.date_range("2026-02-01", "2026-02-01 12:00:00", freq="5min")
    df = _df(fechas)
    destino = tmp_path / "salida.csv"

    _escribir_filtrado(df, set(df["Fecha"]), str(destino))
    contenido_antes = destino.read_bytes()

    filas = _escribir_filtrado(df, set(df["Fecha"]), str(destino))

    assert filas > 0
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
    # completo, no intentar recalcular la ventana con columnas distintas.
    assert filas == len(fechas2)
    resultado = pd.read_csv(destino, encoding="utf-8-sig")
    assert "KVARH_Q1" in resultado.columns
    assert len(resultado) == len(fechas2)


def test_escribir_filtrado_transformar_sobre_la_ventana_recalculada(tmp_path):
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

    # La segunda llamada de transformar recibe la ventana recalculada
    # (MARGEN_REEXPORTAR_DIAS días antes del cursor de la 1a corrida), no
    # solo el tramo estrictamente nuevo.
    inicio_ventana_esperado = fechas.max().normalize() - pd.Timedelta(days=MARGEN_REEXPORTAR_DIAS)
    esperado = len(df2[df2["Fecha"] >= inicio_ventana_esperado])
    assert llamadas[-1] == esperado


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

    inicio_ventana_esperado = mitad.normalize() - pd.Timedelta(days=MARGEN_REEXPORTAR_DIAS)
    esperado = len([f for f in fechas_comunes if f >= inicio_ventana_esperado])
    assert filas_nuevas == esperado

    destino_full = tmp_path / "completo.csv"
    _escribir_filtrado(df_ion, fechas_comunes, str(destino_full))

    df_inc = pd.read_csv(destino_inc, encoding="utf-8-sig")
    df_full = pd.read_csv(destino_full, encoding="utf-8-sig")
    assert df_inc.equals(df_full)
    assert len(df_inc) == len(fechas_comunes)


def test_escribir_filtrado_dia_abierto_recoge_actualizacion(tmp_path):
    """El caso real que motivo este cambio: Verificar puede traer, en
    corridas sucesivas, un valor actualizado para una fecha ya escrita en
    el filtrado ese mismo dia (ver bess/data/pipeline/verify.py y, mas
    atras, bess/data/ingest/ion/export_csv.py). La siguiente corrida de
    Filtrar debe reflejarlo, no quedarse pegada en lo que ya se habia
    escrito."""
    fechas = pd.date_range("2026-07-15 00:05:00", "2026-07-15 23:55:00", freq="5min")
    df = pd.DataFrame({
        "Fecha": fechas,
        "KWH_REC": 0.0,
        "KWH_ENT": 0.0,
    })
    destino = tmp_path / "salida.csv"

    _escribir_filtrado(df, set(df["Fecha"]), str(destino))
    df1 = pd.read_csv(destino, encoding="utf-8-sig")
    assert (df1["KWH_REC"] == 0).all()

    # Verificar trae un valor real para una hora ya escrita ese dia.
    df.loc[df["Fecha"] == pd.Timestamp("2026-07-15 12:15:00"), "KWH_REC"] = 129.6

    _escribir_filtrado(df, set(df["Fecha"]), str(destino))
    df2 = pd.read_csv(destino, encoding="utf-8-sig")
    # generar_archivo_limpio escribe Fecha en formato DD/MM/YYYY.
    fila = df2[df2["Fecha"] == "15/07/2026 12:15:00"]
    assert len(fila) == 1, "la fila se duplico o se perdio al recalcular la ventana"
    assert fila.iloc[0]["KWH_REC"] == 129.6
    assert len(df2) == len(df1), "la cantidad de filas no debia cambiar, solo el valor"


def test_escribir_filtrado_dias_cerrados_no_se_tocan(tmp_path):
    """Un dia bien anterior a la ventana de recalculo no debe verse
    afectado por cambios fuera de esa ventana -- solo los ultimos
    MARGEN_REEXPORTAR_DIAS dias se vuelven a escribir en cada corrida
    incremental."""
    fechas = pd.date_range("2026-08-01 00:05:00", "2026-08-10 00:00:00", freq="5min")
    df = _df(fechas)
    destino = tmp_path / "salida.csv"

    _escribir_filtrado(df, set(df["Fecha"]), str(destino))
    df1 = pd.read_csv(destino, encoding="utf-8-sig")

    # "Corromper" un dia bien cerrado, fuera de la ventana de recalculo.
    df.loc[df["Fecha"].dt.strftime("%Y-%m-%d") == "2026-08-02", "KWH_REC"] = 999.0

    _escribir_filtrado(df, set(df["Fecha"]), str(destino))
    df2 = pd.read_csv(destino, encoding="utf-8-sig")
    # generar_archivo_limpio escribe Fecha en formato DD/MM/YYYY.
    dia2_antes = df1[df1["Fecha"].str.startswith("02/08/2026")].reset_index(drop=True)
    dia2_despues = df2[df2["Fecha"].str.startswith("02/08/2026")].reset_index(drop=True)
    assert len(dia2_antes) > 0, "la prueba no esta comparando nada -- revisar el formato de Fecha"
    assert dia2_despues.equals(dia2_antes)
    assert not (dia2_despues["KWH_REC"] == 999.0).any()


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
