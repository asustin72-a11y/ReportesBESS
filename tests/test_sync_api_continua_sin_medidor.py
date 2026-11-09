"""Un medidor ausente en la API no detiene la descarga de los demás."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from bess.data.ingest.iusasol.client import IusasolError


def test_sincronizar_api_sigue_si_un_medidor_no_esta(monkeypatch):
    from bess.data.ingest.iusasol import sync_db as mod

    medidores = [
        SimpleNamespace(nombre="BESS_ARAGON", numero_serie="CS1991"),
        SimpleNamespace(nombre="BESS_NORTE", numero_serie="CS3878"),
        SimpleNamespace(nombre="BESS_SUR", numero_serie="CS3190"),
    ]
    llamados: list[str] = []

    def _sync(nombre, **kwargs):
        llamados.append(nombre)
        if nombre == "BESS_ARAGON":
            raise ValueError('No se encontró idcode para "BESS_ARAGON"')
        if nombre == "BESS_NORTE":
            raise IusasolError("perfil no disponible")
        return {
            "medidor": nombre,
            "leidos": 4,
            "insertados": 4,
            "actualizados": 0,
            "mensaje": "OK",
        }

    monkeypatch.setattr(mod, "cargar_config_iusasol", lambda: MagicMock())
    monkeypatch.setattr(mod, "IusasolClient", lambda cfg: MagicMock())
    monkeypatch.setattr(mod, "medidores_sync_api_isol", lambda: medidores)
    monkeypatch.setattr(mod, "sincronizar_medidor_api", _sync)

    resumen = mod.sincronizar_api(quiet=True)

    assert llamados == ["BESS_ARAGON", "BESS_NORTE", "BESS_SUR"]
    assert resumen[0]["medidor"] == "BESS_ARAGON"
    assert "idcode" in resumen[0]["error"]
    assert resumen[1]["medidor"] == "BESS_NORTE"
    assert "perfil no disponible" in resumen[1]["error"]
    assert resumen[2]["mensaje"] == "OK"
    assert resumen[2]["leidos"] == 4
