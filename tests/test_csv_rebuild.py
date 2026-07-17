"""Tests del plan de rebuild CSV forzado (sin tocar BD ni archivos reales)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bess.config.catalog import TIPO_BESS
from bess.data.csv_rebuild import plan_rebuild_csv


def test_plan_rebuild_bess_aragon_incluye_cadena():
    fake_fuente = Path("data/ArchivosFuente/IUSA_ARAGON/BESS_ARAGON.csv")
    med = MagicMock()
    med.subestacion_nombre = "IUSA_ARAGON"
    med.tipo_medidor = TIPO_BESS

    cat = MagicMock()
    cat.medidor_por_nombre.return_value = med

    consumo = MagicMock()
    consumo.ruta_combinado.return_value = Path("data/ArchivosReporte/IUSA_ARAGON/COMBINADO.csv")
    consumo.ruta_energia_dia.return_value = Path("data/ArchivosReporte/IUSA_ARAGON/ENERGIA.csv")
    consumo.ruta_acumulados.return_value = Path("data/ArchivosReporte/IUSA_ARAGON/ACUM.csv")

    sub = MagicMock()
    sub.ruta_bess.side_effect = lambda filtrado=False: Path(
        f"data/ArchivosProcesados/IUSA_ARAGON/BESS_IUSA_ARAGON{'_Filtrado' if filtrado else ''}.csv"
    )
    sub.medidores_consumo = [consumo]

    with (
        patch("bess.data.csv_rebuild.obtener_catalogo", return_value=cat),
        patch("bess.data.csv_rebuild._destino_fuente", return_value=fake_fuente),
        patch("bess.data.csv_rebuild.subestacion_por_id", return_value=sub),
        patch(
            "bess.data.csv_rebuild.rutas_mod.ruta_procesado_medidor",
            side_effect=lambda nombre, sub_id, filtrado=False: Path(
                f"data/ArchivosProcesados/{sub_id}/{nombre}"
                f"{'_Filtrado' if filtrado else ''}.csv"
            ),
        ),
        patch(
            "bess.data.csv_rebuild.rutas_mod.ruta_energia_bess_por_dia",
            return_value=Path(
                "data/ArchivosReporte/IUSA_ARAGON/ENERGIA_BESS_IUSA_ARAGON_POR_DIA.csv"
            ),
        ),
    ):
        plan = plan_rebuild_csv("BESS_ARAGON", "2026-05-01")

    assert plan.medidor_id == "BESS_ARAGON"
    assert plan.subestacion_id == "IUSA_ARAGON"
    assert plan.desde == "2026-05-01"
    assert plan.ruta_fuente == fake_fuente
    textos = [str(p).replace("\\", "/") for p in plan.archivos_a_borrar]
    assert any("BESS_ARAGON" in t for t in textos)
    assert any("BESS_IUSA_ARAGON" in t for t in textos)
    assert any("ENERGIA_BESS_IUSA_ARAGON_POR_DIA" in t for t in textos)
    assert any("COMBINADO" in t for t in textos)
    assert any("solo lectura" in a.lower() or "sqlite" in a.lower() for a in plan.avisos)
