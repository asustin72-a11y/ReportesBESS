"""Pruebas de reporte diario BESS incremental (Fase 5.4 del plan CSV->SQLite).

generar_bess_diario_subestacion() agrupa el combinado por minuto por
FECHA (+ PERIODO) igual que daily.py -- cada día es independiente, sin
ventana ni acumulado entre días -- así que recalcular solo el último día
ya escrito (por si seguía abierto) más los días nuevos, conservando los
días ya cerrados, da el mismo resultado que recalcular todo el histórico.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import bess.config.rutas as rutas_mod
from bess.config.subestaciones import SUBESTACIONES
from bess.data.aggregates.bess_daily import generar_bess_diario_subestacion

SUB_IUSA_1 = next(s for s in SUBESTACIONES if s.id == "IUSA_1")
MED_FACT = SUB_IUSA_1.medidor_facturacion
PREFIJO = MED_FACT.prefijo


def _combinado_sintetico(fechas_hora: pd.DatetimeIndex, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(fechas_hora)
    return pd.DataFrame({
        "FECHA_HORA": fechas_hora.strftime("%d/%m/%Y %H:%M"),
        "KWH_REC_BESS": np.round(rng.random(n) * 2, 3),
        "KWH_ENT_BESS": np.round(rng.random(n) * 0.5, 3),
    })


def _escribir_combinado(df, tmp_dir, monkeypatch):
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_dir)
    ruta = MED_FACT.ruta_combinado()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    return ruta


def _ruta_salida():
    return SUB_IUSA_1.ruta_energia_bess_dia()


def test_bess_diario_primera_vez_modo_completo(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-01-05 00:05:00", "2026-01-07 00:00:00", freq="5min")
    _escribir_combinado(_combinado_sintetico(fechas), tmp_path, monkeypatch)

    df = generar_bess_diario_subestacion(SUB_IUSA_1)

    assert df is not None
    assert len(df) == 2  # días operativos 05 y 06 de enero
    assert set(df["FECHA"]) == {"05/01/2026", "06/01/2026"}


def test_bess_diario_incremental_equivale_a_completo(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-02-01 00:05:00", "2026-02-05 00:00:00", freq="5min")
    combinado = _combinado_sintetico(fechas)
    mitad = len(combinado) // 2

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    _escribir_combinado(combinado.iloc[:mitad], dir_inc, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)

    _escribir_combinado(combinado, dir_inc, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)
    salida_inc = pd.read_csv(_ruta_salida())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    _escribir_combinado(combinado, dir_full, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)
    salida_full = pd.read_csv(_ruta_salida())

    assert len(salida_inc) == 4
    pd.testing.assert_frame_equal(
        salida_inc, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )


def test_bess_diario_ultimo_dia_reabierto_se_recalcula(tmp_path, monkeypatch):
    dia1 = pd.date_range("2026-03-01 00:05:00", "2026-03-01 12:00:00", freq="5min")
    dia1_completo = pd.date_range("2026-03-01 00:05:00", "2026-03-02 00:00:00", freq="5min")

    _escribir_combinado(_combinado_sintetico(dia1), tmp_path, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)
    salida_parcial = pd.read_csv(_ruta_salida())
    assert len(salida_parcial) == 1
    rec_parcial = (
        salida_parcial["BASE_REC"].iloc[0]
        + salida_parcial["INTERMEDIO_REC"].iloc[0]
        + salida_parcial["PUNTA_REC"].iloc[0]
    )

    _escribir_combinado(_combinado_sintetico(dia1_completo), tmp_path, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)
    salida_final = pd.read_csv(_ruta_salida())
    assert len(salida_final) == 1
    rec_final = (
        salida_final["BASE_REC"].iloc[0]
        + salida_final["INTERMEDIO_REC"].iloc[0]
        + salida_final["PUNTA_REC"].iloc[0]
    )
    assert rec_final > rec_parcial

    dir_full = tmp_path / "full_dia1"
    dir_full.mkdir()
    _escribir_combinado(_combinado_sintetico(dia1_completo), dir_full, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)
    salida_full = pd.read_csv(_ruta_salida())
    pd.testing.assert_frame_equal(
        salida_final, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )


def test_bess_diario_sin_dias_nuevos_es_no_op(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-04-01 00:05:00", "2026-04-01 12:00:00", freq="5min")
    _escribir_combinado(_combinado_sintetico(fechas), tmp_path, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)
    contenido_antes = _ruta_salida().read_bytes()

    df = generar_bess_diario_subestacion(SUB_IUSA_1)

    assert df is not None
    assert _ruta_salida().read_bytes() == contenido_antes


def test_bess_diario_columnas_distintas_recalcula_completo(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-05-01 00:05:00", "2026-05-02 00:00:00", freq="5min")
    _escribir_combinado(_combinado_sintetico(fechas), tmp_path, monkeypatch)

    ruta_salida = _ruta_salida()
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"FECHA": ["01/05/2026"], "OTRA_COL": [1]}).to_csv(ruta_salida, index=False)

    df = generar_bess_diario_subestacion(SUB_IUSA_1)

    assert df is not None
    assert len(df) == 1
    assert "OTRA_COL" not in df.columns


def test_bess_diario_incremental_equivale_a_completo_datos_reales(tmp_path, monkeypatch):
    ruta_real = "data/ArchivosReporte/IUSA_1/COMBINADO_POR_MINUTO_ION_Testigo_IUSA1_IUSA_1.csv"
    df_real = pd.read_csv(ruta_real)
    if len(df_real) < 500:
        pytest.skip("no hay suficiente combinado real de IUSA_1 para esta prueba")
    mitad = len(df_real) // 2

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    _escribir_combinado(df_real.iloc[:mitad], dir_inc, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)

    _escribir_combinado(df_real, dir_inc, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)
    salida_inc = pd.read_csv(_ruta_salida())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    _escribir_combinado(df_real, dir_full, monkeypatch)
    generar_bess_diario_subestacion(SUB_IUSA_1)
    salida_full = pd.read_csv(_ruta_salida())

    pd.testing.assert_frame_equal(
        salida_inc, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )
