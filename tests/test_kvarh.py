"""Pruebas de bess/core/kvarh.py: columnas y agregacion de energia reactiva."""

from __future__ import annotations

import pandas as pd

from bess.core.kvarh import columnas_kvarh, kvarh_total, normalizar_columnas_kvarh


def test_columnas_kvarh_solo_devuelve_las_presentes():
    df = pd.DataFrame({"Fecha": ["x"], "KVARH_Q1": [1], "KVARH_Q2": [2], "OTRA": [3]})
    assert columnas_kvarh(df) == ["KVARH_Q1", "KVARH_Q2"]


def test_columnas_kvarh_vacio_si_no_hay_ninguna():
    df = pd.DataFrame({"Fecha": ["x"], "OTRA": [3]})
    assert columnas_kvarh(df) == []


def test_normalizar_columnas_kvarh_convierte_y_rellena_no_numericos():
    df = pd.DataFrame({
        "Fecha": ["2026-01-01", "2026-01-02"],
        "KVARH_Q1": ["10", "20"],
        "KVARH_Q2": ["abc", "5"],  # 'abc' no es numerico -> debe quedar en 0
    })
    out = normalizar_columnas_kvarh(df.copy())
    assert out["KVARH_Q1"].tolist() == [10, 20]
    assert out["KVARH_Q2"].tolist() == [0, 5]


def test_kvarh_total_suma_todas_las_columnas_presentes():
    df = pd.DataFrame({
        "Fecha": ["2026-01-01", "2026-01-02"],
        "KVARH_Q1": [10, 20],
        "KVARH_Q2": [0, 5],
    })
    total = kvarh_total(df)
    assert total.tolist() == [10, 25]


def test_kvarh_total_devuelve_ceros_sin_columnas_kvarh():
    df = pd.DataFrame({"Fecha": ["a", "b"], "X": [1, 2]})
    total = kvarh_total(df)
    assert total.tolist() == [0.0, 0.0]
    assert len(total) == len(df)
