"""Cursor de COMBINADO_POR_MINUTO: debe leer FECHA_HORA (2ª col), no FECHA."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bess.data.aggregates.combined import ultima_fecha_hora_escrita


def _escribir_combinado(ruta: Path, filas: list[tuple[str, str, float]]) -> None:
    """Escribe un COMBINADO estilo generación: FECHA, FECHA_HORA, KWH_REC."""
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        fh.write("FECHA,FECHA_HORA,KWH_REC\n")
        for fecha, fecha_hora, kwh in filas:
            fh.write(f"{fecha},{fecha_hora},{kwh}\n")


def test_cursor_usa_fecha_hora_no_fecha(tmp_path):
    ruta = tmp_path / "COMBINADO_POR_MINUTO_GENERACION_ARAGON.csv"
    _escribir_combinado(
        ruta,
        [
            ("11/08/2026", "11/08/2026 11:15", 1.0),
            ("12/08/2026", "12/08/2026 08:15", 2.0),
        ],
    )
    ts = ultima_fecha_hora_escrita(ruta)
    assert ts == pd.Timestamp("2026-08-12 08:15:00")


def test_cursor_no_usa_fragmento_de_cola_a_mitad_de_linea(tmp_path):
    """Archivo grande: la cola de 8 KiB empieza a mitad de línea.

    Antes, si el fragmento empezaba con FECHA_HORA (dígito), no se descartaba
    y el aviso de desfase podía quedar congelado en una hora vieja aunque
    las últimas filas ya estuvieran al día.
    """
    ruta = tmp_path / "COMBINADO_POR_MINUTO_X.csv"
    # Relleno para superar los 8 KiB de cola que lee el cursor.
    relleno = [("10/08/2026", f"10/08/2026 {h:02d}:{m:02d}", 0.1)
               for h in range(24) for m in range(0, 60, 5)]
    # Una fila "vieja" en medio del buffer de cola + filas recientes al final.
    filas = relleno + [
        ("11/08/2026", "11/08/2026 11:15", 1.0),
        ("12/08/2026", "12/08/2026 07:55", 1.5),
        ("12/08/2026", "12/08/2026 08:00", 1.6),
        ("12/08/2026", "12/08/2026 08:05", 1.7),
        ("12/08/2026", "12/08/2026 08:10", 1.8),
        ("12/08/2026", "12/08/2026 08:15", 2.0),
    ]
    _escribir_combinado(ruta, filas)
    assert ruta.stat().st_size > 8192

    ts = ultima_fecha_hora_escrita(ruta)
    assert ts == pd.Timestamp("2026-08-12 08:15:00")
