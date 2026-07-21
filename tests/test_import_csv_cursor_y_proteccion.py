"""Import CSV → BD: cursor alineado y protección frente al día completo de la API."""

from __future__ import annotations

from pathlib import Path

from bess.data.ingest.ion import db
from bess.data.ingest.ion.import_csv import importar_csv
from bess.data.sync_cursor import leer_mapa, leer_ultima_fecha


def _escribir_csv(ruta: Path, filas: list[tuple[str, float, float]]) -> None:
    lineas = ["Fecha,KWH_REC,KWH_ENT,KVARH_Q1,KVARH_Q2,KVARH_Q3,KVARH_Q4"]
    for fecha, rec, ent in filas:
        lineas.append(f"{fecha},{rec},{ent},0,0,0,0")
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8-sig")


def _fila_bd(ruta_bd: Path, medidor_id: str, fecha: str):
    with db.conectar_bd(ruta_bd) as conn:
        return conn.execute(
            "SELECT * FROM perfil_carga WHERE medidor_id = ? AND fecha = ?",
            (medidor_id, fecha),
        ).fetchone()


def test_importar_csv_conserva_primer_registro_aunque_no_sea_0005(tmp_path):
    """No se omite 00:00 ni ningún otro primer registro del día."""
    ruta_bd = tmp_path / "perfiles.db"
    ruta_csv = tmp_path / "BESS_ARAGON.csv"
    medidor_id = "BESS_ARAGON"
    db.init_db(ruta_bd)
    _escribir_csv(
        ruta_csv,
        [
            ("2026-07-08 00:00:00", 0.1, 0.0),
            ("2026-07-08 00:05:00", 0.2, 0.0),
            ("2026-07-09 00:00:00", 0.3, 0.0),
            ("2026-07-09 00:05:00", 0.4, 0.0),
        ],
    )

    codigo = importar_csv(ruta_csv, ruta_bd, medidor_id)
    assert codigo == 0

    with db.conectar_bd(ruta_bd) as conn:
        total = db.contar_registros(conn, medidor_id)
    assert total == 4
    assert _fila_bd(ruta_bd, medidor_id, "2026-07-08 00:00:00") is not None
    assert float(_fila_bd(ruta_bd, medidor_id, "2026-07-08 00:00:00")["kwh_rec"]) == 0.1
    assert _fila_bd(ruta_bd, medidor_id, "2026-07-09 00:00:00") is not None


def test_importar_csv_alinea_cursor_y_marca_fuente_csv(tmp_path, monkeypatch):
    """Tras import OK: sync_state + Ultima_Sincronizacion = MAX(fecha), fuente=csv."""
    ruta_bd = tmp_path / "perfiles.db"
    ruta_cursor = tmp_path / "Ultima_Sincronizacion.csv"
    ruta_csv = tmp_path / "BESS_ARAGON.csv"
    medidor_id = "BESS_ARAGON"
    fecha = "2026-07-08 12:00:00"

    _escribir_csv(ruta_csv, [(fecha, 1.25, 0.5)])
    db.init_db(ruta_bd)

    monkeypatch.setattr(
        "bess.data.sync_cursor.RUTA_ULTIMA_SINCRONIZACION",
        ruta_cursor,
    )
    # importar_csv llama registrar_exito_sync sin ruta_csv; resuelve el Path
    # del módulo sync_cursor en tiempo de ejecución (default None → constante).

    codigo = importar_csv(
        ruta_csv,
        ruta_bd,
        medidor_id,
    )
    assert codigo == 0

    fila = _fila_bd(ruta_bd, medidor_id, fecha)
    assert fila is not None
    assert fila["fuente"] == "csv"
    assert float(fila["kwh_rec"]) == 1.25

    with db.conectar_bd(ruta_bd) as conn:
        estado = conn.execute(
            "SELECT ultima_fecha FROM sync_state WHERE medidor_id = ?",
            (medidor_id,),
        ).fetchone()
    assert estado is not None
    assert estado["ultima_fecha"] == fecha

    assert ruta_cursor.is_file()
    assert leer_ultima_fecha(medidor_id, ruta_cursor) == fecha
    assert medidor_id in leer_mapa(ruta_cursor)


