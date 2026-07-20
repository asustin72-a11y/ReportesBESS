"""Orquestador fallback pcarga IUSA 1/2 (mocks, sin medidor físico)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bess.config.pcarga_endpoints import (
    MEDIDORES_FALLBACK_IUSA12,
    lista_medidores_fallback_iusa12,
)
from bess.data.ingest.pcarga import fallback as fb


def test_lista_fallback_sin_aragon():
    ids = lista_medidores_fallback_iusa12()
    assert ids == list(MEDIDORES_FALLBACK_IUSA12)
    assert "BESS_ARAGON" not in ids
    assert set(ids) == {"Banco_1", "BESS_NORTE", "Cogeneracion", "BESS_SUR"}


def test_fallback_lote_parcial_no_aborta(monkeypatch):
    @dataclass
    class FakeDesc:
        ok: bool
        medidor_id: str
        registros: int = 10
        omitidos_invalidos: int = 0
        ke_aplicado: float = 1.0
        ya_escalado: bool = True
        csv_bytes: bytes = b"Fecha,KWH_REC\n"
        nombre_archivo: str = "x.csv"
        log: str = "ok"
        serie_leida: str = "CS"
        ruta_crudo: str = ""

    calls: list[str] = []

    def fake_descarga(medidor_id, desde, hasta):
        calls.append(medidor_id)
        if medidor_id == "BESS_SUR":
            return FakeDesc(ok=False, medidor_id=medidor_id, registros=0, log="timeout")
        return FakeDesc(ok=True, medidor_id=medidor_id)

    def fake_import(csv_bytes, medidor_id, nombre):
        return 0, "import ok"

    def fake_rebuild(medidor_id, desde, *, procesar=False):
        return {"ok": True, "log": "rebuild ok"}

    monkeypatch.setattr(
        "bess.data.ingest.pcarga.descarga.descargar_pcarga_medidor",
        fake_descarga,
    )
    monkeypatch.setattr(fb, "_importar_bytes", fake_import)
    monkeypatch.setattr(
        "bess.data.csv_rebuild.ejecutar_rebuild_csv",
        fake_rebuild,
    )

    lote = fb.ejecutar_fallback_pcarga_iusa12(
        desde=datetime(2026, 7, 20, 8, 0),
        hasta=datetime(2026, 7, 20, 11, 0),
        rebuild=True,
        procesar=False,
    )
    assert len(lote.medidores) == 4
    assert lote.exitosos == 3
    assert lote.fallidos == 1
    assert lote.ok is False
    sur = next(m for m in lote.medidores if m.medidor_id == "BESS_SUR")
    assert sur.ok is False
    assert sur.etapa == "descarga"
    assert set(calls) == set(MEDIDORES_FALLBACK_IUSA12)
