"""Reglas de generación del catálogo: granja + FV y varios tipo 5."""

from __future__ import annotations

import pytest

from bess.config.catalog import CatalogError, catalogo_desde_filas

TIPOS = [
    {"Tipo": "1", "Descripcion": "Neteo", "Neteo": "1", "Invertir": "0", "Reactivos": "1"},
    {"Tipo": "2", "Descripcion": "Consumo", "Neteo": "0", "Invertir": "1", "Reactivos": "2"},
    {"Tipo": "3", "Descripcion": "BESS", "Neteo": "0", "Invertir": "0", "Reactivos": "0"},
    {"Tipo": "4", "Descripcion": "GeneracionMultiple", "Neteo": "0", "Invertir": "0", "Reactivos": "0"},
    {"Tipo": "5", "Descripcion": "GeneracionIndividual", "Neteo": "0", "Invertir": "0", "Reactivos": "0"},
]


def _sub(numero: int, nombre: str, generacion: int, tarifa: str = "DIST"):
    return {
        "Numero": str(numero),
        "Nombre": nombre,
        "Generacion": str(generacion),
        "Esquema_Tarifa": tarifa,
    }


def _med(
    nombre: str,
    sub: int,
    tipo: int,
    *,
    descarga: str = "API",
    serie: str = "S1",
    ip: str = "0",
    grupo: str = "",
):
    return {
        "Nombre": nombre,
        "Numero_Serie": serie,
        "Subestacion": str(sub),
        "Tipo_Medidor": str(tipo),
        "Descarga": descarga,
        "IP": ip,
        "Puerto": "502" if descarga == "ION" else "0",
        "Grupo_Generacion": grupo,
        "Validado": "",
    }


def _ok(subs, meds):
    catalogo_desde_filas(TIPOS, subs, meds)


def _errores(subs, meds) -> list[str]:
    with pytest.raises(CatalogError) as exc:
        catalogo_desde_filas(TIPOS, subs, meds)
    return list(exc.value.errores)


def test_iusa1_varios_tipo5_con_cogen_y_azotea():
    subs = [_sub(1, "IUSA_1", 2)]
    meds = [
        _med("ION_Testigo_IUSA1", 1, 1, descarga="ION", serie="M_T", ip="172.16.1.1"),
        _med("BESS_NORTE", 1, 3),
        _med("Cogeneracion", 1, 5, serie="CS1305"),
        _med("FV BESS Norte", 1, 5, serie="CS3754"),
        _med("FV Corporativo", 1, 5, serie="CYM601"),
        _med("FV IUSASOL Planta", 1, 5, serie="SAI0402"),
    ]
    _ok(subs, meds)


def test_iusa2_granja_tipo4_con_fv_tipo5():
    subs = [_sub(2, "IUSA_2", 1)]
    meds = [
        _med("ION_TESTIGO_IUSA2", 2, 1, descarga="ION", serie="M_T2", ip="172.16.1.2"),
        _med("BESS_SUR", 2, 3),
        _med("Mega01", 2, 4, serie="CYM769", grupo="Generacion_IUSA_2"),
        _med("FV BESS Sur", 2, 5, serie="CYM293"),
        _med("FV CDPT", 2, 5, serie="CYM443"),
    ]
    _ok(subs, meds)


def test_generacion2_sin_tipo5_sigue_invalido():
    subs = [_sub(1, "IUSA_1", 2)]
    meds = [
        _med("ION", 1, 1, descarga="ION", serie="M", ip="10.0.0.1"),
        _med("BESS", 1, 3),
    ]
    msgs = _errores(subs, meds)
    assert any("requiere al menos 1 medidor tipo 5" in m for m in msgs)


def test_generacion1_sin_tipo4_sigue_invalido():
    subs = [_sub(2, "IUSA_2", 1)]
    meds = [
        _med("ION", 2, 1, descarga="ION", serie="M", ip="10.0.0.2"),
        _med("BESS", 2, 3),
        _med("FV", 2, 5, serie="FV1"),
    ]
    msgs = _errores(subs, meds)
    assert any("requiere medidores tipo 4" in m for m in msgs)


def test_generacion0_no_admite_tipo5():
    subs = [_sub(1, "SOLO_BESS", 0)]
    meds = [
        _med("ION", 1, 1, descarga="ION", serie="M", ip="10.0.0.3"),
        _med("BESS", 1, 3),
        _med("FV", 1, 5, serie="FV1"),
    ]
    msgs = _errores(subs, meds)
    assert any("Generacion=0" in m for m in msgs)
