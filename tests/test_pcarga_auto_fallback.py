"""Fallback pcarga automático (opt-in) tras fallo de API."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

from bess.config.pcarga_endpoints import auto_fallback_habilitado
from bess.data.ingest.iusasol.client import IusasolError

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'sincronizar_perfiles.py'


def _cargar_modulo():
    name = 'sincronizar_perfiles_auto_fb'
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class _LoteFake:
    exitosos: int = 4
    medidores: list = field(default_factory=list)
    log: str = 'ok'

    def __post_init__(self):
        if not self.medidores:
            from bess.data.ingest.pcarga.fallback import ResultadoFallbackMedidor

            self.medidores = [
                ResultadoFallbackMedidor(medidor_id=m, ok=True, registros=1)
                for m in ('Banco_1', 'BESS_NORTE', 'Cogeneracion', 'BESS_SUR')
            ]
            self.exitosos = 4


def test_auto_fallback_default_off(monkeypatch):
    monkeypatch.delenv('PCARGA_AUTO_FALLBACK', raising=False)
    monkeypatch.setattr(
        'bess.config.pcarga_endpoints._pcarga_secrets',
        lambda: {},
    )
    assert auto_fallback_habilitado() is False


def test_auto_fallback_env_on(monkeypatch):
    monkeypatch.setenv('PCARGA_AUTO_FALLBACK', '1')
    assert auto_fallback_habilitado() is True
    assert auto_fallback_habilitado(forzar_off=True) is False


def test_api_fallo_con_flag_llama_pcarga(monkeypatch, capsys):
    mod = _cargar_modulo()
    llamado = {'pcarga': False, 'export': False}

    def _boom_api(**kwargs):
        raise IusasolError('timeout api.iusasol.mx')

    def _fb(**kwargs):
        llamado['pcarga'] = True
        assert kwargs.get('rebuild') is False
        assert kwargs.get('procesar') is False
        return _LoteFake()

    def _export_ok(*args, **kwargs):
        llamado['export'] = True
        return 0

    monkeypatch.setattr(mod, 'sincronizar_api', _boom_api)
    monkeypatch.setattr(mod, 'exportar_todos', _export_ok)
    monkeypatch.setattr(
        mod,
        'aplicar_validacion_post_sync',
        lambda **kwargs: mod.ResultadoValidacionSync(True, 'ok'),
    )
    monkeypatch.setattr(
        'bess.data.ingest.pcarga.fallback.ejecutar_fallback_pcarga_iusa12',
        _fb,
    )

    rc = mod.main(
        [
            '--quiet',
            '--sin-ion',
            '--sin-ion-iusa2',
            '--sin-granja',
            '--fallback-pcarga',
        ]
    )
    assert rc == 0
    assert llamado['pcarga'] is True
    assert llamado['export'] is True
    out = capsys.readouterr().out
    assert 'PCarga:' in out
    assert 'auto' in out.casefold()


def test_api_fallo_sin_opt_in_no_llama_pcarga(monkeypatch):
    mod = _cargar_modulo()
    llamado = {'pcarga': False}

    def _boom_api(**kwargs):
        raise IusasolError('timeout api.iusasol.mx')

    def _fb(**kwargs):
        llamado['pcarga'] = True
        return _LoteFake()

    monkeypatch.delenv('PCARGA_AUTO_FALLBACK', raising=False)
    monkeypatch.setattr(
        'bess.config.pcarga_endpoints._pcarga_secrets',
        lambda: {},
    )
    monkeypatch.setattr(mod, 'sincronizar_api', _boom_api)
    monkeypatch.setattr(mod, 'exportar_todos', lambda *a, **k: 0)
    monkeypatch.setattr(
        mod,
        'aplicar_validacion_post_sync',
        lambda **kwargs: mod.ResultadoValidacionSync(True, 'ok'),
    )
    monkeypatch.setattr(
        'bess.data.ingest.pcarga.fallback.ejecutar_fallback_pcarga_iusa12',
        _fb,
    )

    rc = mod.main(
        [
            '--quiet',
            '--sin-ion',
            '--sin-ion-iusa2',
            '--sin-granja',
            '--sin-fallback-pcarga',
        ]
    )
    assert rc == 0
    assert llamado['pcarga'] is False


def test_sin_api_no_dispara_fallback(monkeypatch):
    mod = _cargar_modulo()
    llamado = {'pcarga': False, 'api': False}

    def _api(**kwargs):
        llamado['api'] = True
        return []

    def _fb(**kwargs):
        llamado['pcarga'] = True
        return _LoteFake()

    monkeypatch.setattr(mod, 'sincronizar_api', _api)
    monkeypatch.setattr(mod, 'exportar_todos', lambda *a, **k: 0)
    monkeypatch.setattr(
        mod,
        'aplicar_validacion_post_sync',
        lambda **kwargs: mod.ResultadoValidacionSync(True, 'ok'),
    )
    monkeypatch.setattr(
        'bess.data.ingest.pcarga.fallback.ejecutar_fallback_pcarga_iusa12',
        _fb,
    )

    rc = mod.main(
        [
            '--quiet',
            '--sin-ion',
            '--sin-ion-iusa2',
            '--sin-granja',
            '--sin-api',
            '--fallback-pcarga',
        ]
    )
    assert rc == 0
    assert llamado['api'] is False
    assert llamado['pcarga'] is False
