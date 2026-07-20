"""Clasificación de mensajes de sync para la UI."""

from __future__ import annotations

from bess.data.sync_mensajes import clasificar_fallo_sync, mensaje_ion_parcial


def test_clasifica_timeout_api_iusasol() -> None:
    stderr = (
        'Sync detenido: BESS_ARAGON — No se pudo conectar a '
        'https://api.iusasol.mx/v2.1/api/OAuth2/Token: [WinError 10060] …'
    )
    stdout = 'API: error — Sync detenido: BESS_ARAGON — No se pudo conectar…'
    msg = clasificar_fallo_sync(stdout, stderr)
    assert msg.tipo == 'error'
    assert 'API IUSASOL' in msg.titulo
    assert 'api.iusasol' in msg.explicacion.casefold() or 'internet' in msg.explicacion.casefold()
    assert 'Reintente' in msg.accion


def test_clasifica_error_api_generico() -> None:
    msg = clasificar_fallo_sync('API: error — credenciales', 'ERROR API: HTTP 401')
    assert 'API IUSASOL' in msg.titulo
    assert msg.tipo == 'error'


def test_mensaje_ion_parcial() -> None:
    aviso = mensaje_ion_parcial('ION: no disponible | BD 19/07 22:00\nExport: OK')
    assert aviso is not None
    assert aviso.tipo == 'warning'
    assert 'ION' in aviso.titulo


def test_sin_aviso_ion_si_ok() -> None:
    assert mensaje_ion_parcial('ION: +12 | 20/07 09:00\nExport: OK') is None
