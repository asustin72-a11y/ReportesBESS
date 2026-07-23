"""Parser de líneas BESS_UI_PROGRESS (tabs o espacios)."""

from __future__ import annotations

from bess.core.ui_progress import es_linea_progreso_ui, parse_ui_progress


def test_parse_con_tabs() -> None:
    p = parse_ui_progress("BESS_UI_PROGRESS\t3\t6\tBESS y medidores (API → SQLite)")
    assert p == (3, 6, "BESS y medidores (API → SQLite)")


def test_parse_con_espacios() -> None:
    p = parse_ui_progress("BESS_UI_PROGRESS 3 6 BESS y medidores")
    assert p == (3, 6, "BESS y medidores")


def test_es_linea_progreso() -> None:
    assert es_linea_progreso_ui("BESS_UI_PROGRESS 0")
    assert es_linea_progreso_ui("BESS_UI_PROGRESS\t1\t6\tx")
    assert not es_linea_progreso_ui("ERROR API: timeout")
