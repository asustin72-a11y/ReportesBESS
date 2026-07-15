"""Pruebas de db.upsert_registros() y la protección `no_degradar_a_ceros`.

Bug encontrado en producción: iusasol/sync_db.py, granja/sync_db.py e
ion/sync.py llamaban a upsert_registros() sin `no_degradar_a_ceros=True`.
Un lote entero en cero devuelto por una falla transitoria de la API o una
lectura Modbus con glitch de comunicación pisaba silenciosamente lecturas
reales ya guardadas de una corrida anterior -- pasó en producción con
Cogeneracion, GENERACION_ARAGON y Generacion_IUSA_2 el mismo día que se
detectó el bug.

El arreglo: con `no_degradar_a_ceros=True`, un registro entrante que llega
completamente en cero se descarta si la fila ya existente para esa fecha
tiene energía real -- sin importar la `fuente` de ninguno de los dos lados
(a diferencia de `respetar_fuente`, que sí distingue por fuente). Estas
pruebas cubren ese comportamiento y confirman que sin el flag (el default)
el comportamiento viejo -- sobrescribir siempre -- no cambió.
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


def test_no_degradar_a_ceros_descarta_lote_en_cero_sobre_dato_real(tmp_path):
    """Un valor real ya guardado (p.ej. de un sync API anterior) no debe
    perderse si una corrida posterior trae un lote todo en cero por una
    falla transitoria propia de la API."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:50:00', kwh_rec=422.68)],
            fuente='iusasol',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:50:00', kwh_rec=0.0)],
            fuente='iusasol', no_degradar_a_ceros=True,
        )
        conn.commit()

    assert resultado.insertados == 0
    assert resultado.actualizados == 0
    fila = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:50:00')
    assert fila['kwh_rec'] == 422.68


def test_no_degradar_a_ceros_permite_lote_en_cero_si_no_habia_dato_previo(tmp_path):
    """Si no hay fila previa (o la previa también era cero), un lote en cero
    sí debe poder insertarse/actualizarse -- no hay nada real que proteger."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:50:00', kwh_rec=0.0)],
            fuente='iusasol', no_degradar_a_ceros=True,
        )
        conn.commit()

    assert resultado.insertados == 1
    fila = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:50:00')
    assert fila['kwh_rec'] == 0.0


def test_no_degradar_a_ceros_permite_lote_con_energia_real(tmp_path):
    """Un lote entrante que sí trae energía real siempre debe aplicarse,
    aunque el valor previo también fuera real (comportamiento normal de
    actualización, sin relación con la protección de ceros)."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:50:00', kwh_rec=422.68)],
            fuente='iusasol',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:50:00', kwh_rec=430.0)],
            fuente='iusasol', no_degradar_a_ceros=True,
        )
        conn.commit()

    assert resultado.actualizados == 1
    fila = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:50:00')
    assert fila['kwh_rec'] == 430.0


def test_no_degradar_a_ceros_lote_mixto_descarta_solo_las_que_degradan(tmp_path):
    """Un lote con varias fechas: las que degradarían un valor real a cero
    se descartan, el resto del lote se aplica normalmente -- igual que hace
    ion/sync.py y iusasol/sync_db.py al guardar por lotes."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id,
            [
                _fila('2026-07-15 12:50:00', kwh_rec=422.68),
                _fila('2026-07-15 12:55:00', kwh_rec=0.0),
            ],
            fuente='iusasol',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id,
            [
                _fila('2026-07-15 12:50:00', kwh_rec=0.0),    # degradaría, se descarta
                _fila('2026-07-15 12:55:00', kwh_rec=426.63),  # sube de cero a real, se aplica
                _fila('2026-07-15 13:00:00', kwh_rec=430.0),   # fila nueva, se aplica
            ],
            fuente='iusasol', no_degradar_a_ceros=True,
        )
        conn.commit()

    f1250 = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:50:00')
    f1255 = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:55:00')
    f1300 = _leer_fila(ruta_bd, medidor_id, '2026-07-15 13:00:00')

    assert f1250['kwh_rec'] == 422.68  # protegido
    assert f1255['kwh_rec'] == 426.63  # actualizado
    assert f1300['kwh_rec'] == 430.0   # insertado
    assert resultado.insertados == 1
    assert resultado.actualizados == 1


def test_sin_no_degradar_a_ceros_sobrescribe_igual_que_antes(tmp_path):
    """Sin el flag (default False), el comportamiento viejo no cambió: un
    lote en cero sí pisa un valor real -- confirma que el fix es opt-in y no
    rompe ningún llamador que todavía no lo use."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_BANCO

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:50:00', kwh_rec=422.68)],
            fuente='iusasol',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:50:00', kwh_rec=0.0)],
            fuente='iusasol',
        )
        conn.commit()

    assert resultado.actualizados == 1
    fila = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:50:00')
    assert fila['kwh_rec'] == 0.0


def test_no_degradar_a_ceros_y_respetar_fuente_combinados(tmp_path):
    """ion/sync.py usa ambos flags juntos para MEDIDOR_ION: respetar_fuente
    protege correcciones CSV con energía real, no_degradar_a_ceros protege
    cualquier dato real (de cualquier fuente) contra un lote Modbus en
    cero. Deben poder combinarse sin interferir entre sí."""
    ruta_bd = tmp_path / 'perfiles.db'
    db.init_db(ruta_bd)
    medidor_id = db.MEDIDOR_ION

    with db.conectar_bd(ruta_bd) as conn:
        db.upsert_registros(
            conn, medidor_id,
            [
                _fila('2026-07-15 12:15:00', kwh_rec=680.8),  # csv, energía real
                _fila('2026-07-15 12:20:00', kwh_rec=1167.9),  # modbus, energía real
            ],
            fuente='csv',
        )
        conn.commit()
        db.upsert_registros(
            conn, medidor_id, [_fila('2026-07-15 12:20:00', kwh_rec=1167.9)],
            fuente='modbus',
        )
        conn.commit()

    with db.conectar_bd(ruta_bd) as conn:
        resultado = db.upsert_registros(
            conn, medidor_id,
            [
                _fila('2026-07-15 12:15:00', kwh_rec=0.0),  # glitch modbus en cero
                _fila('2026-07-15 12:20:00', kwh_rec=0.0),  # glitch modbus en cero
            ],
            fuente='modbus', respetar_fuente='csv', no_degradar_a_ceros=True,
        )
        conn.commit()

    assert resultado.insertados == 0
    assert resultado.actualizados == 0
    f1215 = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:15:00')
    f1220 = _leer_fila(ruta_bd, medidor_id, '2026-07-15 12:20:00')
    assert f1215['kwh_rec'] == 680.8 and f1215['fuente'] == 'csv'
    assert f1220['kwh_rec'] == 1167.9 and f1220['fuente'] == 'modbus'
