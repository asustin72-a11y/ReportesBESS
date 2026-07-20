"""Soft-fail API: el sync continúa y exporta aunque la API falle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from bess.data.ingest.iusasol.client import IusasolError

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'sincronizar_perfiles.py'


def _cargar_modulo():
    spec = importlib.util.spec_from_file_location('sincronizar_perfiles_under_test', SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_quiet_api_fallo_soft_fail_sin_export(monkeypatch, capsys) -> None:
    """Con --sin-export, API caída no aborta (rc 0) y deja aviso."""
    mod = _cargar_modulo()

    def _boom_api(**kwargs):
        raise IusasolError('No se pudo conectar a api.iusasol.mx')

    monkeypatch.setattr(mod, 'sincronizar_api', _boom_api)
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'sincronizar_perfiles.py',
            '--quiet',
            '--sin-ion',
            '--sin-ion-iusa2',
            '--sin-granja',
            '--sin-export',
        ],
    )
    rc = mod.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert 'ERROR API' in captured.err or 'API no disponible' in captured.err
    assert 'API: aviso' in captured.out or 'API: no disponible' in captured.out


def test_api_fallo_llama_export(monkeypatch, capsys) -> None:
    """API caída: se llama exportar_todos (ION/BD) en lugar de abortar."""
    mod = _cargar_modulo()
    llamado = {'export': False}

    def _boom_api(**kwargs):
        raise IusasolError('timeout api.iusasol.mx')

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
        sys,
        'argv',
        [
            'sincronizar_perfiles.py',
            '--quiet',
            '--sin-ion',
            '--sin-ion-iusa2',
            '--sin-granja',
        ],
    )
    rc = mod.main()
    assert llamado['export'] is True
    assert rc == 0
    out = capsys.readouterr().out
    assert 'API: aviso' in out or 'API: no disponible' in out
