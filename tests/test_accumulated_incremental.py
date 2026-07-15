"""Pruebas de acumulados incrementales (Fase 5.3 del plan CSV->SQLite).

generar_acumulados() calcula, a partir del reporte diario, un cumsum de
energía y un máximo corrido de demanda -- ambos reiniciados cada mes. A
diferencia de daily.py, aquí SÍ hay dependencia entre días consecutivos
del mismo mes: el cumsum/máximo de un día depende del día anterior. La
versión incremental hereda ese estado (semilla) del día anterior al
último ya escrito, y solo recalcula desde ahí -- reiniciando en 0 si el
día ya escrito era el primero de su mes, igual que una corrida completa.

Las comparaciones de equivalencia usan check_exact=False por la misma
razón que en daily.py: sumar en un lote distinto puede diferir en el
último dígito de precisión float (orden de suma no asociativo),
inmaterial para facturación.
"""

from __future__ import annotations

import pandas as pd
import pytest

import bess.config.rutas as rutas_mod
from bess.config.subestaciones import SUBESTACIONES
from bess.data.aggregates.accumulated import generar_acumulados
from bess.data.aggregates.daily import COLUMNAS_DIARIO

SUB_IUSA_1 = next(s for s in SUBESTACIONES if s.id == "IUSA_1")
MED_ION = next(m for m in SUB_IUSA_1.medidores_consumo if m.nombre == "ION_Testigo_IUSA1")
PREFIJO = MED_ION.prefijo


def _diario_sintetico(fechas: list[str], rec_base: float = 100.0, paso: float = 10.0) -> pd.DataFrame:
    """Un ENERGIA_*_POR_DIA.csv sintético: una fila por fecha (DD/MM/YYYY),
    con REC/ENT crecientes y una demanda máxima fija por fecha (derivada
    del índice) para poder verificar el máximo corrido fácilmente."""
    filas = []
    for i, fecha in enumerate(fechas):
        valor_rec = rec_base + i * paso
        valor_dem = 50.0 + (i % 5) * 10.0  # varía para ejercitar el máximo corrido
        filas.append({
            "FECHA": fecha,
            "BASE_ENT": 0.0, "INTERMEDIO_ENT": 0.0, "PUNTA_ENT": 0.0,
            "BASE_REC": valor_rec, "INTERMEDIO_REC": valor_rec, "PUNTA_REC": valor_rec,
            "BASE_REC_SIN_BESS": valor_rec, "INTERMEDIO_REC_SIN_BESS": valor_rec, "PUNTA_REC_SIN_BESS": valor_rec,
            "KVARH": valor_rec * 0.1,
            "BASE_DEM_CON_BESS": valor_dem, "BASE_DEM_CON_BESS_FECHA_HORA": f"{fecha} 12:00",
            "INTERMEDIO_DEM_CON_BESS": valor_dem, "INTERMEDIO_DEM_CON_BESS_FECHA_HORA": f"{fecha} 12:00",
            "PUNTA_DEM_CON_BESS": valor_dem, "PUNTA_DEM_CON_BESS_FECHA_HORA": f"{fecha} 12:00",
            "BASE_DEM_SIN_BESS": valor_dem, "BASE_DEM_SIN_BESS_FECHA_HORA": f"{fecha} 12:00",
            "INTERMEDIO_DEM_SIN_BESS": valor_dem, "INTERMEDIO_DEM_SIN_BESS_FECHA_HORA": f"{fecha} 12:00",
            "PUNTA_DEM_SIN_BESS": valor_dem, "PUNTA_DEM_SIN_BESS_FECHA_HORA": f"{fecha} 12:00",
        })
    df = pd.DataFrame(filas)
    return df[COLUMNAS_DIARIO]


def _escribir_diario(df, tmp_dir, monkeypatch):
    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_dir)
    ruta = MED_ION.ruta_energia_dia()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    return ruta


def _fechas_mes(dia_inicio: int, dia_fin: int, mes: int, anio: int = 2026) -> list[str]:
    return [f"{d:02d}/{mes:02d}/{anio}" for d in range(dia_inicio, dia_fin + 1)]


def test_acumulados_primera_vez_modo_completo(tmp_path, monkeypatch):
    fechas = _fechas_mes(1, 5, 1)
    _escribir_diario(_diario_sintetico(fechas), tmp_path, monkeypatch)

    df = generar_acumulados(PREFIJO)

    assert df is not None
    assert len(df) == 5
    # cumsum del 5o día = suma de los 5 valores REC (100+110+120+130+140)
    assert df["BASE_REC_ACUM"].iloc[-1] == pytest.approx(100 + 110 + 120 + 130 + 140)