def test_sync_api_no_pisa_import_csv_con_energia(tmp_path):
    """La API trae el día completo; filas csv con energía no se sobrescriben."""
    ruta_bd = tmp_path / "perfiles.db"
    medidor_id = "BESS_ARAGON"
    fecha = "2026-07-08 12:05:00"
    db.init_db(ruta_bd)

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn,
            medidor_id,
            [
                {
                    "fecha": fecha,
                    "kwh_rec": 5.9,
                    "kwh_ent": 0.0,
                    "kvarh_q1": 0.0,
                    "kvarh_q2": 0.0,
                    "kvarh_q3": 0.0,
                    "kvarh_q4": 0.0,
                }
            ],
            fuente="csv",
        )
        conn.commit()

    # Simula lo que hace iusasol/sync_db: día completo con ceros / otros valores
    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn,
            medidor_id,
            [
                {
                    "fecha": fecha,
                    "kwh_rec": 0.0,
                    "kwh_ent": 0.0,
                    "kvarh_q1": 0.0,
                    "kvarh_q2": 0.0,
                    "kvarh_q3": 0.0,
                    "kvarh_q4": 0.0,
                },
                {
                    "fecha": "2026-07-08 12:10:00",
                    "kwh_rec": 0.1,
                    "kwh_ent": 0.0,
                    "kvarh_q1": 0.0,
                    "kvarh_q2": 0.0,
                    "kvarh_q3": 0.0,
                    "kvarh_q4": 0.0,
                },
            ],
            fuente="iusasol",
            respetar_fuente="csv",
            no_degradar_a_ceros=True,
        )
        conn.commit()

    assert resultado.actualizados == 0  # la fila csv no se actualiza
    assert resultado.insertados == 1  # el slot nuevo sí entra

    fila_csv = _fila_bd(ruta_bd, medidor_id, fecha)
    assert float(fila_csv["kwh_rec"]) == 5.9
    assert fila_csv["fuente"] == "csv"

    fila_nueva = _fila_bd(ruta_bd, medidor_id, "2026-07-08 12:10:00")
    assert float(fila_nueva["kwh_rec"]) == 0.1
    assert fila_nueva["fuente"] == "iusasol"


def test_sync_api_puede_corregir_fila_csv_en_cero(tmp_path):
    """Filas csv en cero (relleno) sí pueden ser completadas por la API."""
    ruta_bd = tmp_path / "perfiles.db"
    medidor_id = "BESS_ARAGON"
    fecha = "2026-07-09 10:00:00"
    db.init_db(ruta_bd)

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn,
            medidor_id,
            [
                {
                    "fecha": fecha,
                    "kwh_rec": 0.0,
                    "kwh_ent": 0.0,
                    "kvarh_q1": 0.0,
                    "kvarh_q2": 0.0,
                    "kvarh_q3": 0.0,
                    "kvarh_q4": 0.0,
                }
            ],
            fuente="csv",
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn,
            medidor_id,
            [
                {
                    "fecha": fecha,
                    "kwh_rec": 2.4,
                    "kwh_ent": 0.0,
                    "kvarh_q1": 0.0,
                    "kvarh_q2": 0.0,
                    "kvarh_q3": 0.0,
                    "kvarh_q4": 0.0,
                }
            ],
            fuente="iusasol",
            respetar_fuente="csv",
            no_degradar_a_ceros=True,
        )
        conn.commit()

    fila = _fila_bd(ruta_bd, medidor_id, fecha)
    assert float(fila["kwh_rec"]) == 2.4
    assert fila["fuente"] == "iusasol"
