#!/usr/bin/env python3
"""
Descarga perfiles de medidores de granja (API Reports/Farm).

Por defecto: primeros 20 MEGA, periodicidad diaria (5 min), desde 2026-05-01 hasta hoy.
Salida: CSV por medidor en data/perfiles_granja/.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.data.ingest.iusasol import IusasolClient, cargar_config_iusasol
from bess.data.ingest.iusasol.client import IusasolError

ZONA = ZoneInfo("America/Mexico_City")
PERIODICIDAD = "D"


def _hoy_local() -> date:
    return datetime.now(ZONA).date()


def _rango_fechas(desde: date, hasta: date) -> list[date]:
    dias: list[date] = []
    cursor = desde
    while cursor <= hasta:
        dias.append(cursor)
        cursor += timedelta(days=1)
    return dias


def _slug_nickname(nickname: str, indice: int) -> str:
    if nickname.strip().upper().startswith("MEGA"):
        return f"MEGA_{indice:02d}"
    limpio = "".join(c if c.isalnum() else "_" for c in nickname.strip())
    limpio = limpio.strip("_") or f"medidor_{indice:02d}"
    return limpio


class FarmClient:
    """Cliente mínimo para endpoints Reports/Farm (sin integrar al pipeline BESS)."""

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
                "periodicity": PERIODICIDAD,
            },
        )
        perfiles = datos.get("profiles", [])
        return perfiles if isinstance(perfiles, list) else []


def _filas_csv(perfiles: list[dict]) -> list[dict[str, str | float]]:
    filas: list[dict[str, str | float]] = []
    for item in perfiles:
        if not isinstance(item, dict):
            continue
        tiempo = item.get("time")
        if not tiempo:
            continue
        canales = item.get("channels") or []
        montos = item.get("amounts") or []
        kw = float(canales[0]) if len(canales) > 0 and canales[0] is not None else 0.0
        monto = float(montos[0]) if len(montos) > 0 and montos[0] is not None else 0.0
        filas.append({
            "Fecha_Hora": str(tiempo).replace("T", " "),
            "kW": kw,
            "Monto": monto,
        })
    return filas


def _guardar_csv(ruta: Path, filas: list[dict[str, str | float]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=["Fecha_Hora", "kW", "Monto"])
        writer.writeheader()
        writer.writerows(filas)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga perfiles Farm/Meter/Profiles de los primeros N medidores MEGA.",
    )
    parser.add_argument("--desde", default="2026-05-01", help="Fecha inicio YYYY-MM-DD.")
    parser.add_argument("--hasta", default=None, help="Fecha fin YYYY-MM-DD (default: hoy).")
    parser.add_argument("--cantidad", type=int, default=20, help="Cuántos medidores bajar (orden API).")
    parser.add_argument(
        "--salida",
        type=Path,
        default=ROOT / "data" / "perfiles_granja",
        help="Carpeta de salida.",
    )
    parser.add_argument("--granja", default=None, help="idcode de granja (default: la primera).")
    parser.add_argument("--pausa", type=float, default=0.15, help="Segundos entre peticiones API.")
    args = parser.parse_args()

    desde = date.fromisoformat(args.desde)
    hasta = date.fromisoformat(args.hasta) if args.hasta else _hoy_local()
    if desde > hasta:
        print("ERROR: --desde no puede ser posterior a --hasta.", file=sys.stderr)
        return 1
    if args.cantidad < 1:
        print("ERROR: --cantidad debe ser >= 1.", file=sys.stderr)
        return 1

    dias = _rango_fechas(desde, hasta)
    salida = args.salida.resolve()
    salida.mkdir(parents=True, exist_ok=True)

    try:
        config = cargar_config_iusasol()
        api = IusasolClient(config)
        api.autenticar()
        farm_api = FarmClient(api)

        granjas = farm_api.listar_granjas()
        if not granjas:
            print("ERROR: no hay granjas en Reports/Farms.", file=sys.stderr)
            return 1

        if args.granja:
            granja = next((g for g in granjas if g.get("idcode") == args.granja), None)
            if not granja:
                print(f"ERROR: granja {args.granja!r} no encontrada.", file=sys.stderr)
                return 1
        else:
            granja = granjas[0]

        farm_id = str(granja["idcode"])
        farm_nombre = str(granja.get("name", "granja"))
        medidores = farm_api.listar_medidores(farm_id)[: args.cantidad]
        if not medidores:
            print("ERROR: la granja no tiene medidores.", file=sys.stderr)
            return 1

        print("=" * 72)
        print(f"Granja: {farm_nombre}")
        print(f"Medidores: {len(medidores)} | Días: {len(dias)} ({desde} → {hasta})")
        print(f"Salida: {salida}")
        print("=" * 72)

        manifest = {
            "granja": farm_nombre,
            "farm_idcode": farm_id,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "periodicity": PERIODICIDAD,
            "descargado_en": datetime.now(ZONA).isoformat(),
            "medidores": [],
        }

        total_peticiones = len(medidores) * len(dias)
        hechas = 0
        inicio = time.time()

        for idx, medidor in enumerate(medidores, start=1):
            nick = str(medidor.get("nickname") or f"MEGA #{idx}")
            serial = str(medidor.get("serial") or "")
            meter_id = str(medidor["idcode"])
            slug = _slug_nickname(nick, idx)
            ruta_csv = salida / f"{slug}.csv"

            filas_medidor: list[dict[str, str | float]] = []
            dias_con_datos = 0
            dias_vacios = 0
            errores_dia: list[str] = []

            print(f"\n[{idx}/{len(medidores)}] {nick} ({serial})")

            for dia in dias:
                hechas += 1
                try:
                    perfiles = farm_api.perfil_medidor_dia(meter_id, dia)
                    filas = _filas_csv(perfiles)
                    if filas:
                        filas_medidor.extend(filas)
                        dias_con_datos += 1
                    else:
                        dias_vacios += 1
                except IusasolError as exc:
                    errores_dia.append(f"{dia}: {exc}")
                    dias_vacios += 1

                if args.pausa > 0:
                    time.sleep(args.pausa)

                if hechas % 50 == 0 or hechas == total_peticiones:
                    pct = 100.0 * hechas / total_peticiones
                    print(f"  progreso global: {hechas}/{total_peticiones} ({pct:.1f}%)")

            filas_medidor.sort(key=lambda r: r["Fecha_Hora"])
            _guardar_csv(ruta_csv, filas_medidor)

            resumen_medidor = {
                "nickname": nick,
                "serial": serial,
                "idcode": meter_id,
                "archivo": ruta_csv.name,
                "registros": len(filas_medidor),
                "dias_con_datos": dias_con_datos,
                "dias_vacios": dias_vacios,
                "errores": errores_dia[:5],
            }
            manifest["medidores"].append(resumen_medidor)
            print(
                f"  → {ruta_csv.name}: {len(filas_medidor)} registros "
                f"({dias_con_datos} días con datos, {dias_vacios} vacíos/error)"
            )

        manifest_path = salida / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        elapsed = time.time() - inicio
        print("\n" + "=" * 72)
        print(f"Listo en {elapsed / 60:.1f} min. Manifest: {manifest_path}")
        print("=" * 72)
        return 0

    except (IusasolError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
