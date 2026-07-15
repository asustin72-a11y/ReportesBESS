"""Pruebas de agregados diarios incrementales (Fase 5.2 del plan CSV->SQLite).

generar_diarios_con_demandas() agrupa el combinado por minuto por FECHA (+
PERIODO) -- cada día es independiente de los demás, sin ventana rodante ni
acumulado entre días en este cálculo -- así que recalcular solo el último
día ya escrito (por si seguía abierto) más los días nuevos, y conservar los
días ya cerrados, da exactamente el mismo resultado que recalcular todo el
histórico.

Las pruebas cubren: primera corrida completa, incremental == completo con
un split a mitad de historia, que el último día ya escrito se recalcule
correctamente si le llegan más registros (día "reabierto"), no-op sin días
nuevos, fallback a completo si cambia el formato de columnas, y una
comparación con el combinado real de IUSA_1.

Las comparaciones de equivalencia usan check_exact=False (tolerancia
mínima): sumar los mismos valores en un lote distinto (todo el
histórico vs. solo el día reabierto) puede diferir en el último dígito
de precisión float por el orden de suma (la suma en punto flotante no
es asociativa) -- una diferencia inmaterial para datos de facturación
(muy por debajo de la resolución de cualquier medidor real), no un
error de cálculo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import bess.config.rutas as rutas_mod
from bess.config.subestaciones import SUBESTACIONES
from bess.data.aggregates.daily import generar_diarios_con_demandas

SUB_IUSA_1 = next(s for s in SUBESTACIONES if s.id == "IUSA_1")
MED_ION = next(m for m in SUB_IUSA_1.medidores_consumo if m.nombre == "ION_Testigo_IUSA1")
PREFIJO = MED_ION.prefijo


def _combinado_sintetico(fechas_hora: pd.DatetimeIndex, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(fechas_hora)
    df = pd.DataFrame({
        "FECHA_HORA": fechas_hora.strftime("%d/%m/%Y %H:%M"),
        "KWH_REC_BESS": np.round(rng.random(n) * 2, 3),
        "KWH_ENT_BESS": np.round(rng.random(n) * 0.5, 3),
        f"KWH_REC_{PREFIJO}": np.round(rng.random(n) * 5 + 1, 3),
        f"KWH_ENT_{PREFIJO}": np.zeros(n),
        f"IUSA_CON_BESS_{PREFIJO}_kW_DEM_15min": np.round(rng.random(n) * 50, 3),
        f"IUSA_SIN_BESS_{PREFIJO}_kW_DEM_15min": np.round(rng.random(n) * 50, 3),
    })
    return df


def _escribir_combinado(df, tmp_dir, monkeypatch):
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_dir)
    ruta = MED_ION.ruta_combinado()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    return ruta


def test_diarios_primera_vez_modo_completo(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-01-05 00:05:00", "2026-01-07 00:00:00", freq="5min")
    _escribir_combinado(_combinado_sintetico(fechas), tmp_path, monkeypatch)

    df = generar_diarios_con_demandas(PREFIJO)

    assert df is not None
    # Día operativo 00:05-00:00: el rango cubre 2 días completos (05 y 06);
    # el registro final (07/01 00:00) cierra el día 06, no abre el 07.
    assert len(df) == 2
    assert set(df["FECHA"]) == {"05/01/2026", "06/01/2026"}


def test_diarios_incremental_equivale_a_completo(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-02-01 00:05:00", "2026-02-05 00:00:00", freq="5min")
    combinado = _combinado_sintetico(fechas)
    mitad = len(combinado) // 2  # corta a media día 3

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    _escribir_combinado(combinado.iloc[:mitad], dir_inc, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)

    _escribir_combinado(combinado, dir_inc, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)
    salida_inc = pd.read_csv(MED_ION.ruta_energia_dia())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    _escribir_combinado(combinado, dir_full, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)
    salida_full = pd.read_csv(MED_ION.ruta_energia_dia())

    assert len(salida_inc) == 4  # días operativos 01 al 04 de febrero
    pd.testing.assert_frame_equal(
        salida_inc, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )


def test_diarios_ultimo_dia_reabierto_se_recalcula(tmp_path, monkeypatch):
    """El cron corre cada 15 min: el día de hoy se recalcula varias veces
    mientras siguen llegando registros. La fila de ese día en el reporte
    diario debe reflejar SIEMPRE el total acumulado hasta el momento, no
    quedarse con el valor de la primera corrida parcial."""
    dia1 = pd.date_range("2026-03-01 00:05:00", "2026-03-01 12:00:00", freq="5min")
    dia1_completo = pd.date_range("2026-03-01 00:05:00", "2026-03-02 00:00:00", freq="5min")

    _escribir_combinado(_combinado_sintetico(dia1), tmp_path, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)
    salida_parcial = pd.read_csv(MED_ION.ruta_energia_dia())
    assert len(salida_parcial) == 1
    rec_parcial = (
        salida_parcial["BASE_REC"].iloc[0]
        + salida_parcial["INTERMEDIO_REC"].iloc[0]
        + salida_parcial["PUNTA_REC"].iloc[0]
    )

    _escribir_combinado(_combinado_sintetico(dia1_completo), tmp_path, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)
    salida_final = pd.read_csv(MED_ION.ruta_energia_dia())
    assert len(salida_final) == 1  # sigue siendo un solo día, no un día duplicado
    rec_final = (
        salida_final["BASE_REC"].iloc[0]
        + salida_final["INTERMEDIO_REC"].iloc[0]
        + salida_final["PUNTA_REC"].iloc[0]
    )

    assert rec_final > rec_parcial  # se agregó energía del resto del día

    # Debe ser exactamente igual a una corrida completa sobre el día entero.
    dir_full = tmp_path / "full_dia1"
    dir_full.mkdir()
    _escribir_combinado(_combinado_sintetico(dia1_completo), dir_full, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)
    salida_full = pd.read_csv(MED_ION.ruta_energia_dia())
    pd.testing.assert_frame_equal(
        salida_final, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )


def test_diarios_sin_dias_nuevos_es_no_op(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-04-01 00:05:00", "2026-04-01 12:00:00", freq="5min")
    _escribir_combinado(_combinado_sintetico(fechas), tmp_path, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)
    contenido_antes = MED_ION.ruta_energia_dia().read_bytes()

    df = generar_diarios_con_demandas(PREFIJO)

    assert df is not None
    assert MED_ION.ruta_energia_dia().read_bytes() == contenido_antes


def test_diarios_columnas_distintas_recalcula_completo(tmp_path, monkeypatch):
    fechas = pd.date_range("2026-05-01 00:05:00", "2026-05-02 00:00:00", freq="5min")
    _escribir_combinado(_combinado_sintetico(fechas), tmp_path, monkeypatch)

    ruta_salida = MED_ION.ruta_energia_dia()
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"FECHA": ["01/05/2026"], "OTRA_COL": [1]}).to_csv(ruta_salida, index=False)

    df = generar_diarios_con_demandas(PREFIJO)

    assert df is not None
    assert len(df) == 1
    assert "OTRA_COL" not in df.columns


def test_diarios_incremental_equivale_a_completo_datos_reales(tmp_path, monkeypatch):
    ruta_real = "data/ArchivosReporte/IUSA_1/COMBINADO_POR_MINUTO_ION_Testigo_IUSA1_IUSA_1.csv"
    df_real = pd.read_csv(ruta_real)
    if len(df_real) < 500:
        pytest.skip("no hay suficiente combinado real de IUSA_1 para esta prueba")
    mitad = len(df_real) // 2

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    _escribir_combinado(df_real.iloc[:mitad], dir_inc, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)

    _escribir_combinado(df_real, dir_inc, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)
    salida_inc = pd.read_csv(MED_ION.ruta_energia_dia())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    _escribir_combinado(df_real, dir_full, monkeypatch)
    generar_diarios_con_demandas(PREFIJO)
    salida_full = pd.read_csv(MED_ION.ruta_energia_dia())

    pd.testing.assert_frame_equal(
        salida_inc, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )
