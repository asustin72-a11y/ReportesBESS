"""Clasificación de mensajes de sync para la UI."""

from __future__ import annotations

from bess.data.sync_mensajes import (
    clasificar_fallo_sync,
    mensaje_api_parcial,
    mensaje_granja_parcial,
    mensaje_ion_parcial,
)


def test_clasifica_timeout_api_iusasol() -> None:
    stderr = (
        'API: aviso — BESS_ARAGON — No se pudo conectar a '
        'https://api.iusasol.mx/v2.1/api/OAuth2/Token: [WinError 10060] …'
    )
    stdout = 'API: aviso — BESS_ARAGON — No se pudo conectar…'
    msg = clasificar_fallo_sync(stdout, stderr)
    assert msg.tipo == 'error'
    assert 'API IUSASOL' in msg.titulo
    assert 'api.iusasol' in msg.explicacion.casefold() or 'internet' in msg.explicacion.casefold()
    assert 'PCarga' in msg.accion or 'Fallback' in msg.accion


def test_clasifica_error_api_generico() -> None:
    msg = clasificar_fallo_sync('API: error — credenciales', 'ERROR API: HTTP 401')
    assert 'API IUSASOL' in msg.titulo
    assert msg.tipo == 'error'
    assert 'PCarga' in msg.accion or 'Fallback' in msg.accion


def test_mensaje_api_parcial() -> None:
    aviso = mensaje_api_parcial(
        'Export: OK\nAPI: no disponible — use Mantenimiento DB → PCarga → Fallback',
        'API no disponible — se continúa con export',
    )
    assert aviso is not None
    assert aviso.tipo == 'warning'
    assert 'API' in aviso.titulo
    assert 'PCarga' in aviso.accion or 'Fallback' in aviso.accion


def test_mensaje_api_parcial_con_auto() -> None:
    aviso = mensaje_api_parcial(
        'API: aviso — x\nPCarga: 4/4 OK\nPCarga: auto — Ethernet tras fallo API\nExport: OK',
        '',
    )
    assert aviso is not None
    assert 'pcarga' in aviso.titulo.casefold()
    assert 'Ethernet' in aviso.explicacion or 'automático' in aviso.explicacion.casefold()


def test_mensaje_granja_parcial_sin_api() -> None:
    aviso = mensaje_granja_parcial('Granja: pendiente de API (sin plan B por pcarga)')
    assert aviso is not None
    assert aviso.tipo == 'warning'
    assert 'Granja' in aviso.titulo


def test_mensaje_ion_parcial() -> None:
    aviso = mensaje_ion_parcial('ION: no disponible | BD 19/07 22:00\nExport: OK')
    assert aviso is not None
    assert aviso.tipo == 'warning'
    assert 'ION' in aviso.titulo


def test_mensaje_ion_no_confunde_api() -> None:
    assert (
        mensaje_ion_parcial(
            'API: no disponible — use Mantenimiento DB → PCarga → Fallback (Banco/BESS/Cogen)\n'
            'Export: OK'
        )
        is None
    )


def test_sin_aviso_ion_si_ok() -> None:
    assert mensaje_ion_parcial('ION: +12 | 20/07 09:00\nExport: OK') is None
