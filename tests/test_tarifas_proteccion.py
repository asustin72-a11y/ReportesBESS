"""Protección de tarifas ya cargadas frente a sync parcial / ceros."""

from __future__ import annotations

from bess.data.ingest.cfe.tarifas_client import ResultadoTarifaCFE
from bess.data.tariffs_db import fusionar_preferir_positivo


def _resultado(**kwargs) -> ResultadoTarifaCFE:
    base = dict(
        esquema_id="DIST",
        anio=2026,
        mes=9,
        estado="",
        municipio="",
        division="",
        url="",
        cargos={},
    )
    base.update(kwargs)
    return ResultadoTarifaCFE(**base)


def _base_con_agosto() -> dict[str, dict[int, float]]:
    return {
        "Base": {m: 0.0 for m in range(1, 13)} | {7: 1.0511, 8: 1.0400},
        "Intermedio": {m: 0.0 for m in range(1, 13)} | {7: 1.7287, 8: 1.7100},
        "Punta": {m: 0.0 for m in range(1, 13)} | {7: 2.0184, 8: 2.0000},
        "Capacidad": {m: 0.0 for m in range(1, 13)} | {7: 386.37, 8: 380.0},
        "CargoFijo": {m: 793.13 for m in range(1, 13)},
    }


def test_fusionar_cero_no_pisa_positivo():
    csv = {"Base": {8: 0.0, 9: 1.0511}}
    bd = {"Base": {8: 1.04, 9: 0.0}}
    out = fusionar_preferir_positivo(csv, bd)
    assert out["Base"][8] == 1.04
    assert out["Base"][9] == 1.0511


def test_a_matriz_mes_sync_septiembre_conserva_agosto():
    base = _base_con_agosto()
    resultado = _resultado(
        mes=9,
        cargos={
            "Base": 1.0511,
            "Intermedio": 1.7288,
            "Punta": 2.0184,
            "Capacidad": 386.38,
            "CargoFijo": 793.13,
        },
    )
    matriz = fusionar_preferir_positivo(base, resultado.a_matriz_mes(base))
    assert matriz["Base"][8] == 1.0400
    assert matriz["Base"][9] == 1.0511
    assert matriz["Capacidad"][8] == 380.0


def test_a_matriz_mes_rechaza_cargo_cero_sobre_existente():
    base = _base_con_agosto()
    resultado = _resultado(
        mes=8,
        cargos={
            "Base": 0.0,
            "Intermedio": 0.0,
            "Punta": 0.0,
            "Capacidad": 0.0,
            "CargoFijo": 793.13,
        },
    )
    matriz = resultado.a_matriz_mes(base)
    assert matriz["Base"][8] == 1.0400
    assert matriz["CargoFijo"][8] == 793.13


def test_publicado_exige_energia_no_solo_cargo_fijo():
    solo_fijo = _resultado(
        cargos={"CargoFijo": 793.13, "Suministro": 793.13},
    )
    assert solo_fijo.publicado() is False

    con_energia = _resultado(cargos={"CargoFijo": 793.13, "Base": 1.05})
    assert con_energia.publicado() is True
