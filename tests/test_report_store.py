"""Round-trip CSV ↔ report_store (Fase 7.0)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bess.data.report_store import (
    cargar_reporte,
    fallback_csv_habilitado,
    leer_dataframe,
    serie_id_desde_nombre,
    sincronizar_desde_csv,
    tipo_y_stem_desde_nombre,
)


def test_tipo_desde_nombre():
    assert tipo_y_stem_desde_nombre(
        "COMBINADO_POR_MINUTO_ION_Testigo_IUSA1_IUSA_1.csv"
    ) == ("combinado", "ION_Testigo_IUSA1_IUSA_1")
    assert tipo_y_stem_desde_nombre("ENERGIA_BESS_IUSA_1_POR_DIA.csv") == (
        "bess_dia",
        "IUSA_1",
    )
    assert tipo_y_stem_desde_nombre(
        "ENERGIA_ION_Testigo_IUSA1_IUSA_1_POR_DIA.csv"
    ) == ("energia_dia", "ION_Testigo_IUSA1_IUSA_1")
    assert tipo_y_stem_desde_nombre("ACUMULADOS_X_IUSA_1.csv") == (
        "acumulados",
        "X_IUSA_1",
    )


def test_roundtrip_combinado(tmp_path, monkeypatch):
    bd = tmp_path / "t.db"
    monkeypatch.setattr("bess.data.report_store.RUTA_BD_PERFILES", bd)
    csv = tmp_path / "COMBINADO_POR_MINUTO_MED_SUB.csv"
    df = pd.DataFrame(
        {
            "FECHA": ["01/05/2026", "01/05/2026"],
            "FECHA_HORA": ["01/05/2026 00:05", "01/05/2026 00:10"],
            "PERIODO": ["Base", "Base"],
            "KWH_REC_BESS": [0.0, 1.5],
            "KWH_REC_MED": [10.0, 11.0],
        }
    )
    df.to_csv(csv, index=False)
    n = sincronizar_desde_csv(csv, ruta_bd=bd)
    assert n == 2
    sid = serie_id_desde_nombre(csv.name)
    out = leer_dataframe(sid, ruta_bd=bd)
    assert out is not None
    assert list(out.columns) == list(df.columns)
    assert len(out) == 2
    assert float(out.loc[0, "KWH_REC_MED"]) == 10.0


def test_cargar_prefiere_bd(tmp_path, monkeypatch):
    bd = tmp_path / "t.db"
    monkeypatch.setattr("bess.data.report_store.RUTA_BD_PERFILES", bd)
    monkeypatch.setenv("BESS_REPORTES_FALLBACK_CSV", "0")
    csv = tmp_path / "ENERGIA_BESS_SUB_POR_DIA.csv"
    df_csv = pd.DataFrame({"FECHA": ["01/05/2026"], "BASE_REC": [1.0]})
    df_csv.to_csv(csv, index=False)
    sincronizar_desde_csv(csv, ruta_bd=bd)
    # Ensuciar CSV: cargar debe seguir leyendo BD
    pd.DataFrame({"FECHA": ["01/05/2026"], "BASE_REC": [999.0]}).to_csv(csv, index=False)
    loaded = cargar_reporte(csv, ruta_bd=bd)
    assert float(loaded.loc[0, "BASE_REC"]) == 1.0
    assert not fallback_csv_habilitado()


def test_guardar_dataframe_bd_primero(tmp_path, monkeypatch):
    from bess.data.report_store import guardar_dataframe_reporte, leer_dataframe, serie_id_desde_nombre

    bd = tmp_path / "t.db"
    monkeypatch.setattr("bess.data.report_store.RUTA_BD_PERFILES", bd)
    monkeypatch.setenv("BESS_REPORTES_ESCRIBIR_CSV", "0")
    ruta = tmp_path / "ACUMULADOS_MED_SUB.csv"
    df = pd.DataFrame({"FECHA": ["01/05/2026", "02/05/2026"], "BASE_REC_ACUM": [1.0, 2.0]})
    n = guardar_dataframe_reporte(ruta, df, ruta_bd=bd)
    assert n == 2
    assert not ruta.exists()
    out = leer_dataframe(serie_id_desde_nombre(ruta.name), ruta_bd=bd)
    assert out is not None and len(out) == 2
