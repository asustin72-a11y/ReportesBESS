"""Tests: sync_log API/Granja, divergencia de cursores."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from bess.data.ingest.ion import db
from bess.data.sync_cursor import (
    alinear_cursores_a_bd,
    divergencias_cursores,
    guardar_ultima_fecha,
)


ZONA = ZoneInfo("America/Mexico_City")


def _fila(fecha: str, rec: float = 1.0) -> dict:
    return {
        "fecha": fecha,
        "kwh_rec": rec,
        "kwh_ent": 0.0,
        "kvarh_q1": 0.0,
        "kvarh_q2": 0.0,
        "kvarh_q3": 0.0,
        "kvarh_q4": 0.0,
    }


def test_divergencias_cursores_detecta_csv_atras(tmp_path):
    ruta_bd = tmp_path / "perfiles.db"
    ruta_csv = tmp_path / "Ultima_Sincronizacion.csv"
    medidor = "BESS_ARAGON"
    db.init_db(ruta_bd)

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor, [_fila("2026-07-10 12:00:00", 2.0)], fuente="iusasol"
        )
        db.actualizar_sync_state(conn, medidor, "2026-07-10 12:00:00")
        conn.commit()

    guardar_ultima_fecha(medidor, "2026-07-08 00:00:00", ruta_csv)

    divs = divergencias_cursores(ruta_bd=ruta_bd, ruta_csv=ruta_csv)
    assert any(d["medidor_id"] == medidor for d in divs)
    fila = next(d for d in divs if d["medidor_id"] == medidor)
    assert "atrás" in fila["motivo"] or "atras" in fila["motivo"].lower()


def test_alinear_cursores_a_bd(tmp_path):
    ruta_bd = tmp_path / "perfiles.db"
    ruta_csv = tmp_path / "Ultima_Sincronizacion.csv"
    medidor = "BESS_ARAGON"
    db.init_db(ruta_bd)

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor, [_fila("2026-07-12 15:00:00", 3.0)], fuente="csv"
        )
        conn.commit()

    guardar_ultima_fecha(medidor, "2026-07-01 00:00:00", ruta_csv)
    hechos = alinear_cursores_a_bd([medidor], ruta_bd=ruta_bd, ruta_csv=ruta_csv)
    assert len(hechos) == 1
    assert hechos[0]["cursor"].startswith("2026-07-12")

    divs = divergencias_cursores(ruta_bd=ruta_bd, ruta_csv=ruta_csv)
    assert not any(d["medidor_id"] == medidor for d in divs)


def test_sync_api_escribe_sync_log_ok(tmp_path, monkeypatch):
    from bess.data.ingest.iusasol import sync_db as mod

    ruta_bd = tmp_path / "perfiles.db"
    db.init_db(ruta_bd)
    medidor = "BESS_ARAGON"

    # Rango forzado: evita "sin rango pendiente"
    df = pd.DataFrame(
        {
            "Fecha": [pd.Timestamp("2026-07-08 12:00:00")],
            "KWH_REC": [1.0],
            "KWH_ENT": [0.0],
            "KVARH_Q1": [0.0],
            "KVARH_Q2": [0.0],
            "KVARH_Q3": [0.0],
            "KVARH_Q4": [0.0],
        }
    )

    client = MagicMock()
    client.listar_medidores.return_value = [{"idcode": "1", "name": medidor}]
    client.obtener_perfil.return_value = {}

    monkeypatch.setattr(mod, "cargar_config_iusasol", lambda: MagicMock(tym=1, tye=1))
    monkeypatch.setattr(mod, "resolver_id_medidor", lambda *a, **k: "1")
    monkeypatch.setattr(mod, "perfil_json_a_dataframe", lambda p: df)
    monkeypatch.setattr(mod, "rellenar_slots_medianoche_api", lambda d, **k: d)
    monkeypatch.setattr(mod, "contexto_previo_bd", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_recortar_slots_futuros", lambda d, ahora: d)
    monkeypatch.setattr(mod, "persistir_slots_medianoche_bd", lambda *a, **k: 0)
    monkeypatch.setattr(mod, "registrar_exito_sync", lambda *a, **k: "2026-07-08 12:00:00")
    monkeypatch.setattr(
        mod,
        "_calcular_rango_fechas",
        lambda *a, **k: ("2026-07-08", "2026-07-08"),
    )
    monkeypatch.setattr(mod, "_sin_rango_api", lambda *a, **k: False)
    monkeypatch.setattr(mod, "_ultima_fecha_bd", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_resolver_medidor_bd", lambda m: medidor)

    resultado = mod.sincronizar_medidor_api(
        medidor,
        ruta_bd=ruta_bd,
        desde="2026-07-08",
        hasta="2026-07-08",
        client=client,
        quiet=True,
    )
    assert resultado["mensaje"] == "OK"

    with db.conectar_bd(ruta_bd) as conn:
        row = conn.execute(
            "SELECT status, medidor_id, registros_leidos FROM sync_log "
            "WHERE medidor_id = ? ORDER BY id DESC LIMIT 1",
            (medidor,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "ok"
    assert int(row["registros_leidos"]) == 1


def test_sync_api_escribe_sync_log_error(tmp_path, monkeypatch):
    from bess.data.ingest.iusasol import sync_db as mod
    from bess.data.ingest.iusasol.client import IusasolError

    ruta_bd = tmp_path / "perfiles.db"
    db.init_db(ruta_bd)
    medidor = "BESS_ARAGON"

    client = MagicMock()
    client.listar_medidores.side_effect = IusasolError("fallo API")

    monkeypatch.setattr(mod, "cargar_config_iusasol", lambda: MagicMock(tym=1, tye=1))
    monkeypatch.setattr(mod, "_calcular_rango_fechas", lambda *a, **k: ("2026-07-08", "2026-07-08"))
    monkeypatch.setattr(mod, "_sin_rango_api", lambda *a, **k: False)
    monkeypatch.setattr(mod, "_ultima_fecha_bd", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_resolver_medidor_bd", lambda m: medidor)

    with pytest.raises(IusasolError):
        mod.sincronizar_medidor_api(
            medidor,
            ruta_bd=ruta_bd,
            desde="2026-07-08",
            hasta="2026-07-08",
            client=client,
            quiet=True,
        )

    with db.conectar_bd(ruta_bd) as conn:
        row = conn.execute(
            "SELECT status, error_message FROM sync_log "
            "WHERE medidor_id = ? ORDER BY id DESC LIMIT 1",
            (medidor,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "error"
    assert "fallo API" in (row["error_message"] or "")
