"""Cliente API Reports/Farm (granja · medidores MEGA)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from bess.data.ingest.iusasol import IusasolClient
from bess.data.ingest.iusasol.client import IusasolError

PERIODICIDAD_DIARIA = "D"


class FarmClient:
    """Endpoints Reports/Farms, Farm/Meters y Farm/Meter/Profiles."""

    def __init__(self, client: IusasolClient):
        self._client = client
        self._base = client.config.base_url.rstrip("/")

    def _get(self, ruta: str, params: dict[str, str]) -> dict:
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

    def listar_granjas(self) -> list[dict]:
        datos = self._get("Reports/Farms", {})
        granjas = datos.get("farms", [])
        if not isinstance(granjas, list):
            raise IusasolError("Respuesta inesperada en Reports/Farms")
        return granjas

    def listar_medidores(self, farm_idcode: str) -> list[dict]:
        datos = self._get("Reports/Farm/Meters", {"id": farm_idcode})
        medidores = datos.get("meters", [])
        if not isinstance(medidores, list):
            raise IusasolError("Respuesta inesperada en Reports/Farm/Meters")
        return medidores

    def perfil_medidor_dia(self, meter_idcode: str, dia: date) -> list[dict]:
        datos = self._get(
            "Reports/Farm/Meter/Profiles",
            {
                "id": meter_idcode,
                "date": dia.isoformat(),
                "periodicity": PERIODICIDAD_DIARIA,
            },
        )
        perfiles = datos.get("profiles", [])
        return perfiles if isinstance(perfiles, list) else []


def kw_desde_perfil(perfiles: list[dict]) -> list[tuple[str, float]]:
    """Extrae (fecha_hora, kW) de la respuesta Farm/Meter/Profiles."""
    filas: list[tuple[str, float]] = []
    for item in perfiles:
        if not isinstance(item, dict):
            continue
        tiempo = item.get("time")
        if not tiempo:
            continue
        canales = item.get("channels") or []
        kw = float(canales[0]) if len(canales) > 0 and canales[0] is not None else 0.0
        fecha_txt = str(tiempo).replace("T", " ")
        if len(fecha_txt) == 16:
            fecha_txt += ":00"
        filas.append((fecha_txt, kw))
    return filas
