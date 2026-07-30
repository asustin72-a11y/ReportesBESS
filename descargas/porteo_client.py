"""Cliente API Reports/Porteo (medidores de porteo)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from bess.data.ingest.iusasol import IusasolClient
from bess.data.ingest.iusasol.client import IusasolError


class PorteoClient:
    """Endpoints Reports/Porteo/Meters y Porteo/Meter/Profiles."""

    def __init__(self, client: IusasolClient):
        self._client = client
        self._base = client.config.base_url.rstrip("/")

    def _get(self, ruta: str, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        url = f"{self._base}/{ruta}?{query}"
        solicitud = urllib.request.Request(
            url,
            method="GET",
            headers={"Authorization": f"Bearer {self._client.access_token}"},
        )
        try:
            with urllib.request.urlopen(solicitud, timeout=120) as respuesta:
                raw = respuesta.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            cuerpo = exc.read().decode("utf-8", errors="replace")
            raise IusasolError(
                f"Error en {url}",
                codigo=exc.code,
                cuerpo=cuerpo,
            ) from exc
        except urllib.error.URLError as exc:
            raise IusasolError(f"No se pudo conectar a {url}: {exc.reason}") from exc

        if not raw.strip():
            return {}
        return json.loads(raw)

    def listar_medidores(self) -> list[dict[str, Any]]:
        datos = self._get(
            "Reports/Porteo/Meters",
            {"company": self._client.company},
        )
        medidores = datos.get("meters", [])
        if not isinstance(medidores, list):
            raise IusasolError("Respuesta inesperada en Reports/Porteo/Meters")
        return medidores

    def obtener_perfil(
        self,
        meter_id: str,
        begin_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """GET Reports/Porteo/Meter/Profiles (rango beginDate/endDate)."""
        return self._get(
            "Reports/Porteo/Meter/Profiles",
            {
                "id": meter_id,
                "beginDate": begin_date,
                "endDate": end_date,
            },
        )
