"""Pruebas de reportes de generación/granja incrementales (Fase 5.5 del
plan CSV->SQLite).

generar_reportes_generacion() escribe dos archivos a partir del CSV
filtrado de generación:
  - COMBINADO_POR_MINUTO_{prefijo}.csv: passthrough FECHA/FECHA_HORA/KWH,
    sin columnas derivadas ni dependencia entre filas -- cursor simple
    sobre FECHA_HORA, sin necesidad de contexto (a diferencia de
    combined.py).
  - ENERGIA_Generacion_{sub}_POR_DIA.csv: agregado por día, mismo patrón
    de "recalcular el último día abierto + días nuevos" que daily.py /
    bess_daily.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import bess.config.rutas as rutas_mod
from bess.data.aggregates.granja import generar_reportes_generacion

SUBESTACION = "IUSA_2"
PREFIJO = "Generacion_IUSA_2"


def _filtrado_sintetico(fechas: pd.DatetimeIndex, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(fechas)
    return pd.DataFrame({
        "Fecha": fechas.strftime("%Y-%m-%d %H:%M:%S"),
        "KWH_REC": np.round(rng.random(n) * 3, 3),
        "KWH_ENT": np.zeros(n),
    })


def _escribir_filtrado(df, ruta, monkeypatch, tmp_dir):
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_dir)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8-sig")


def _rutas_reporte(tmp_dir):
    ruta_min = tmp_dir / SUBESTACION / f"COMBINADO_POR_MINUTO_{PREFIJO}.csv"
    ruta_dia = tmp_dir / SUBESTACION / f"ENERGIA_Generacion_{SUBESTACION}_POR_DIA.csv"
    return ruta_min, ruta_dia


def test_granja_primera_vez_modo_completo(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-01-05 00:05:00", "2026-01-07 00:00:00", freq="5min")
    ruta_filtrado = tmp_path / "fuente.csv"
    _escribir_filtrado(_filtrado_sintetico(fechas), ruta_filtrado, monkeypatch, tmp_path)

    resultado = generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)

    ruta_min, ruta_dia = _rutas_reporte(tmp_path)
    assert resultado
    df_min = pd.read_csv(ruta_min)
    df_dia = pd.read_csv(ruta_dia)
    assert len(df_min) == len(fechas)
    assert len(df_dia) == 2  # días operativos 05 y 06 de enero
    assert list(df_min.columns) == ["FECHA", "FECHA_HORA", "KWH_REC"]


def test_granja_incremental_equivale_a_completo(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-02-01 00:05:00", "2026-02-05 00:00:00", freq="5min")
    filtrado = _filtrado_sintetico(fechas)
    mitad = len(filtrado) // 2

    dir_inc = tmp_path / "inc"
    ruta_filtrado = dir_inc / "fuente.csv"
    _escribir_filtrado(filtrado.iloc[:mitad], ruta_filtrado, monkeypatch, dir_inc)
    generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)

    _escribir_filtrado(filtrado, ruta_filtrado, monkeypatch, dir_inc)
    generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)
    ruta_min_inc, ruta_dia_inc = _rutas_reporte(dir_inc)
    min_inc = pd.read_csv(ruta_min_inc)
    dia_inc = pd.read_csv(ruta_dia_inc)

    dir_full = tmp_path / "full"
    ruta_filtrado_full = dir_full / "fuente.csv"
    _escribir_filtrado(filtrado, ruta_filtrado_full, monkeypatch, dir_full)
    generar_reportes_generacion(str(ruta_filtrado_full), SUBESTACION, PREFIJO)
    ruta_min_full, ruta_dia_full = _rutas_reporte(dir_full)
    min_full = pd.read_csv(ruta_min_full)
    dia_full = pd.read_csv(ruta_dia_full)

    assert len(min_inc) == len(filtrado)
    assert len(dia_inc) == 4
    pd.testing.assert_frame_equal(min_inc, min_full)
    pd.testing.assert_frame_equal(dia_inc, dia_full, check_exact=False, rtol=1e-9, atol=1e-6)


def test_granja_ultimo_dia_reabierto_se_recalcula(tmp_path, monkeypatch):
    dia1 = pd.date_range("2026-03-01 00:05:00", "2026-03-01 12:00:00", freq="5min")
    dia1_completo = pd.date_range("2026-03-01 00:05:00", "2026-03-02 00:00:00", freq="5min")

    ruta_filtrado = tmp_path / "fuente.csv"
    _escribir_filtrado(_filtrado_sintetico(dia1), ruta_filtrado, monkeypatch, tmp_path)
    generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)
    _, ruta_dia = _rutas_reporte(tmp_path)
    dia_parcial = pd.read_csv(ruta_dia)
    assert len(dia_parcial) == 1
    rec_parcial = dia_parcial["BASE_REC"].iloc[0] + dia_parcial["INTERMEDIO_REC"].iloc[0] + dia_parcial["PUNTA_REC"].iloc[0]

    _escribir_filtrado(_filtrado_sintetico(dia1_completo), ruta_filtrado, monkeypatch, tmp_path)
    generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)
    dia_final = pd.read_csv(ruta_dia)
    assert len(dia_final) == 1
    rec_final = dia_final["BASE_REC"].iloc[0] + dia_final["INTERMEDIO_REC"].iloc[0] + dia_final["PUNTA_REC"].iloc[0]
    assert rec_final > rec_parcial

    # También el combinado por minuto debe reflejar todo el día, no solo la mitad.
    ruta_min, _ = _rutas_reporte(tmp_path)
    assert len(pd.read_csv(ruta_min)) == len(dia1_completo)


def test_granja_sin_dias_nuevos_es_no_op(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-04-01 00:05:00", "2026-04-01 12:00:00", freq="5min")
    ruta_filtrado = tmp_path / "fuente.csv"
    _escribir_filtrado(_filtrado_sintetico(fechas), ruta_filtrado, monkeypatch, tmp_path)
    generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)
    ruta_min, ruta_dia = _rutas_reporte(tmp_path)
    contenido_min_antes = ruta_min.read_bytes()
    contenido_dia_antes = ruta_dia.read_bytes()

    resultado = generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)

    assert resultado
    assert ruta_min.read_bytes() == contenido_min_antes
    assert ruta_dia.read_bytes() == contenido_dia_antes


def test_granja_incremental_equivale_a_completo_datos_reales(tmp_path, monkeypatch):
    ruta_real = "data/ArchivosProcesados/IUSA_2/Generacion_IUSA_2_Filtrado.csv"
    df_real = pd.read_csv(ruta_real, encoding="utf-8-sig")
    if len(df_real) < 500:
        pytest.skip("no hay suficientes datos reales de generación IUSA_2 para esta prueba")
    mitad = len(df_real) // 2

    dir_inc = tmp_path / "inc"
    ruta_filtrado = dir_inc / "fuente.csv"
    _escribir_filtrado(df_real.iloc[:mitad], ruta_filtrado, monkeypatch, dir_inc)
    generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)

    _escribir_filtrado(df_real, ruta_filtrado, monkeypatch, dir_inc)
    generar_reportes_generacion(str(ruta_filtrado), SUBESTACION, PREFIJO)
    ruta_min_inc, ruta_dia_inc = _rutas_reporte(dir_inc)
    min_inc = pd.read_csv(ruta_min_inc)
    dia_inc = pd.read_csv(ruta_dia_inc)

    dir_full = tmp_path / "full"
    ruta_filtrado_full = dir_full / "fuente.csv"
    _escribir_filtrado(df_real, ruta_filtrado_full, monkeypatch, dir_full)
    generar_reportes_generacion(str(ruta_filtrado_full), SUBESTACION, PREFIJO)
    ruta_min_full, ruta_dia_full = _rutas_reporte(dir_full)
    min_full = pd.read_csv(ruta_min_full)
    dia_full = pd.read_csv(ruta_dia_full)

    pd.testing.assert_frame_equal(min_inc, min_full)
    pd.testing.assert_frame_equal(dia_inc, dia_full, check_exact=False, rtol=1e-9, atol=1e-6)
