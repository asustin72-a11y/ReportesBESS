"""Cliente HTTP para OAuth2 y reportes ISOL."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from bess.data.ingest.iusasol.config import IusasolConfig


class IusasolError(RuntimeError):
    """Error de la API IUSASOL."""

    def __init__(self, mensaje: str, *, codigo: int | None = None, cuerpo: str | None = None):
        detalle = mensaje
        if codigo is not None:
            detalle = f'{mensaje} (HTTP {codigo})'
        if cuerpo:
            detalle = f'{detalle}: {cuerpo[:500]}'
        super().__init__(detalle)
        self.codigo = codigo
        self.cuerpo = cuerpo


class IusasolClient:
    def __init__(self, config: IusasolConfig):
        self.config = config
        self._access_token: str | None = None
        self._company: str | None = None

    @property
    def access_token(self) -> str:
        if self._access_token is None:
            self.autenticar()
        assert self._access_token is not None
        return self._access_token

    @property
    def company(self) -> str:
        if self._company is None:
            self.autenticar()
        assert self._company is not None
        return self._company

    def autenticar(self) -> dict[str, Any]:
        """POST OAuth2/Token. Guarda access_token y company (ckey)."""
        cuerpo = urllib.parse.urlencode({
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'company_key': self.config.company_key,
            'grant_type': self.config.grant_type,
            'encrypted': self.config.encrypted,
        }).encode('utf-8')

        url = f'{self.config.base_url.rstrip("/")}/OAuth2/Token'
        solicitud = urllib.request.Request(
            url,
            data=cuerpo,
            method='POST',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )

        respuesta = self._ejecutar(solicitud)
        token = respuesta.get('access_token')
        if not token:
            raise IusasolError('La respuesta del token no incluye access_token', cuerpo=json.dumps(respuesta))

        self._access_token = str(token)
        self._company = str(respuesta.get('ckey') or respuesta.get('company_key') or 'ISM')
        return respuesta

    def listar_medidores(self) -> Any:
        """GET Reports/ISOL/Meters."""
        return self._get('Reports/ISOL/Meters', {'company': self.company})

    def listar_contratos(self) -> Any:
        """GET Reports/ISOL/Contracts — contratos activos."""
        return self._get('Reports/ISOL/Contracts', {'company': self.company})

    def medidores_de_contrato(self, contract_id: str) -> Any:
        """GET Reports/ISOL/Contract — medidores de un contrato (idcode)."""
        return self._get('Reports/ISOL/Contract', {
            'id': contract_id,
            'company': self.company,
        })

    def obtener_perfil(
        self,
        meter_id: str,
        begin_date: str,
        end_date: str,
        *,
        tym: str,
        tye: str,
        detallado: bool = False,
        permitir_vacio: bool = False,
    ) -> Any:
        """GET Reports/ISOL/Profiles/Gral o Detailed."""
        ruta = (
            'Reports/ISOL/Profiles/Detailed'
            if detallado
            else 'Reports/ISOL/Profiles/Gral'
        )
        return self._get(
            ruta,
            {
                'id': meter_id,
                'beginDate': begin_date,
                'endDate': end_date,
                'tym': tym,
                'tye': tye,
                'company': self.company,
            },
            permitir_vacio=permitir_vacio,
        )

    def _get(
        self,
        ruta: str,
        params: dict[str, str],
        *,
        permitir_vacio: bool = False,
        timeout: int = 120,
    ) -> Any:
        query = urllib.parse.urlencode(params)
        url = f'{self.config.base_url.rstrip("/")}/{ruta}?{query}'
        solicitud = urllib.request.Request(
            url,
            method='GET',
            headers={'Authorization': f'Bearer {self.access_token}'},
        )
        return self._ejecutar(
            solicitud,
            permitir_vacio=permitir_vacio,
            timeout=timeout,
        )

    def _ejecutar(
        self,
        solicitud: urllib.request.Request,
        *,
        permitir_vacio: bool = False,
        timeout: int = 120,
    ) -> Any:
        try:
            with urllib.request.urlopen(solicitud, timeout=timeout) as respuesta:
                raw = respuesta.read().decode('utf-8')
                status = respuesta.status
        except urllib.error.HTTPError as exc:
            cuerpo = exc.read().decode('utf-8', errors='replace')
            raise IusasolError(
                f'Error en {solicitud.full_url}',
                codigo=exc.code,
                cuerpo=cuerpo,
            ) from exc
        except urllib.error.URLError as exc:
            raise IusasolError(f'No se pudo conectar a {solicitud.full_url}: {exc.reason}') from exc

        if status == 204 or not raw.strip():
            if permitir_vacio:
                return {'profiles': [], 'response': {'code': status or 204, 'result': 'empty'}}
            raise IusasolError(
                'La API no devolvió datos de perfil (HTTP 204 / cuerpo vacío). '
                'Revise id del medidor, rango de fechas y parámetros tym/tye '
                '(deben ser los mismos que funcionaron en Postman).',
                codigo=status if status == 204 else None,
            )

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
