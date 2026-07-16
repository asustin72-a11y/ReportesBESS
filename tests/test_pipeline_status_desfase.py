"""Pruebas de evaluar_desfase_reportes()/render_aviso_reporte_desactualizado()
(bess/ui/pipeline_status.py).

Motivo: el usuario reporto (segunda vez) que, al abrir la app, el reporte
mostrado tenia datos solo hasta el 13/07 pese a que la sincronizacion ya
habia avanzado hasta el 15/07. La sync_log confirmo que la sincronizacion
(fuente -> SQLite) nunca retrocede -- es puramente incremental --, asi que
el hueco real esta en que Verificar/Filtrar/Reportes es un paso manual
separado que puede quedarse atras del sync sin ningun aviso en la UI
(p. ej. si el reporte se regenero justo tras restaurar un respaldo, antes
de que el sync se pusiera al dia, y no se volvio a regenerar despues).

Estas pruebas cubren evaluar_desfase_reportes() con subestaciones/medidores
falsos (sin tocar SQLite ni CSV reales) y render_aviso_reporte_desactualizado()
capturando la llamada a st.warning().

Tambien cubren la extension posterior: el aviso original solo revisaba el
reporte de consumo (medidor de facturacion) de cada subestacion. Caso real
que se escapo por eso: GENERACION_ARAGON con su Filtrado al corriente
(11:25) pero su combinado congelado varias horas atras (08:20) -- el aviso
no decia nada porque nunca miraba ese archivo. Ahora evaluar_desfase_reportes()
tambien revisa el reporte de generacion (granja o cogeneracion/individual)
de cada subestacion, via bess.config.subestaciones.recurso_generacion_subestacion.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

import bess.ui.pipeline_status as pipeline_status
from bess.config import rutas as rutas_mod


@dataclass(frozen=True)
class _ResumenMedidorFalso:
    """Mismos campos que bess.ui.db_tools.service.ResumenMedidor -- se
    define localmente (en vez de importar la clase real) para que esta
    prueba no dispare, ni siquiera al recolectar el modulo, la carga del
    catalogo real (bess.data.ingest.ion.db importa medidor_ids ->
    obtener_catalogo() -> abre RUTA_BD_PERFILES). evaluar_desfase_reportes()
    solo usa duck typing (.medidor_id/.ultima_sync), no isinstance."""

    medidor_id: str
    registros: int
    fecha_min: str | None
    fecha_max: str | None
    ultima_sync: str | None
    ultima_sync_ok: str | None


@dataclass(frozen=True)
class _MedidorFalso:
    nombre: str
    ruta: str

    def ruta_combinado(self) -> str:
        return self.ruta


@dataclass(frozen=True)
class _SubestacionFalsa:
    id: str
    nombre: str
    medidor_facturacion: _MedidorFalso


@dataclass(frozen=True)
class _RecursoGeneracionFalso:
    """Mismos campos usados de bess.config.subestaciones.RecursoGeneracion
    (solo prefijo_reporte -- lo unico que usa evaluar_desfase_reportes())."""

    prefijo_reporte: str


def _preparar(monkeypatch, subs, resumen_por_id, reporte_por_ruta, generacion_por_sub=None):
    """subs: lista de _SubestacionFalsa.
    resumen_por_id: {medidor_id: _ResumenMedidorFalso} (puede omitir medidores).
    reporte_por_ruta: {ruta: pd.Timestamp | None}.
    generacion_por_sub: {sub_id: _RecursoGeneracionFalso | None} -- subestaciones
    omitidas se tratan como sin recurso de generacion (comportamiento por
    defecto: solo se evalua el reporte de consumo, igual que antes de esta
    extension).

    evaluar_desfase_reportes() hace "from bess.ui.db_tools.service import
    resumen_medidores" y "from bess.data.aggregates.combined import
    ultima_fecha_hora_escrita" DENTRO de la funcion (import perezoso, a
    proposito, para que importar bess.ui.pipeline_status no dependa de
    SQLite). bess.ui.db_tools.service importa a su vez, a nivel de modulo,
    bess.data.ingest.ion.db -- que construye el catalogo real desde
    RUTA_BD_PERFILES en cuanto se importa. Para que esta prueba no dependa
    en absoluto de esa base real (que en este entorno puede estar en un
    estado stale/inconsistente del propio montaje, nada que ver con esta
    funcion), se inyecta un modulo falso directamente en sys.modules: el
    "from X import Y" de evaluar_desfase_reportes() lo encuentra ya
    cacheado ahi y nunca ejecuta el modulo real.

    subestaciones_mod.recurso_generacion_subestacion, en cambio, se referencia
    en pipeline_status.py como atributo de modulo ya importado a nivel de
    archivo (subestaciones_mod.recurso_generacion_subestacion(...), no un
    "from X import Y" perezoso) -- por eso aqui se parchea directo el
    atributo del modulo real via monkeypatch.setattr, en vez de sys.modules."""
    monkeypatch.setattr(pipeline_status, "SUBESTACIONES", tuple(subs))

    fake_service = types.ModuleType("bess.ui.db_tools.service")
    fake_service.resumen_medidores = lambda: list(resumen_por_id.values())
    monkeypatch.setitem(sys.modules, "bess.ui.db_tools.service", fake_service)

    fake_combined = types.ModuleType("bess.data.aggregates.combined")
    fake_combined.ultima_fecha_hora_escrita = lambda ruta: reporte_por_ruta.get(ruta)
    monkeypatch.setitem(sys.modules, "bess.data.aggregates.combined", fake_combined)

    generacion_por_sub = generacion_por_sub or {}
    monkeypatch.setattr(
        pipeline_status.subestaciones_mod,
        "recurso_generacion_subestacion",
        lambda sub_id: generacion_por_sub.get(sub_id),
    )


def _resumen(medidor_id: str, ultima_sync: str) -> _ResumenMedidorFalso:
    return _ResumenMedidorFalso(
        medidor_id=medidor_id,
        registros=1,
        fecha_min=None,
        fecha_max=None,
        ultima_sync=ultima_sync,
        ultima_sync_ok=None,
    )


def test_sin_desfase_no_marca_atrasado(monkeypatch):
    med = _MedidorFalso("ION_Testigo_IUSA1", "ruta_1")
    sub = _SubestacionFalsa("IUSA_1", "IUSA 1", med)
    _preparar(
        monkeypatch,
        [sub],
        {med.nombre: _resumen(med.nombre, "2026-07-16 08:15:00")},
        {med.ruta: pd.Timestamp("2026-07-16 08:15:00")},
    )
    resultado = pipeline_status.evaluar_desfase_reportes()
    assert len(resultado) == 1
    assert resultado[0].desfase == timedelta(0)


def test_desfase_leve_bajo_umbral_no_alerta(monkeypatch):
    med = _MedidorFalso("ION_Testigo_IUSA1", "ruta_1")
    sub = _SubestacionFalsa("IUSA_1", "IUSA 1", med)
    # Reporte 1 hora atras del sync -- por debajo de UMBRAL_DESFASE_REPORTE
    # (3h): es el rezago normal de un flujo manual "sync ahora, proceso en
    # un rato", no debe generar aviso.
    _preparar(
        monkeypatch,
        [sub],
        {med.nombre: _resumen(med.nombre, "2026-07-16 08:15:00")},
        {med.ruta: pd.Timestamp("2026-07-16 07:15:00")},
    )
    warnings = []
    monkeypatch.setattr(pipeline_status.st, "warning", lambda texto: warnings.append(texto))
    pipeline_status.render_aviso_reporte_desactualizado()
    assert warnings == []


def test_desfase_grande_dispara_alerta(monkeypatch):
    """Reproduce el caso real: reporte congelado en 13/07, sync ya en 15/07
    (~2 dias de diferencia, muy por encima del umbral de 3h)."""
    med = _MedidorFalso("ION_Testigo_IUSA1", "ruta_1")
    sub = _SubestacionFalsa("IUSA_1", "IUSA 1", med)
    _preparar(
        monkeypatch,
        [sub],
        {med.nombre: _resumen(med.nombre, "2026-07-15 19:00:00")},
        {med.ruta: pd.Timestamp("2026-07-13 19:55:00")},
    )
    warnings = []
    monkeypatch.setattr(pipeline_status.st, "warning", lambda texto: warnings.append(texto))
    pipeline_status.render_aviso_reporte_desactualizado()
    assert len(warnings) == 1
    assert "IUSA 1" in warnings[0]
    assert "Procesar todo" in warnings[0]


def test_medidor_sin_sync_state_no_rompe(monkeypatch):
    """Medidor nunca sincronizado (sin fila en sync_state): no debe fallar
    ni marcarse como atrasado (no hay con que comparar)."""
    med = _MedidorFalso("ION_Testigo_IUSA1", "ruta_1")
    sub = _SubestacionFalsa("IUSA_1", "IUSA 1", med)
    _preparar(monkeypatch, [sub], {}, {med.ruta: pd.Timestamp("2026-07-16 08:15:00")})
    resultado = pipeline_status.evaluar_desfase_reportes()
    assert resultado[0].ultima_sync is None
    assert resultado[0].desfase is None

    warnings = []
    monkeypatch.setattr(pipeline_status.st, "warning", lambda texto: warnings.append(texto))
    pipeline_status.render_aviso_reporte_desactualizado()
    assert warnings == []


def test_reporte_inexistente_no_rompe(monkeypatch):
    """Reporte aun no generado (archivo no existe -> None): no debe fallar
    ni marcarse como atrasado -- ese caso ya lo cubre render_estado_vacio_reporteador."""
    med = _MedidorFalso("ION_Testigo_IUSA1", "ruta_1")
    sub = _SubestacionFalsa("IUSA_1", "IUSA 1", med)
    _preparar(
        monkeypatch,
        [sub],
        {med.nombre: _resumen(med.nombre, "2026-07-16 08:15:00")},
        {},
    )
    resultado = pipeline_status.evaluar_desfase_reportes()
    assert resultado[0].ultima_reporte is None
    assert resultado[0].desfase is None

    warnings = []
    monkeypatch.setattr(pipeline_status.st, "warning", lambda texto: warnings.append(texto))
    pipeline_status.render_aviso_reporte_desactualizado()
    assert warnings == []


def test_varias_subestaciones_solo_reporta_las_atrasadas(monkeypatch):
    med_ok = _MedidorFalso("ION_Testigo_IUSA1", "ruta_ok")
    sub_ok = _SubestacionFalsa("IUSA_1", "IUSA 1", med_ok)
    med_atrasado = _MedidorFalso("BESS_NORTE", "ruta_atrasada")
    sub_atrasada = _SubestacionFalsa("IUSA_ARAGON", "IUSA Aragon", med_atrasado)

    _preparar(
        monkeypatch,
        [sub_ok, sub_atrasada],
        {
            med_ok.nombre: _resumen(med_ok.nombre, "2026-07-16 08:15:00"),
            med_atrasado.nombre: _resumen(med_atrasado.nombre, "2026-07-16 08:15:00"),
        },
        {
            med_ok.ruta: pd.Timestamp("2026-07-16 08:15:00"),
            med_atrasado.ruta: pd.Timestamp("2026-07-14 00:00:00"),
        },
    )
    warnings = []
    monkeypatch.setattr(pipeline_status.st, "warning", lambda texto: warnings.append(texto))
    pipeline_status.render_aviso_reporte_desactualizado()
    assert len(warnings) == 1
    assert "IUSA Aragon" in warnings[0]
    assert "IUSA 1" not in warnings[0]


def test_sin_recurso_generacion_solo_evalua_consumo(monkeypatch):
    """Subestacion sin generacion (recurso_generacion_subestacion -> None):
    el resultado sigue teniendo una sola entrada, igual que antes de esta
    extension -- no debe agregar nada por el solo hecho de que exista la
    revision de generacion."""
    med = _MedidorFalso("ION_Testigo_IUSA1", "ruta_1")
    sub = _SubestacionFalsa("IUSA_1", "IUSA 1", med)
    _preparar(
        monkeypatch,
        [sub],
        {med.nombre: _resumen(med.nombre, "2026-07-16 08:15:00")},
        {med.ruta: pd.Timestamp("2026-07-16 08:15:00")},
    )
    resultado = pipeline_status.evaluar_desfase_reportes()
    assert len(resultado) == 1
    assert resultado[0].etiqueta == "IUSA 1"


def test_generacion_incluida_como_entrada_separada(monkeypatch):
    """Subestacion con consumo Y generacion: evaluar_desfase_reportes()
    debe devolver dos entradas, una por cada reporte."""
    med = _MedidorFalso("Consumo_Aragon", "ruta_consumo")
    sub = _SubestacionFalsa("IUSA_ARAGON", "IUSA Aragon", med)
    ruta_gen = rutas_mod.ruta_reporte(
        "IUSA_ARAGON", "COMBINADO_POR_MINUTO_GENERACION_ARAGON.csv"
    )
    _preparar(
        monkeypatch,
        [sub],
        {
            med.nombre: _resumen(med.nombre, "2026-07-16 10:00:00"),
            "GENERACION_ARAGON": _resumen("GENERACION_ARAGON", "2026-07-16 10:00:00"),
        },
        {
            med.ruta: pd.Timestamp("2026-07-16 10:00:00"),
            ruta_gen: pd.Timestamp("2026-07-16 10:00:00"),
        },
        generacion_por_sub={
            "IUSA_ARAGON": _RecursoGeneracionFalso(prefijo_reporte="GENERACION_ARAGON"),
        },
    )
    resultado = pipeline_status.evaluar_desfase_reportes()
    assert len(resultado) == 2
    etiquetas = {r.etiqueta for r in resultado}
    assert "IUSA Aragon" in etiquetas
    assert "IUSA Aragon · Generación" in etiquetas


def test_generacion_atrasada_dispara_alerta_aunque_consumo_al_dia(monkeypatch):
    """Reproduce el caso real: GENERACION_ARAGON con Filtrado/sync al
    corriente (10:00) pero su combinado congelado horas atras (06:00,
    4h de diferencia) -- mientras el reporte de consumo de la misma
    subestacion esta perfectamente al dia. El aviso original (solo
    consumo) nunca hubiera detectado esto."""
    med = _MedidorFalso("Consumo_Aragon", "ruta_consumo")
    sub = _SubestacionFalsa("IUSA_ARAGON", "IUSA Aragon", med)
    ruta_gen = rutas_mod.ruta_reporte(
        "IUSA_ARAGON", "COMBINADO_POR_MINUTO_GENERACION_ARAGON.csv"
    )
    _preparar(
        monkeypatch,
        [sub],
        {
            med.nombre: _resumen(med.nombre, "2026-07-16 10:00:00"),
            "GENERACION_ARAGON": _resumen("GENERACION_ARAGON", "2026-07-16 10:00:00"),
        },
        {
            med.ruta: pd.Timestamp("2026-07-16 10:00:00"),
            ruta_gen: pd.Timestamp("2026-07-16 06:00:00"),
        },
        generacion_por_sub={
            "IUSA_ARAGON": _RecursoGeneracionFalso(prefijo_reporte="GENERACION_ARAGON"),
        },
    )
    warnings = []
    monkeypatch.setattr(pipeline_status.st, "warning", lambda texto: warnings.append(texto))
    pipeline_status.render_aviso_reporte_desactualizado()
    assert len(warnings) == 1
    assert "IUSA Aragon · Generación" in warnings[0]
    # El de consumo esta al dia -- no debe aparecer mencionado como atrasado.
    assert "reporte hasta 16/07/2026 10:00, sincronizado hasta 16/07/2026 10:00" not in warnings[0]
