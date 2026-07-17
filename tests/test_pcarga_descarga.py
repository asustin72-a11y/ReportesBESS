"""Tests de conversión pcarga → CSV importable (sin medidor físico)."""

from __future__ import annotations

import io

from bess.config.pcarga_endpoints import ENDPOINTS_PCARGA, endpoint_pcarga
from bess.data.ingest.pcarga.descarga import convertir_pcarga_a_import, wh_a_kwh


def test_wh_a_kwh_con_ke():
    assert wh_a_kwh(1000, 7200) == 7200.0
    assert wh_a_kwh(500, 1) == 0.5


def test_endpoints_cinco_medidores():
    assert set(ENDPOINTS_PCARGA) == {
        "Banco_1",
        "BESS_NORTE",
        "Cogeneracion",
        "BESS_SUR",
        "BESS_ARAGON",
    }
    assert endpoint_pcarga("BESS_SUR").puerto == 5
    assert endpoint_pcarga("BESS_ARAGON").ya_escalado is True
    assert endpoint_pcarga("Cogeneracion").ke_efectivo == 1.0
    assert endpoint_pcarga("Banco_1").ke_efectivo == 18400.0


def test_convertir_omite_invalidos_y_aplica_ke():
    crudo = io.StringIO(
        "valido,verano,fecha,hora,KWH_REC,KWH_ENT,KVARH_Q1,KVARH_Q2,KVARH_Q3,KVARH_Q4\n"
        "1,0,2026-07-16,19:00:00,10,2,1,0,0,0\n"
        "0,0,2026-07-16,19:05:00,99,99,0,0,0,0\n"
        "1,0,2026-07-16,19:10:00,5,0,0,0,0,0\n"
    )
    txt, n, omitidos = convertir_pcarga_a_import(crudo, ke=7200)
    assert n == 2
    assert omitidos == 1
    lineas = [ln for ln in txt.strip().splitlines() if ln]
    assert lineas[0].startswith("Fecha,")
    # 10 Wh * 7200 / 1000 = 72 kWh
    assert "2026-07-16 19:00:00,72.000000," in lineas[1]
    assert "2026-07-16 19:10:00,36.000000," in lineas[2]
