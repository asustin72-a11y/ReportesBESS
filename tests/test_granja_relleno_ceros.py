"""Pruebas de _escribir_combinado_minuto() (bess/data/aggregates/granja.py)
-- complementa tests/test_granja_incremental.py, centradas en el bug de
relleno de ceros encontrado en producción con GENERACION_ARAGON.

Bug real: la escritura incremental del combinado de generación/cogeneración
solo anexaba filas con FECHA_HORA estrictamente posterior al cursor (última
fila ya escrita). Eso se rompe cuando la fuente (API ISOL) rellena el día
completo con ceros por adelantado y los va reemplazando con datos reales
conforme pasan las horas: la última fila ya escrita podía ser un cero de
relleno de una hora futura (p.ej. 19:10) mientras llegaban datos reales
para horas anteriores a esa pero posteriores a la corrida previa (p.ej.
08:20-12:00). Como esas fechas no eran "más nuevas" que el cursor, nunca
se anexaban -- el archivo se quedaba con el cero de relleno para siempre
en vez del dato real, sin importar cuántas veces se volviera a correr
Reportes (confirmado en producción: Filtrado ya llevaba hasta las 12:00,
el combinado seguía topado en 08:20 tras varias corridas de Reportes).

El arreglo: en vez de anexar solo lo estrictamente nuevo, reescribe una
ventana de los últimos _MARGEN_REEXPORTAR_DIAS días (mismo mecanismo que
combined.py ya usa para el lado de consumo), permitiendo que un dato real
sustituya a un cero de relleno ya escrito.
"""

from __future__ import annotations

import pandas as pd

from bess.data.aggregates.granja import _COLUMNAS_MIN_GRANJA, _escribir_combinado_minuto


def _escribir_csv(ruta, filas):
    """filas: lista de (FECHA, FECHA_HORA, KWH_REC)."""
    df = pd.DataFrame(filas, columns=_COLUMNAS_MIN_GRANJA)
    df.to_csv(ruta, index=False)


def _leer_csv(ruta):
    return pd.read_csv(ruta)


def test_corrige_ceros_de_relleno_cuando_llega_dato_real_posterior(tmp_path):
    """Reproduce el bug real de GENERACION_ARAGON: el archivo ya escrito
    tiene ceros de relleno en las últimas filas (cursor = última fila,
    un cero); la corrida actual trae datos reales para esas mismas fechas
    -- deben sustituir a los ceros, no quedar descartados."""
    ruta = tmp_path / "COMBINADO_POR_MINUTO_GENERACION_TEST.csv"
    _escribir_csv(ruta, [
        ("01/06/2026", "01/06/2026 00:05", 2.0),
        ("01/06/2026", "01/06/2026 00:10", 3.0),
        ("01/06/2026", "01/06/2026 00:15", 0.0),  # relleno viejo
        ("01/06/2026", "01/06/2026 00:20", 0.0),  # relleno viejo -- cursor
    ])

    df_min_out = pd.DataFrame(
        [
            ("01/06/2026", "01/06/2026 00:05", 2.0),
            ("01/06/2026", "01/06/2026 00:10", 3.0),
            ("01/06/2026", "01/06/2026 00:15", 5.5),   # dato real llegó
            ("01/06/2026", "01/06/2026 00:20", 6.1),   # dato real llegó (era el cursor)
            ("01/06/2026", "01/06/2026 00:25", 7.2),   # fila nueva de verdad
        ],
        columns=_COLUMNAS_MIN_GRANJA,
    )
    escritas = _escribir_combinado_minuto(df_min_out, str(ruta))
    assert escritas == 5

    resultado = _leer_csv(ruta)
    assert list(resultado["KWH_REC"]) == [2.0, 3.0, 5.5, 6.1, 7.2]
    assert len(resultado) == 5  # sin duplicar filas


def test_preserva_dias_anteriores_fuera_de_la_ventana(tmp_path):
    """Un día completo, ya cerrado, anterior a la ventana de reescritura
    (_MARGEN_REEXPORTAR_DIAS=1 día antes del cursor) debe conservarse tal
    cual -- no se reprocesa ni se pierde."""
    ruta = tmp_path / "COMBINADO_POR_MINUTO_GENERACION_TEST.csv"
    _escribir_csv(ruta, [
        ("29/05/2026", "29/05/2026 23:55", 9.9),           # día cerrado, fuera de ventana
        ("01/06/2026", "01/06/2026 00:05", 2.0),
        ("01/06/2026", "01/06/2026 00:10", 0.0),            # relleno viejo dentro de ventana
    ])

    df_min_out = pd.DataFrame(
        [
            ("29/05/2026", "29/05/2026 23:55", 9.9),
            ("01/06/2026", "01/06/2026 00:05", 2.0),
            ("01/06/2026", "01/06/2026 00:10", 4.4),        # dato real reemplaza al relleno
        ],
        columns=_COLUMNAS_MIN_GRANJA,
    )
    escritas = _escribir_combinado_minuto(df_min_out, str(ruta))
    assert escritas == 2  # solo la ventana (01/06); el día previo se preserva crudo

    resultado = _leer_csv(ruta)
    assert len(resultado) == 3
    assert resultado.iloc[0]["FECHA_HORA"] == "29/05/2026 23:55"
    assert resultado.iloc[0]["KWH_REC"] == 9.9
    assert resultado.iloc[-1]["KWH_REC"] == 4.4


def test_sin_filas_en_ventana_no_modifica_archivo(tmp_path):
    """Si la corrida actual no trae nada dentro de la ventana (p.ej. un
    reintento sin datos nuevos de la fuente), el archivo no debe tocarse."""
    ruta = tmp_path / "COMBINADO_POR_MINUTO_GENERACION_TEST.csv"
    _escribir_csv(ruta, [
        ("01/06/2026", "01/06/2026 00:05", 2.0),
        ("01/06/2026", "01/06/2026 00:10", 3.0),
    ])
    antes = ruta.read_bytes()

    # df_min_out muy anterior a la ventana (más de 1 día antes del cursor).
    df_min_out = pd.DataFrame(
        [("20/05/2026", "20/05/2026 00:05", 1.0)],
        columns=_COLUMNAS_MIN_GRANJA,
    )
    escritas = _escribir_combinado_minuto(df_min_out, str(ruta))
    assert escritas == 0
    assert ruta.read_bytes() == antes


def test_cambio_de_columnas_cae_a_modo_completo(tmp_path):
    """Si el archivo existente tiene un formato de columnas distinto al
    esperado, se recalcula y reescribe completo en vez de intentar una
    ventana incremental sobre un formato que no coincide."""
    ruta = tmp_path / "COMBINADO_POR_MINUTO_GENERACION_TEST.csv"
    pd.DataFrame(
        [("01/06/2026", "01/06/2026 00:05", 2.0, "extra")],
        columns=["FECHA", "FECHA_HORA", "KWH_REC", "OTRA_COLUMNA"],
    ).to_csv(ruta, index=False)

    df_min_out = pd.DataFrame(
        [
            ("01/06/2026", "01/06/2026 00:05", 9.0),
            ("01/06/2026", "01/06/2026 00:10", 9.5),
        ],
        columns=_COLUMNAS_MIN_GRANJA,
    )
    escritas = _escribir_combinado_minuto(df_min_out, str(ruta))
    assert escritas == 2

    resultado = _leer_csv(ruta)
    assert list(resultado.columns) == _COLUMNAS_MIN_GRANJA
    assert list(resultado["KWH_REC"]) == [9.0, 9.5]
