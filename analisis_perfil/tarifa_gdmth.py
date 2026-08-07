"""Tarifa GDMTH (VMC): precios mensuales por periodo horario.

Fuente: GDMTH VMC.xlsx, convertida a formato largo (tarifas_gdmth.csv).

Costo de energía = kWh_Base×P_Base + kWh_Intermedio×P_Intermedio + kWh_Punta×P_Punta.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
CSV_TARIFAS = DIR / "tarifas_gdmth.csv"

PERIODOS = ("Base", "Intermedio", "Punta")
CLAVE_PRECIO = {
    "Base": "base",
    "Intermedio": "intermedio",
    "Punta": "punta",
}


@dataclass(frozen=True)
class PreciosGDMTH:
    fecha_vigencia: date
    base: float
    intermedio: float
    punta: float
    cargo_fijo: float = 0.0
    distribucion: float = 0.0
    capacidad: float = 0.0

    def precio_periodo(self, periodo: str) -> float:
        return float(getattr(self, CLAVE_PRECIO[periodo]))


def _parse_fecha(valor: str | date | datetime) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor).strip()[:10])


def cargar_tarifas(ruta: Path | None = None) -> list[PreciosGDMTH]:
    path = ruta or CSV_TARIFAS
    if not path.exists():
        raise FileNotFoundError(f"No se encontro el CSV de tarifas GDMTH: {path}")
    filas: list[PreciosGDMTH] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filas.append(
                PreciosGDMTH(
                    fecha_vigencia=_parse_fecha(row["fecha_vigencia"]),
                    base=float(row["precio_base"]),
                    intermedio=float(row["precio_intermedio"]),
                    punta=float(row["precio_punta"]),
                    cargo_fijo=float(row.get("cargo_fijo") or 0),
                    distribucion=float(row.get("distribucion") or 0),
                    capacidad=float(row.get("capacidad") or 0),
                )
            )
    if not filas:
        raise ValueError(f"CSV de tarifas GDMTH vacio: {path}")
    filas.sort(key=lambda p: p.fecha_vigencia)
    return filas


def precios_vigentes(
    fecha: str | date | datetime,
    tarifas: list[PreciosGDMTH] | None = None,
    region: str | None = None,
) -> PreciosGDMTH:
    """Precio del mes vigente en `fecha`.

    Si `region` está definida, intenta primero el reporte CFE de ese mes.
    """
    if region:
        try:
            from tarifas_cfe_catalog import precios_desde_reporte

            cfe = precios_desde_reporte("GDMTH", region, fecha)
            if cfe is not None:
                return cfe  # type: ignore[return-value]
        except Exception:
            pass
    catalogo = tarifas if tarifas is not None else cargar_tarifas()
    dia = _parse_fecha(fecha)
    vigencia_mes = date(dia.year, dia.month, 1)
    elegida: PreciosGDMTH | None = None
    for fila in catalogo:
        if fila.fecha_vigencia <= vigencia_mes:
            elegida = fila
        else:
            break
    if elegida is None:
        raise ValueError(
            f"No hay tarifa GDMTH vigente para {dia.isoformat()} "
            f"(catalogo desde {catalogo[0].fecha_vigencia.isoformat()})"
        )
    return elegida


def _pago_por_periodos(
    kwh_por_periodo: dict[str, float], precios: PreciosGDMTH
) -> dict:
    escalones: dict[str, dict[str, float]] = {}
    total_kwh = 0.0
    total_imp = 0.0
    for periodo in PERIODOS:
        kwh = max(0.0, float(kwh_por_periodo.get(periodo, 0.0) or 0.0))
        importe = kwh * precios.precio_periodo(periodo)
        clave = CLAVE_PRECIO[periodo]
        escalones[clave] = {"kwh": kwh, "importe": importe}
        total_kwh += kwh
        total_imp += importe
    return {"kwh": total_kwh, "importe": total_imp, "escalones": escalones}


def calcular_ahorro(
    kwh_neteo_por_periodo: dict[str, float],
    kwh_real_por_periodo: dict[str, float],
    fecha_fin_periodo: str | date | datetime,
    tarifas: list[PreciosGDMTH] | None = None,
    region: str | None = None,
) -> dict:
    """Costo Neteo / Real / ahorro con precios GDMTH del último día del periodo."""
    precios = precios_vigentes(fecha_fin_periodo, tarifas, region=region)
    neteo = _pago_por_periodos(kwh_neteo_por_periodo, precios)
    real = _pago_por_periodos(kwh_real_por_periodo, precios)
    titulo = f"GDMTH · {region}" if region else "GDMTH"
    return {
        "esquema": "GDMTH",
        "titulo_tarifa": titulo,
        "fecha_tarifa": precios.fecha_vigencia.isoformat(),
        "region": region or "",
        "precios": {
            "base": precios.base,
            "intermedio": precios.intermedio,
            "punta": precios.punta,
        },
        "etiquetas_escalones": (
            ("base", "Base"),
            ("intermedio", "Intermedio"),
            ("punta", "Punta"),
        ),
        "neteo": neteo,
        "real": real,
        "ahorro": real["importe"] - neteo["importe"],
    }


def calcular_costo(
    kwh_por_periodo: dict[str, float],
    fecha_fin_periodo: str | date | datetime,
    tarifas: list[PreciosGDMTH] | None = None,
    region: str | None = None,
) -> dict:
    """Costo de energía (consumo) con precios GDMTH del último mes del perfil."""
    precios = precios_vigentes(fecha_fin_periodo, tarifas, region=region)
    consumo = _pago_por_periodos(kwh_por_periodo, precios)
    titulo = f"GDMTH · {region}" if region else "GDMTH"
    return {
        "esquema": "GDMTH",
        "titulo_tarifa": titulo,
        "fecha_tarifa": precios.fecha_vigencia.isoformat(),
        "region": region or "",
        "precios": {
            "base": precios.base,
            "intermedio": precios.intermedio,
            "punta": precios.punta,
        },
        "etiquetas_escalones": (
            ("base", "Base"),
            ("intermedio", "Intermedio"),
            ("punta", "Punta"),
        ),
        "consumo": consumo,
    }
