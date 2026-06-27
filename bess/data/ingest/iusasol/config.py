"""Credenciales y URL base de la API IUSASOL."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from bess.config.paths import PROJECT_ROOT

from bess.data.ingest.iusasol.to_csv import TYE_ENERGIA, TYM_KWH

DEFAULT_BASE_URL = 'https://api.iusasol.mx/v2.1/api'

_ERROR_SIN_CREDENCIALES = (
    'Credenciales IUSASOL no configuradas. Use variables de entorno '
    'IUSASOL_CLIENT_ID e IUSASOL_CLIENT_SECRET, o la sección [iusasol] '
    'en .streamlit/secrets.toml (vea .streamlit/secrets.toml.example).'
)


@dataclass(frozen=True)
class IusasolConfig:
    client_id: str
    client_secret: str
    company_key: str = 'system'
    grant_type: str = 'password'
    encrypted: str = 'false'
    base_url: str = DEFAULT_BASE_URL
    # tym: escala (0=W, 1=Wh, 2=kWh, 3=MWh, 4=GWh). tye: E=energía, P=potencia.
    tym: str = TYM_KWH
    tye: str = TYE_ENERGIA


def _desde_variables_entorno() -> IusasolConfig | None:
    client_id = os.environ.get('IUSASOL_CLIENT_ID', '').strip()
    client_secret = os.environ.get('IUSASOL_CLIENT_SECRET', '').strip()
    if not client_id or not client_secret:
        return None
    return IusasolConfig(
        client_id=client_id,
        client_secret=client_secret,
        company_key=os.environ.get('IUSASOL_COMPANY_KEY', 'system').strip() or 'system',
        grant_type=os.environ.get('IUSASOL_GRANT_TYPE', 'password').strip() or 'password',
        encrypted=os.environ.get('IUSASOL_ENCRYPTED', 'false').strip() or 'false',
        base_url=os.environ.get('IUSASOL_BASE_URL', DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        tym=os.environ.get('IUSASOL_TYM', '').strip() or TYM_KWH,
        tye=os.environ.get('IUSASOL_TYE', '').strip() or TYE_ENERGIA,
    )


def _desde_secrets_toml() -> IusasolConfig | None:
    ruta = PROJECT_ROOT / '.streamlit' / 'secrets.toml'
    if not ruta.is_file():
        return None
    with ruta.open('rb') as archivo:
        secrets = tomllib.load(archivo)
    seccion = secrets.get('iusasol')
    if not isinstance(seccion, dict):
        return None
    client_id = str(seccion.get('client_id', '')).strip()
    client_secret = str(seccion.get('client_secret', '')).strip()
    if not client_id or not client_secret:
        return None
    return IusasolConfig(
        client_id=client_id,
        client_secret=client_secret,
        company_key=str(seccion.get('company_key', 'system')).strip() or 'system',
        grant_type=str(seccion.get('grant_type', 'password')).strip() or 'password',
        encrypted=str(seccion.get('encrypted', 'false')).strip() or 'false',
        base_url=str(seccion.get('base_url', DEFAULT_BASE_URL)).strip() or DEFAULT_BASE_URL,
        tym=str(seccion.get('tym', '')).strip() or TYM_KWH,
        tye=str(seccion.get('tye', '')).strip() or TYE_ENERGIA,
    )


def cargar_config_iusasol() -> IusasolConfig:
    """Credenciales desde env (prioridad) o .streamlit/secrets.toml."""
    config = _desde_variables_entorno() or _desde_secrets_toml()
    if config is None:
        raise RuntimeError(_ERROR_SIN_CREDENCIALES)
    return config
