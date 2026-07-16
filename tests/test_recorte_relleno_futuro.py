"""Pruebas de _recortar_slots_futuros() (iusasol/sync_db.py) y
_recortar_registros_futuros() (granja/sync_db.py).

Causa raiz de fondo (a diferencia del arreglo anterior en granja.py, que
corregia el cursor incremental del reporte ya generado): la API ISOL, al
pedir el dia en curso, regresa el dia completo relleno con ceros por
adelantado para los slots que todavia no ocurren en tiempo real. Ese
relleno se guardaba tal cual en SQLite (perfil_carga) porque nada lo
filtraba antes de insertar, dejando sync_state "sincronizado" hasta una
hora futura -- confirmado en produccion con Cogeneracion.csv y
GENERACION_ARAGON.csv (datos reales hasta la hora real del sync, luego
ceros escritos hasta 23:55 del mismo dia). Eso disparaba avisos falsos de
"reporte desactualizado" (bess/ui/pipeline_status.py) todos los dias,
porque la comparacion contra sync_state nunca podia alcanzar una hora que
en realidad era solo relleno.

El arreglo: descartar esas filas futuras antes de guardar nada en SQLite,
en el punto de entrada de cada sync (API IUSASOL y API Farm/granja).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from bess.data.ingest.granja.sync_db import _recortar_registros_futuros
from bess.data.ingest.iusasol.sync_db import _recortar_slots_futuros


def _df(fechas: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Fecha": pd.to_datetime(fechas),
            "KWH_REC": [1.0] * len(fechas),
            "KWH_ENT": [0.0] * len(fechas),
            "KVARH_Q1": [0.0] * len(fechas),
            "KVARH_Q2": [0.0] * len(fechas),
            "KVARH_Q3": [0.0] * len(fechas),
            "KVARH_Q4": [0.0] * len(fechas),
        }
    )


def test_recortar_slots_futuros_descarta_posteriores_a_ahora():
    """Reproduce el caso real: filas reales hasta las 12:15, luego ceros
    de relleno hasta las 23:55 -- deben descartarse todas las filas
    posteriores a la hora real del sync."""
    df = _df(
        [
            "2026-07-16 12:05:00",
            "2026-07-16 12:10:00",
            "2026-07-16 12:15:00",
            "2026-07-16 12:20:00",  # relleno futuro
            "2026-07-16 23:55:00",  # relleno futuro
        ]
    )
    ahora = datetime(2026, 7, 16, 12, 17, 0)
    resultado = _recortar_slots_futuros(df, ahora)
    assert list(resultado["Fecha"].dt.strftime("%Y-%m-%d %H:%M:%S")) == [
        "2026-07-16 12:05:00",
        "2026-07-16 12:10:00",
        "2026-07-16 12:15:00",
    ]


def test_recortar_slots_futuros_conserva_fila_exactamente_en_ahora():
    df = _df(["2026-07-16 12:15:00"])
    ahora = datetime(2026, 7, 16, 12, 15, 0)
    resultado = _recortar_slots_futuros(df, ahora)
    assert len(resultado) == 1


def test_recortar_slots_futuros_conserva_ceros_reales_pasados():
    """No debe filtrar por valor -- un cero real de la noche (pasado) se
    conserva; solo se descarta por estar en el futuro respecto a `ahora`."""
    df = _df(["2026-07-16 02:00:00", "2026-07-16 12:20:00"])
    df.loc[0, "KWH_REC"] = 0.0  # cero real nocturno, no relleno
    ahora = datetime(2026, 7, 16, 12, 17, 0)
    resultado = _recortar_slots_futuros(df, ahora)
    assert len(resultado) == 1
    assert resultado.iloc[0]["Fecha"] == pd.Timestamp("2026-07-16 02:00:00")


def test_recortar_slots_futuros_df_vacio_no_falla():
    df = _df([])
    resultado = _recortar_slots_futuros(df, datetime(2026, 7, 16, 12, 0, 0))
    assert resultado.empty


def test_recortar_registros_futuros_granja():
    registros = [
        {"fecha": "2026-07-16 12:05:00", "kwh_rec": 3.0},
        {"fecha": "2026-07-16 12:10:00", "kwh_rec": 4.0},
        {"fecha": "2026-07-16 12:15:00", "kwh_rec": 0.0},  # relleno futuro
        {"fecha": "2026-07-17 00:00:00", "kwh_rec": 0.0},  # relleno futuro (dia siguiente)
    ]
    resultado = _recortar_registros_futuros(registros, "2026-07-16 12:12:00")
    assert [r["fecha"] for r in resultado] == [
        "2026-07-16 12:05:00",
        "2026-07-16 12:10:00",
    ]


def test_recortar_registros_futuros_sin_registros_futuros_no_cambia_nada():
    registros = [{"fecha": "2026-07-16 08:00:00", "kwh_rec": 1.0}]
    resultado = _recortar_registros_futuros(registros, "2026-07-16 12:00:00")
    assert resultado == registros
