"""Tests de reconciliación SQLite ↔ ArchivosFuente."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from bess.data.ingest.ion import db
from bess.data.reconcile_csv import reconciliar_medidor, resumen_por_medidor


def _fila(fecha: str, rec: float, ent: float = 0.0) -> dict:
    return {
        "fecha": fecha,
        "kwh_rec": rec,
        "kwh_ent": ent,
        "kvarh_q1": 0.0,
        "kvarh_q2": 0.0,
        "kvarh_q3": 0.0,
        "kvarh_q4": 0.0,
    }


def test_detecta_dia_con_energia_en_bd_faltante_en_fuente(tmp_path):
    ruta_bd = tmp_path / "perfiles.db"
    ruta_csv = tmp_path / "BESS_ARAGON.csv"
    medidor = "BESS_ARAGON"
    db.init_db(ruta_bd)

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn,
            medidor,
            [
                _fila("2026-07-08 12:00:00", 1.0),
                _fila("2026-07-08 12:05:00", 1.5),
                _fila("2026-07-09 12:00:00", 2.0),
            ],
            fuente="iusasol",
        )
        conn.commit()

    # Fuente solo tiene el día 9 (8 ausente → divergencia tipo Aragón)
    ruta_csv.write_text(
        "Fecha,KWH_REC,KWH_ENT,KVARH_Q1,KVARH_Q2,KVARH_Q3,KVARH_Q4\n"
        "2026-07-09 12:00:00,2.0,0,0,0,0,0\n",
        encoding="utf-8-sig",
    )

    divs = reconciliar_medidor(
        medidor,
        ruta_csv,
        desde=date(2026, 7, 8),
        hasta=date(2026, 7, 9),
        ruta_bd=ruta_bd,
    )
    assert len(divs) == 1
    assert divs[0].dia == date(2026, 7, 8)
    assert divs[0].motivo == "faltan en Fuente"
    assert abs(divs[0].sum_rec_bd - 2.5) < 0.01
    assert divs[0].filas_csv == 0

    resumen = resumen_por_medidor(divs)
    assert resumen[0]["dias_divergentes"] == 1
    assert resumen[0]["medidor_id"] == medidor


def test_detecta_suma_distinta(tmp_path):
    ruta_bd = tmp_path / "perfiles.db"
    ruta_csv = tmp_path / "BESS_ARAGON.csv"
    medidor = "BESS_ARAGON"
    db.init_db(ruta_bd)

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor, [_fila("2026-07-10 10:00:00", 5.0)], fuente="csv"
        )
        conn.commit()

    ruta_csv.write_text(
        "Fecha,KWH_REC,KWH_ENT,KVARH_Q1,KVARH_Q2,KVARH_Q3,KVARH_Q4\n"
        "2026-07-10 10:00:00,0.0,0,0,0,0,0\n",
        encoding="utf-8-sig",
    )

    divs = reconciliar_medidor(
        medidor,
        ruta_csv,
        desde=date(2026, 7, 10),
        hasta=date(2026, 7, 10),
        ruta_bd=ruta_bd,
    )
    assert len(divs) == 1
    assert divs[0].motivo == "suma kWh distinta"
    assert abs(divs[0].delta_rec - 5.0) < 0.01


def test_sin_divergencia_si_coinciden(tmp_path):
    ruta_bd = tmp_path / "perfiles.db"
    ruta_csv = tmp_path / "BESS_ARAGON.csv"
    medidor = "BESS_ARAGON"
    db.init_db(ruta_bd)

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor, [_fila("2026-07-11 10:00:00", 3.25)], fuente="iusasol"
        )
        conn.commit()

    ruta_csv.write_text(
        "Fecha,KWH_REC,KWH_ENT,KVARH_Q1,KVARH_Q2,KVARH_Q3,KVARH_Q4\n"
        "2026-07-11 10:00:00,3.25,0,0,0,0,0\n",
        encoding="utf-8-sig",
    )

    divs = reconciliar_medidor(
        medidor,
        ruta_csv,
        desde=date(2026, 7, 11),
        hasta=date(2026, 7, 11),
        ruta_bd=ruta_bd,
    )
    assert divs == []
