"""Pruebas del plan de rebuild total desde BD."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from bess.data.csv_rebuild import plan_rebuild_csv_todos


def test_plan_rebuild_csv_todos_estructura(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bess.data.csv_rebuild.destinos_export_bd",
        lambda _bd=None: [
            ("Cogeneracion", tmp_path / "Cogeneracion.csv"),
            ("GeneracionNorte", tmp_path / "GeneracionNorte.csv"),
        ],
    )
    monkeypatch.setattr(
        "bess.data.csv_rebuild._listar_csv_derivados_globales",
        lambda: [tmp_path / "ArchivosReporte" / "x.csv"],
    )
    plan = plan_rebuild_csv_todos(date(2026, 5, 1))
    assert plan["desde"] == "2026-05-01"
    assert plan["n_medidores"] == 2
    assert "Cogeneracion" in plan["medidores"]
    assert plan["n_csv_derivados_a_borrar"] == 1
    assert any("todos" in a.lower() or "TODOS" in a for a in plan["avisos"]) or len(
        plan["avisos"]
    ) >= 3


def test_rebuild_todos_emite_progreso(tmp_path, monkeypatch):
    from bess.data import csv_rebuild

    monkeypatch.setattr(
        csv_rebuild,
        "destinos_export_bd",
        lambda _bd=None: [("MedA", tmp_path / "MedA.csv")],
    )
    monkeypatch.setattr(csv_rebuild, "exportar", lambda *a, **k: 0)
    monkeypatch.setattr(csv_rebuild, "_listar_csv_derivados_globales", lambda: [])

    eventos: list[tuple[int, int, str]] = []

    def _on(step, total, label):
        eventos.append((step, total, label))

    resultado = csv_rebuild.ejecutar_rebuild_csv_todos(
        date(2026, 5, 1),
        procesar=False,
        on_progress=_on,
    )
    assert resultado["ok"] is True
    assert eventos[0][0] == 0
    assert any("Exportando MedA" in e[2] for e in eventos)
    assert any("Borrando" in e[2] for e in eventos)
    assert eventos[-1][0] == eventos[-1][1]