def test_acumulados_incremental_equivale_a_completo_mismo_mes(tmp_path, monkeypatch):
    fechas = _fechas_mes(1, 10, 2)
    diario = _diario_sintetico(fechas)
    mitad = 6

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    _escribir_diario(diario.iloc[:mitad], dir_inc, monkeypatch)
    generar_acumulados(PREFIJO)

    _escribir_diario(diario, dir_inc, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_inc = pd.read_csv(MED_ION.ruta_acumulados())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    _escribir_diario(diario, dir_full, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_full = pd.read_csv(MED_ION.ruta_acumulados())

    assert len(salida_inc) == 10
    pd.testing.assert_frame_equal(
        salida_inc, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )


def test_acumulados_incremental_equivale_a_completo_frontera_mes(tmp_path, monkeypatch):
    """Split justo en la frontera marzo/abril: el cumsum y el máximo
    corrido deben reiniciar en 0 al llegar a abril, tanto en la corrida
    incremental como en la completa."""
    fechas = _fechas_mes(28, 31, 3) + _fechas_mes(1, 3, 4)
    diario = _diario_sintetico(fechas)
    corte = 4  # hasta el 31/03 inclusive

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    _escribir_diario(diario.iloc[:corte], dir_inc, monkeypatch)
    generar_acumulados(PREFIJO)

    _escribir_diario(diario, dir_inc, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_inc = pd.read_csv(MED_ION.ruta_acumulados())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    _escribir_diario(diario, dir_full, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_full = pd.read_csv(MED_ION.ruta_acumulados())

    pd.testing.assert_frame_equal(
        salida_inc, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )

    fila_1_abril = salida_inc[salida_inc["FECHA"] == "01/04/2026"].iloc[0]
    # El cumsum de abril no debe incluir nada de marzo.
    assert fila_1_abril["BASE_REC_ACUM"] == pytest.approx(diario["BASE_REC"].iloc[corte])


def test_acumulados_ultimo_dia_reabierto_se_recalcula(tmp_path, monkeypatch):
    fechas = _fechas_mes(1, 3, 5)
    diario_v1 = _diario_sintetico(fechas, rec_base=100.0)

    _escribir_diario(diario_v1, tmp_path, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_v1 = pd.read_csv(MED_ION.ruta_acumulados())
    acum_dia3_v1 = salida_v1["BASE_REC_ACUM"].iloc[-1]

    # El día 3 (el último) "crece": más energía llegó en una sync posterior.
    diario_v2 = diario_v1.copy()
    diario_v2.loc[diario_v2["FECHA"] == fechas[-1], "BASE_REC"] += 500
    _escribir_diario(diario_v2, tmp_path, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_v2 = pd.read_csv(MED_ION.ruta_acumulados())

    assert len(salida_v2) == 3  # sigue siendo el mismo día, no uno nuevo
    acum_dia3_v2 = salida_v2["BASE_REC_ACUM"].iloc[-1]
    assert acum_dia3_v2 == pytest.approx(acum_dia3_v1 + 500)

    # Debe coincidir con una corrida completa sobre los datos finales.
    dir_full = tmp_path / "full"
    dir_full.mkdir()
    _escribir_diario(diario_v2, dir_full, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_full = pd.read_csv(MED_ION.ruta_acumulados())
    pd.testing.assert_frame_equal(
        salida_v2, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )


def test_acumulados_sin_dias_nuevos_es_no_op(tmp_path, monkeypatch):
    fechas = _fechas_mes(1, 3, 6)
    _escribir_diario(_diario_sintetico(fechas), tmp_path, monkeypatch)
    generar_acumulados(PREFIJO)
    contenido_antes = MED_ION.ruta_acumulados().read_bytes()

    df = generar_acumulados(PREFIJO)

    assert df is not None
    assert MED_ION.ruta_acumulados().read_bytes() == contenido_antes


def test_acumulados_columnas_distintas_recalcula_completo(tmp_path, monkeypatch):
    fechas = _fechas_mes(1, 3, 7)
    _escribir_diario(_diario_sintetico(fechas), tmp_path, monkeypatch)

    ruta_salida = MED_ION.ruta_acumulados()
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"FECHA": ["01/07/2026"], "OTRA_COL": [1]}).to_csv(ruta_salida, index=False)

    df = generar_acumulados(PREFIJO)

    assert df is not None
    assert len(df) == 3
    assert "OTRA_COL" not in df.columns


def test_acumulados_incremental_equivale_a_completo_datos_reales(tmp_path, monkeypatch):
    ruta_real = "data/ArchivosReporte/IUSA_1/ENERGIA_ION_Testigo_IUSA1_IUSA_1_POR_DIA.csv"
    df_real = pd.read_csv(ruta_real)
    if len(df_real) < 20:
        pytest.skip("no hay suficiente energía diaria real de IUSA_1 para esta prueba")
    mitad = len(df_real) // 2

    dir_inc = tmp_path / "inc"
    dir_inc.mkdir()
    _escribir_diario(df_real.iloc[:mitad], dir_inc, monkeypatch)
    generar_acumulados(PREFIJO)

    _escribir_diario(df_real, dir_inc, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_inc = pd.read_csv(MED_ION.ruta_acumulados())

    dir_full = tmp_path / "full"
    dir_full.mkdir()
    _escribir_diario(df_real, dir_full, monkeypatch)
    generar_acumulados(PREFIJO)
    salida_full = pd.read_csv(MED_ION.ruta_acumulados())

    pd.testing.assert_frame_equal(
        salida_inc, salida_full, check_exact=False, rtol=1e-9, atol=1e-6
    )
