"""Descarga de reportes del catálogo: solo CSV/PDF dentro de las carpetas permitidas."""

from __future__ import annotations

from pathlib import Path

import pytest

from bess.ui.catalog_admin.reportes_descarga import leer_reporte, listar_reportes


def _raices(tmp_path: Path) -> tuple[tuple[str, Path], ...]:
    reportes = tmp_path / "ArchivosReporte"
    pdfs = tmp_path / "ReportesDiarios"
    (reportes / "IUSA_1").mkdir(parents=True)
    (pdfs / "IUSA_1").mkdir(parents=True)
    return (("Reportes CSV", reportes), ("PDF diarios", pdfs))


def test_lista_csv_y_pdf_y_omite_temporales(tmp_path: Path):
    raices = _raices(tmp_path)
    reportes = raices[0][1]
    csv = reportes / "IUSA_1" / "COMBINADO_POR_MINUTO_FV BESS Norte.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    (reportes / "IUSA_1" / ".tmp_algo.csv").write_text("x", encoding="utf-8")
    (reportes / "IUSA_1" / "corte.part").write_text("x", encoding="utf-8")
    pdf = raices[1][1] / "IUSA_1" / "dia.pdf"
    pdf.write_bytes(b"%PDF")

    nombres = {r.nombre for r in listar_reportes(raices)}
    assert nombres == {"COMBINADO_POR_MINUTO_FV BESS Norte.csv", "dia.pdf"}
    combinado = next(r for r in listar_reportes(raices) if r.nombre.endswith(".csv"))
    assert combinado.subestacion == "IUSA_1"
    assert combinado.origen == "Reportes CSV"


def test_lee_el_archivo_con_espacios(tmp_path: Path):
    raices = _raices(tmp_path)
    csv = raices[0][1] / "IUSA_1" / "COMBINADO_POR_MINUTO_FV BESS Norte.csv"
    csv.write_bytes(b"fecha,kwh\n")
    assert leer_reporte(csv, raices) == b"fecha,kwh\n"


def test_rechaza_ruta_fuera_de_reportes(tmp_path: Path):
    raices = _raices(tmp_path)
    ajeno = tmp_path / "secreto.csv"
    ajeno.write_text("no", encoding="utf-8")
    with pytest.raises(ValueError, match="fuera de los reportes"):
        leer_reporte(ajeno, raices)
