"""Varios medidores tipo 5 (Generacion=2): catálogo, recursos y diario sumado."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from bess.config.catalog import (
    GENERACION_GRUPO,
    GENERACION_INDIVIDUAL,
    TIPO_BESS,
    TIPO_FACTURACION,
    TIPO_GENERACION_INDIVIDUAL,
    TIPO_GENERACION_MULTIPLE,
    Catalogo,
    MedidorCatalogo,
    ReglasTipoMedidor,
    SubestacionCatalogo,
    _validar_reglas_negocio,
)
from bess.config.subestaciones import (
    MedidorGeneracionIndividual,
    RecursoGeneracion,
    Subestacion,
    recursos_generacion_subestacion,
)
from bess.data.aggregates.granja import consolidar_energia_generacion_subestacion


def _cat_base(tipo5_nombres: list[str]) -> Catalogo:
    tipos = (
        ReglasTipoMedidor(1, "Fact", True, False, 0),
        ReglasTipoMedidor(3, "BESS", False, False, 0),
        ReglasTipoMedidor(5, "GenInd", False, False, 0),
    )
    subs = (
        SubestacionCatalogo(
            numero=1,
            nombre="IUSA_1",
            generacion=GENERACION_INDIVIDUAL,
            esquema_tarifa="DIST",
        ),
    )
    validado = datetime(2026, 1, 1, 0, 0)
    meds = [
        MedidorCatalogo(
            nombre="ION_Testigo_IUSA1",
            numero_serie="S1",
            subestacion_numero=1,
            subestacion_nombre="IUSA_1",
            tipo_medidor=TIPO_FACTURACION,
            descarga="ION",
            ip="172.16.0.1",
            puerto=502,
            grupo_generacion="",
            validado=validado,
        ),
        MedidorCatalogo(
            nombre="BESS_NORTE",
            numero_serie="B1",
            subestacion_numero=1,
            subestacion_nombre="IUSA_1",
            tipo_medidor=TIPO_BESS,
            descarga="API",
            ip="0",
            puerto=0,
            grupo_generacion="",
            validado=validado,
        ),
    ]
    for nombre in tipo5_nombres:
        meds.append(
            MedidorCatalogo(
                nombre=nombre,
                numero_serie=f"SER-{nombre}",
                subestacion_numero=1,
                subestacion_nombre="IUSA_1",
                tipo_medidor=TIPO_GENERACION_INDIVIDUAL,
                descarga="API",
                ip="0",
                puerto=0,
                grupo_generacion="",
                validado=validado,
            )
        )
    return Catalogo(tipos=tipos, subestaciones=subs, medidores=tuple(meds))


def test_catalogo_permite_dos_tipo5_en_generacion_2():
    cat = _cat_base(["Cogeneracion", "Generacion_Solar_IUSA1"])
    assert _validar_reglas_negocio(cat) == []


def test_catalogo_exige_al_menos_un_tipo5_en_generacion_2():
    cat = _cat_base([])
    errores = _validar_reglas_negocio(cat)
    assert any("al menos" in e.lower() or "requiere" in e.lower() for e in errores)


def test_catalogo_generacion_1_admite_tipo5_ademas_del_grupo():
    tipos = (
        ReglasTipoMedidor(1, "Fact", True, False, 0),
        ReglasTipoMedidor(3, "BESS", False, False, 0),
        ReglasTipoMedidor(4, "GenMult", False, False, 0),
        ReglasTipoMedidor(5, "GenInd", False, False, 0),
    )
    subs = (
        SubestacionCatalogo(
            numero=2,
            nombre="IUSA_2",
            generacion=GENERACION_GRUPO,
            esquema_tarifa="DIST",
        ),
    )
    validado = datetime(2026, 1, 1, 0, 0)
    meds = (
        MedidorCatalogo(
            nombre="ION_TESTIGO_IUSA2",
            numero_serie="S2",
            subestacion_numero=2,
            subestacion_nombre="IUSA_2",
            tipo_medidor=TIPO_FACTURACION,
            descarga="ION",
            ip="172.16.0.2",
            puerto=502,
            grupo_generacion="",
            validado=validado,
        ),
        MedidorCatalogo(
            nombre="BESS_SUR",
            numero_serie="B2",
            subestacion_numero=2,
            subestacion_nombre="IUSA_2",
            tipo_medidor=TIPO_BESS,
            descarga="API",
            ip="0",
            puerto=0,
            grupo_generacion="",
            validado=validado,
        ),
        MedidorCatalogo(
            nombre="Mega01",
            numero_serie="M1",
            subestacion_numero=2,
            subestacion_nombre="IUSA_2",
            tipo_medidor=TIPO_GENERACION_MULTIPLE,
            descarga="API",
            ip="0",
            puerto=0,
            grupo_generacion="Generacion_IUSA_2",
            validado=validado,
        ),
        MedidorCatalogo(
            nombre="GenExtra_IUSA2",
            numero_serie="GX",
            subestacion_numero=2,
            subestacion_nombre="IUSA_2",
            tipo_medidor=TIPO_GENERACION_INDIVIDUAL,
            descarga="API",
            ip="0",
            puerto=0,
            grupo_generacion="",
            validado=validado,
        ),
    )
    cat = Catalogo(tipos=tipos, subestaciones=subs, medidores=meds)
    assert _validar_reglas_negocio(cat) == []


def test_recursos_generacion_lista_todos_tipo5(monkeypatch):
    gen = (
        MedidorGeneracionIndividual(
            nombre="Cogeneracion",
            csv="Cogeneracion.csv",
            filtrado="Cogeneracion_Filtrado.csv",
        ),
        MedidorGeneracionIndividual(
            nombre="Generacion_Solar_IUSA1",
            csv="Generacion_Solar_IUSA1.csv",
            filtrado="Generacion_Solar_IUSA1_Filtrado.csv",
        ),
    )
    sub = Subestacion(
        id="IUSA_1",
        nombre="Subestación IUSA 1",
        medidores_consumo=(),
        bess_csv="BESS_IUSA_1.csv",
        bess_filtrado="BESS_IUSA_1_Filtrado.csv",
        bess_bd="BESS_IUSA_1",
        cogeneracion_csv=gen[0].csv,
        cogeneracion_filtrado=gen[0].filtrado,
        cogeneracion_nombre=gen[0].nombre,
        medidores_gen_individual=gen,
    )

    import bess.config.subestaciones as subestaciones_mod

    monkeypatch.setattr(
        subestaciones_mod,
        "subestacion_por_id",
        lambda sub_id: sub if sub_id == "IUSA_1" else None,
    )
    recursos = recursos_generacion_subestacion("IUSA_1")
    assert len(recursos) == 2
    assert {r.prefijo_reporte for r in recursos} == {
        "Cogeneracion",
        "Generacion_Solar_IUSA1",
    }
    assert all(r.columna_kwh == "KWH_ENT" for r in recursos)
    assert all(isinstance(r, RecursoGeneracion) for r in recursos)


def test_consolidar_diario_suma_sin_pisar(tmp_path, monkeypatch):
    import bess.config.rutas as rutas_mod

    monkeypatch.setattr(rutas_mod, "DIRECTORIO_REPORTES", tmp_path)
    sub = "IUSA_1"
    (tmp_path / sub).mkdir(parents=True)

    def _escribir(prefijo: str, filas: list[tuple[str, float, float, float]]):
        ruta = rutas_mod.ruta_energia_por_dia(prefijo, sub)
        pd.DataFrame(
            {
                "FECHA": [f[0] for f in filas],
                "BASE_REC": [f[1] for f in filas],
                "INTERMEDIO_REC": [f[2] for f in filas],
                "PUNTA_REC": [f[3] for f in filas],
            }
        ).to_csv(ruta, index=False)

    _escribir("Cogeneracion", [("01/08/2026", 10.0, 5.0, 1.0)])
    _escribir("Generacion_Solar_IUSA1", [("01/08/2026", 20.0, 0.0, 2.0)])

    n = consolidar_energia_generacion_subestacion(
        sub, ["Cogeneracion", "Generacion_Solar_IUSA1"]
    )
    assert n == 1
    out = pd.read_csv(tmp_path / sub / "ENERGIA_Generacion_IUSA_1_POR_DIA.csv")
    assert float(out.loc[0, "BASE_REC"]) == 30.0
    assert float(out.loc[0, "INTERMEDIO_REC"]) == 5.0
    assert float(out.loc[0, "PUNTA_REC"]) == 3.0
    assert Path(rutas_mod.ruta_energia_por_dia("Cogeneracion", sub)).exists()
    assert Path(rutas_mod.ruta_energia_por_dia("Generacion_Solar_IUSA1", sub)).exists()
