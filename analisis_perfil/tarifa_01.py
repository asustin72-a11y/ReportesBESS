"""Tarifa 01 (doméstica): bloques de energía y precios históricos.

Bloques de facturación (sobre el kWh total del periodo facturado):
  - primeros 150 kWh → precio básico
  - siguientes 130 kWh → precio intermedio
  - resto → precio excedente

Periodo que cruza meses calendario (p. ej. bimestre CFE 06-may → 06-jul):
  - Los bloques se aplican una sola vez al consumo total del periodo
    (evidencia recibo: 341 kWh → 150 + 130 + 61).
  - El precio de cada escalón es el promedio simple de las tarifas vigentes
    en cada mes calendario que abarca el periodo
    (mayo+junio+julio 2026 → 1.125 / 1.369 / 4.004).

Límite DAC (referencia CFE): promedio mensual ≈ (kWh/días)×(365.25/12) > 250 kWh
→ riesgo de reclasificación a Doméstica de Alto Consumo (sin subsidio).

Los precios mensuales viven en tarifas_t01.csv.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
CSV_TARIFAS = DIR / "tarifas_t01.csv"

KWH_BASICO = 150.0
KWH_INTERMEDIO = 130.0  # tramo siguiente (hasta 280 kWh acumulados)
LIMITE_DAC_KWH_MES = 250.0
DIAS_MES_PROM = 365.25 / 12.0


@dataclass(frozen=True)
class PreciosT01:
    fecha_vigencia: date
    basico: float
    intermedio: float
    excedente: float


@dataclass(frozen=True)
class DesglosePagoT01:
    kwh: float
    kwh_basico: float
    kwh_intermedio: float
    kwh_excedente: float
    precios: PreciosT01
    importe_basico: float
    importe_intermedio: float
    importe_excedente: float
    total: float


def _parse_fecha(valor: str | date | datetime) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()[:10]
    return date.fromisoformat(texto)


def cargar_tarifas(ruta: Path | None = None) -> list[PreciosT01]:
    path = ruta or CSV_TARIFAS
    if not path.exists():
        raise FileNotFoundError(f"No se encontro el CSV de tarifas T01: {path}")
    filas: list[PreciosT01] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filas.append(
                PreciosT01(
                    fecha_vigencia=_parse_fecha(row["fecha_vigencia"]),
                    basico=float(row["precio_basico"]),
                    intermedio=float(row["precio_intermedio"]),
                    excedente=float(row["precio_excedente"]),
                )
            )
    if not filas:
        raise ValueError(f"CSV de tarifas T01 vacio: {path}")
    filas.sort(key=lambda p: p.fecha_vigencia)
    return filas


def precios_vigentes(
    fecha: str | date | datetime, tarifas: list[PreciosT01] | None = None
) -> PreciosT01:
    """Precio del mes vigente en `fecha` (última vigencia <= primer día del mes)."""
    catalogo = tarifas if tarifas is not None else cargar_tarifas()
    dia = _parse_fecha(fecha)
    vigencia_mes = date(dia.year, dia.month, 1)
    elegida: PreciosT01 | None = None
    for fila in catalogo:
        if fila.fecha_vigencia <= vigencia_mes:
            elegida = fila
        else:
            break
    if elegida is None:
        raise ValueError(
            f"No hay tarifa T01 vigente para {dia.isoformat()} "
            f"(catalogo desde {catalogo[0].fecha_vigencia.isoformat()})"
        )
    return elegida


def meses_calendario(fecha_ini: date, fecha_fin: date) -> list[date]:
    """Primer día de cada mes calendario tocado por [fecha_ini, fecha_fin]."""
    if fecha_fin < fecha_ini:
        raise ValueError("fecha_fin debe ser ≥ fecha_ini")
    out: list[date] = []
    cur = date(fecha_ini.year, fecha_ini.month, 1)
    fin_mes = date(fecha_fin.year, fecha_fin.month, 1)
    while cur <= fin_mes:
        out.append(cur)
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return out


def precios_promedio_periodo(
    fecha_ini: date,
    fecha_fin: date,
    tarifas: list[PreciosT01] | None = None,
) -> tuple[PreciosT01, list[dict]]:
    """Promedio simple de precios por escalón en los meses que abarca el periodo.

    Evidencia recibo CFE (06-may-26 → 06-jul-26): promedio mayo+junio+julio
    = 1.125 / 1.369 / 4.004 (no ponderado por días).
    """
    catalogo = tarifas if tarifas is not None else cargar_tarifas()
    meses = meses_calendario(fecha_ini, fecha_fin)
    detalle: list[dict] = []
    bas = inter = exc = 0.0
    for mes in meses:
        p = precios_vigentes(mes, catalogo)
        bas += p.basico
        inter += p.intermedio
        exc += p.excedente
        detalle.append(
            {
                "mes": mes.strftime("%Y-%m"),
                "fecha_tarifa": p.fecha_vigencia.isoformat(),
                "precios": {
                    "basico": p.basico,
                    "intermedio": p.intermedio,
                    "excedente": p.excedente,
                },
            }
        )
    n = len(meses)
    promedio = PreciosT01(
        fecha_vigencia=meses[0],
        basico=round(bas / n, 3),
        intermedio=round(inter / n, 3),
        excedente=round(exc / n, 3),
    )
    return promedio, detalle


def repartir_bloques(kwh: float) -> tuple[float, float, float]:
    """Reparte kWh en (basico, intermedio, excedente). kWh negativos → (0,0,0)."""
    restante = max(0.0, float(kwh))
    basico = min(restante, KWH_BASICO)
    restante -= basico
    intermedio = min(restante, KWH_INTERMEDIO)
    restante -= intermedio
    return basico, intermedio, restante


def calcular_pago(kwh: float, precios: PreciosT01) -> DesglosePagoT01:
    kb, ki, ke = repartir_bloques(kwh)
    ib = kb * precios.basico
    ii = ki * precios.intermedio
    ie = ke * precios.excedente
    return DesglosePagoT01(
        kwh=float(kwh),
        kwh_basico=kb,
        kwh_intermedio=ki,
        kwh_excedente=ke,
        precios=precios,
        importe_basico=ib,
        importe_intermedio=ii,
        importe_excedente=ie,
        total=ib + ii + ie,
    )


def _desglose_pago(pago: DesglosePagoT01) -> dict:
    return {
        "kwh": pago.kwh,
        "importe": pago.total,
        "escalones": {
            "basico": {
                "kwh": pago.kwh_basico,
                "importe": pago.importe_basico,
            },
            "intermedio": {
                "kwh": pago.kwh_intermedio,
                "importe": pago.importe_intermedio,
            },
            "excedente": {
                "kwh": pago.kwh_excedente,
                "importe": pago.importe_excedente,
            },
        },
    }


def promedio_mensual_equivalente(kwh: float, n_dias: int) -> float:
    """kWh/mes equivalentes = (kWh/días) × días promedio de mes."""
    if n_dias <= 0:
        return 0.0
    return (float(kwh) / float(n_dias)) * DIAS_MES_PROM


def _meta_dac(kwh: float, n_dias: int) -> dict:
    prom = promedio_mensual_equivalente(kwh, n_dias)
    return {
        "limite_kwh_mes": LIMITE_DAC_KWH_MES,
        "promedio_mensual_kwh": round(prom, 3),
        "supera_dac": prom > LIMITE_DAC_KWH_MES,
    }


def _resolver_precios(
    fecha_ini: date,
    fecha_fin: date,
    tarifas: list[PreciosT01],
) -> tuple[PreciosT01, list[dict] | None, str, str]:
    """Devuelve (precios, detalle_meses|None, metodo, fecha_tarifa_label)."""
    meses = meses_calendario(fecha_ini, fecha_fin)
    if len(meses) == 1:
        p = precios_vigentes(fecha_fin, tarifas)
        return p, None, "mes_unico", p.fecha_vigencia.isoformat()
    promedio, detalle = precios_promedio_periodo(fecha_ini, fecha_fin, tarifas)
    label = (
        f"{fecha_ini.isoformat()} → {fecha_fin.isoformat()} "
        f"(promedio {len(meses)} meses)"
    )
    return promedio, detalle, "promedio_meses_cfe", label


def _envelope_costo(
    *,
    consumo: dict,
    precios: PreciosT01,
    fecha_tarifa: str,
    metodo: str,
    n_dias: int,
    kwh_total: float,
    meses_promedio: list[dict] | None,
) -> dict:
    out = {
        "esquema": "T01",
        "titulo_tarifa": "Tarifa 01",
        "fecha_tarifa": fecha_tarifa,
        "precios": {
            "basico": precios.basico,
            "intermedio": precios.intermedio,
            "excedente": precios.excedente,
        },
        "etiquetas_escalones": (
            ("basico", "Básico"),
            ("intermedio", "Intermedio"),
            ("excedente", "Excedente"),
        ),
        "bloques_kwh": {"basico": KWH_BASICO, "intermedio": KWH_INTERMEDIO},
        "consumo": consumo,
        "metodo": metodo,
        "n_dias": n_dias,
        "dac": _meta_dac(kwh_total, n_dias),
    }
    if meses_promedio and len(meses_promedio) > 1:
        out["meses_promedio"] = meses_promedio
    return out


def calcular_ahorro(
    kwh_neteo: float,
    kwh_real: float,
    fecha_fin_periodo: str | date | datetime,
    tarifas: list[PreciosT01] | None = None,
    fecha_inicio_periodo: str | date | datetime | None = None,
) -> dict:
    """Costo Neteo / Real / ahorro con precios promedio CFE si cruza meses."""
    catalogo = tarifas if tarifas is not None else cargar_tarifas()
    fin = _parse_fecha(fecha_fin_periodo)
    ini = _parse_fecha(fecha_inicio_periodo) if fecha_inicio_periodo else fin
    if ini > fin:
        ini, fin = fin, ini
    n_dias = (fin - ini).days + 1
    precios, meses_det, metodo, fecha_tarifa = _resolver_precios(ini, fin, catalogo)

    neteo = _desglose_pago(calcular_pago(kwh_neteo, precios))
    real = _desglose_pago(calcular_pago(kwh_real, precios))

    out = {
        "esquema": "T01",
        "titulo_tarifa": "Tarifa 01",
        "fecha_tarifa": fecha_tarifa,
        "precios": {
            "basico": precios.basico,
            "intermedio": precios.intermedio,
            "excedente": precios.excedente,
        },
        "etiquetas_escalones": (
            ("basico", "Básico"),
            ("intermedio", "Intermedio"),
            ("excedente", "Excedente"),
        ),
        "bloques_kwh": {"basico": KWH_BASICO, "intermedio": KWH_INTERMEDIO},
        "neteo": neteo,
        "real": real,
        "ahorro": real["importe"] - neteo["importe"],
        "metodo": metodo,
        "n_dias": n_dias,
        "dac": _meta_dac(kwh_real, n_dias),
    }
    if meses_det and len(meses_det) > 1:
        out["meses_promedio"] = meses_det
    return out


def calcular_costo(
    kwh: float,
    fecha_fin_periodo: str | date | datetime,
    tarifas: list[PreciosT01] | None = None,
    fecha_inicio_periodo: str | date | datetime | None = None,
) -> dict:
    """Costo T01. Cruce de meses → promedio simple de precios; bloques sobre el total."""
    catalogo = tarifas if tarifas is not None else cargar_tarifas()
    fin = _parse_fecha(fecha_fin_periodo)
    ini = _parse_fecha(fecha_inicio_periodo) if fecha_inicio_periodo else fin
    if ini > fin:
        ini, fin = fin, ini
    n_dias = (fin - ini).days + 1
    precios, meses_det, metodo, fecha_tarifa = _resolver_precios(ini, fin, catalogo)
    pago = calcular_pago(kwh, precios)
    return _envelope_costo(
        consumo=_desglose_pago(pago),
        precios=precios,
        fecha_tarifa=fecha_tarifa,
        metodo=metodo,
        n_dias=n_dias,
        kwh_total=float(kwh),
        meses_promedio=meses_det,
    )
