"""Pruebas de db.upsert_registros() y la protección `respetar_fuente`.

`sync_db.py` llama a upsert_registros(..., fuente='iusasol',
respetar_fuente='csv') en cada sincronización con la API, para que una
corrección manual importada por CSV (p.ej. para arreglar un tramo con datos
malos del medidor) no se pierda si la API vuelve a sincronizar y sigue
reportando el valor viejo/incorrecto.

Bug encontrado en producción: esa protección era ciega a cualquier fila con
`fuente='csv'`, incluyendo las que solo son relleno en cero de un import
masivo (p.ej. restaurar un respaldo de perfil_carga que trae el día en
curso prellenado con ceros, igual que hace la API antes de completarlo con
valores reales). Con eso, ninguna sincronización posterior con la API podía
corregir esas horas -- el día se quedaba pegado en cero para siempre, sin
importar cuántas veces se sincronizara.

El arreglo: `respetar_fuente` solo protege filas que además tienen energía
real (no son puro cero). Estas pruebas cubren ambos casos y confirman que
el comportamiento sin `respetar_fuente` no cambió.
"""

from __future__ import annotations

from bess.data.ingest.ion import db


def _fila(fecha: str, kwh_rec: float = 0.0, kwh_ent: float = 0.0) -> dict:
    return {
        'fecha': fecha,
        'kwh_rec': kwh_rec,
        'kwh_ent': kwh_ent,
        'kvarh_q1': 0.0,
        'kvarh_q2': 0.0,
        'kvarh_q3': 0.0,
        'kvarh_q4': 0.0,
    }


def _leer_fila(ruta_bd, medidor_id, fecha):
    with db.conectar_bd(ruta_bd) as conn:
        return conn.execute(
            'SELECT * FROM perfil_carga WHERE medidor_id = ? AND fecha = ?',
            (medidor_id, fecha),
        ).fetchone()


def test_respetar_fuente_protege_fila_csv_con_energia_real(tmp_path):
    """Una corrección manual real (fuente=csv, valor distinto de cero) no
    debe perderse si la API vuelve a sincronizar con un valor distinto."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:20:00', kwh_rec=999.0)],
            fuente='csv',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:20:00', kwh_rec=5.0)],
            fuente='iusasol', respetar_fuente='csv',
        )
        conn.commit()

    assert resultado.insertados == 0
    assert resultado.actualizados == 0
    fila = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:20:00')
    assert fila['kwh_rec'] == 999.0
    assert fila['fuente'] == 'csv'


def test_respetar_fuente_no_protege_fila_csv_en_cero(tmp_path):
    """Una fila fuente=csv que es solo relleno en cero (p.ej. de un import
    masivo de respaldo) SÍ debe poder actualizarse con el valor real que
    trae la API -- de lo contrario el día en curso queda pegado en cero
    para siempre."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:20:00', kwh_rec=0.0)],
            fuente='csv',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:20:00', kwh_rec=680.8)],
            fuente='iusasol', respetar_fuente='csv',
        )
        conn.commit()

    assert resultado.actualizados == 1
    fila = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:20:00')
    assert fila['kwh_rec'] == 680.8
    assert fila['fuente'] == 'iusasol'


def test_respetar_fuente_lote_mixto_protege_solo_las_no_cero(tmp_path):
    """Un lote con varias fechas: las que tenían energía real en csv se
    conservan, las que eran puro relleno en cero se actualizan -- ambas en
    la misma llamada."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id,
            [
                _fila('2026-07-15 12:15:00', kwh_rec=680.8),
                _fila('2026-07-15 12:20:00', kwh_rec=0.0),
                _fila('2026-07-15 12:25:00', kwh_rec=0.0),
            ],
            fuente='csv',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id,
            [
                _fila('2026-07-15 12:15:00', kwh_rec=1.0),  # protegida, no debe cambiar
                _fila('2026-07-15 12:20:00', kwh_rec=644.0),  # debe actualizarse
                _fila('2026-07-15 12:25:00', kwh_rec=662.4),  # debe actualizarse
            ],
            fuente='iusasol', respetar_fuente='csv',
        )
        conn.commit()

    f1215 = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:15:00')
    f1220 = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:20:00')
    f1225 = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:25:00')

    assert f1215['kwh_rec'] == 680.8 and f1215['fuente'] == 'csv'
    assert f1220['kwh_rec'] == 644.0 and f1220['fuente'] == 'iusasol'
    assert f1225['kwh_rec'] == 662.4 and f1225['fuente'] == 'iusasol'


def test_sin_respetar_fuente_siempre_sobrescribe(tmp_path):
    """Sin `respetar_fuente`, el comportamiento de upsert no cambia: la
    fuente csv (con o sin energía) se sobrescribe igual que antes."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:20:00', kwh_rec=999.0)],
            fuente='csv',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:20:00', kwh_rec=5.0)],
            fuente='iusasol',
        )
        conn.commit()

    assert resultado.actualizados == 1
    fila = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:20:00')
    assert fila['kwh_rec'] == 5.0
    assert fila['fuente'] == 'iusasol'
