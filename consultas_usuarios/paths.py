"""Rutas del módulo Consultas Usuarios."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'consultas_usuarios'

REPORTE_PRINCIPAL = DATA_DIR / 'reporte_principal.csv'
CONTRATOS_MEDIDORES = DATA_DIR / 'contratos_medidores.csv'
CONTRATOS_VACIOS = DATA_DIR / 'contratos_vacios.csv'

# Logo IUSASOL (compartido con el repo; no acopla UI a BESS)
LOGO_CANDIDATOS = (
    PROJECT_ROOT / 'data' / 'Logo IUSASOL.png',
    PROJECT_ROOT / 'data' / 'LogoIUSASOL.png',
    PROJECT_ROOT / 'data' / 'LogoIUSASOL.jpeg',
    PROJECT_ROOT / 'LogoIUSASOL.jpeg',
)


def resolver_logo() -> Path | None:
    for ruta in LOGO_CANDIDATOS:
        if ruta.is_file():
            return ruta
    return None
