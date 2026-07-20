"""Con --quiet, los fallos API deben llegar a stderr/stdout (UI sidebar)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

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


def test_quiet_imprime_fallo_api_en_stderr(monkeypatch, capsys) -> None:
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
    assert rc == 1
    assert 'ERROR API' in captured.err
    assert 'API: error' in captured.out
