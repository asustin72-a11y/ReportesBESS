"""Resumen de máximos de demanda rolada en Análisis → Demanda."""

from __future__ import annotations

from datetime import date

import pandas as pd

from bess.cfe.report_data import construir_tabla_demanda_rolada_max_mes
from bess.core.demand import demanda_rodante_15min_por_mes


PREFIJO = "ION_Testigo_IUSA1"
COL_CON = f"IUSA_CON_BESS_{PREFIJO}_kW_DEM_15min"
COL_SIN = f"IUSA_SIN_BESS_{PREFIJO}_kW_DEM_15min"


def _bloque(fecha: str, hora0: str, periodo: str, kw_con: list[float], kw_sin: list[float]):
    """Tres intervalos de 5 min (ventana 15 min) en el mismo periodo."""
    h, m = map(int, hora0.split(":"))
    filas = []
    for i, (c, s) in enumerate(zip(kw_con, kw_sin, strict=True)):
        minutos = m + 5 * i
        hh = h + minutos // 60
        mm = minutos % 60
        filas.append(
            {
                "FECHA": fecha,
                "FECHA_HORA": f"{fecha} {hh:02d}:{mm:02d}",
                "PERIODO": periodo,
                COL_CON: c,
                COL_SIN: s,
            }
        )
    return filas


def test_maximo_usa_rolada_ceil_y_fecha_de_corte():
    """El pico del día posterior al corte no entra; kW va a entero CFE (ceil)."""
    filas = []
    # 02/09 punta: el máximo válido es el 3.er intervalo (los 2 primeros se enmascaran)
    filas += _bloque(
        "02/09/2026",
        "19:20",
        "Punta",
        [1000.0, 1000.0, 7000.0],
        [1000.0, 1000.0, 12632.26],
    )
    filas += _bloque(
        "02/09/2026",
        "22:00",
        "Base",
        [1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0],
    )
    # 23/09 punta con BESS 7943.09 → 7,944
    filas += _bloque(
        "23/09/2026",
        "19:15",
        "Punta",
        [1000.0, 1000.0, 7943.09],
        [1000.0, 1000.0, 12599.0],
    )
    # 25/09 posterior al corte: no debe ganar
    filas += _bloque(
        "25/09/2026",
        "19:15",
        "Punta",
        [99999.0, 99999.0, 99999.0],
        [99999.0, 99999.0, 99999.0],
    )
    filas += _bloque(
        "24/09/2026",
        "01:00",
        "Base",
        [1000.0, 1000.0, 20167.4],
        [1000.0, 1000.0, 12800.1],
    )
    filas += _bloque(
        "24/09/2026",
        "12:00",
        "Intermedio",
        [1000.0, 1000.0, 18782.0],
        [1000.0, 1000.0, 18782.0],
    )

    df = pd.DataFrame(filas)
    tabla = construir_tabla_demanda_rolada_max_mes(df, date(2026, 9, 24), PREFIJO)
    assert tabla is not None
    por = tabla.set_index("Periodo")

    assert por.loc["Punta", "Con BESS (kW, 15 min)"] == "7,944"
    assert por.loc["Punta", "Hora con BESS"] == "23/09/2026 19:25"
    assert por.loc["Punta", "Sin BESS (kW, 15 min)"] == "12,633"
    assert por.loc["Punta", "Hora sin BESS"] == "02/09/2026 19:30"
    assert por.loc["Base", "Con BESS (kW, 15 min)"] == "20,168"
    assert por.loc["Intermedio", "Con BESS (kW, 15 min)"] == "18,782"


def test_mascara_ignora_borde_mezclado_al_entrar_a_punta():
    """Los dos primeros intervalos de Punta no pueden ser el máximo."""
    filas = _bloque(
        "10/09/2026",
        "17:50",
        "Intermedio",
        [3.0, 3.0, 3.0],
        [3.0, 3.0, 3.0],
    )
    # Primeros dos de Punta inflados (mezcla de rolling); el tercero es el válido
    filas += _bloque(
        "10/09/2026",
        "18:00",
        "Punta",
        [999.0, 800.0, 50.0],
        [999.0, 800.0, 50.0],
    )
    df = pd.DataFrame(filas)
    tabla = construir_tabla_demanda_rolada_max_mes(df, date(2026, 9, 10), PREFIJO)
    por = tabla.set_index("Periodo")
    assert por.loc["Punta", "Con BESS (kW, 15 min)"] == "50"
    assert por.loc["Punta", "Hora con BESS"] == "10/09/2026 18:10"


def test_sin_columna_rolada_devuelve_none():
    df = pd.DataFrame({"FECHA": ["01/09/2026"], "PERIODO": ["Punta"]})
    assert construir_tabla_demanda_rolada_max_mes(df, date(2026, 9, 1), PREFIJO) is None


def test_rolante_de_instantanea_coincide_con_media_de_tres():
    """Sanity: la columna DEM_15min del combinado es media de 3 kW instantáneos."""
    kw = pd.Series([6636.77, 7886.63, 8078.65])
    mes = pd.Series(["2026-09"] * 3)
    dem = demanda_rodante_15min_por_mes(kw, mes)
    assert dem.iloc[0] == 0.0
    assert dem.iloc[1] == 0.0
    assert abs(float(dem.iloc[2]) - (6636.77 + 7886.63 + 8078.65) / 3) < 1e-6
