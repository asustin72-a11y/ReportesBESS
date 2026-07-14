"""Huella de carbono (Scope 2) por periodo tarifario — consumo red ± BESS y generación."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from bess.config.esquema_tarifa import esquema_tarifa_prefijo, usa_netmetering
from bess.config.subestaciones import (
    recurso_generacion_subestacion,
    ruta_energia_dia_por_prefijo,
    subestacion_por_prefijo,
)
from bess.core.energia_periodo import (
    PERIODOS,
    sumar_consumo_por_periodo_df,
    sumar_ent_por_periodo_df,
    sumar_rec_por_periodo_df,
)
from bess.cfe.daily_data import energia_diaria_tiene_sin_bess
from bess.cfe.report_data import dias_transcurridos_mes
from bess.data.aggregates.generacion import sumar_generacion_por_periodo

# kg CO2/kWh por periodo tarifario (escenario operativo del reporte).
# Origen: hipótesis de intensidad marginal relativa punta–base del análisis de
# huella BESS IUSASOL (jul 2026); no es el factor oficial único de la red MX.
FACTORES_EMISION = {
    "id": "marcado",
    "etiqueta": "Marcado 0.30 / 0.45 / 0.65",
    "base": 0.30,
    "intermedio": 0.45,
    "punta": 0.65,
}

# Cogeneración (gas): escenario plano — un solo EF, independiente del periodo.
EF_GAS_PLANO_KG_KWH = 0.45

CITA_FACTORES_EMISION = (
    "Factores de emisión de red (kg CO₂/kWh): Base 0.30 · Intermedio 0.45 · Punta 0.65 "
    "(escenario «Marcado», análisis huella BESS IUSASOL, julio 2026). "
    "Cogeneración (gas): escenario plano EF = 0.45 kg CO₂/kWh para emisiones locales; "
    "se compara contra las emisiones de red Marcado que se generarían si esos kWh "
    "se consumieran de la red (CO₂ neto = CO₂ red − CO₂ gas plano)."
)

# Compatibilidad: un solo escenario activo
ESCENARIOS_EF: dict[str, dict[str, Any]] = {
    FACTORES_EMISION["id"]: dict(FACTORES_EMISION),
}
ESCENARIO_DEFAULT = FACTORES_EMISION["id"]
ETIQUETA_PERIODO = {"base": "Base", "intermedio": "Intermedio", "punta": "Punta"}

# Fuente energética para el reporte de emisiones (no confundir con tipo de medidor API).
# IUSA 1: cogeneración a gas; IUSA 2 y Aragón: granja solar.
_FUENTE_GENERACION_SUB: dict[str, tuple[str, str]] = {
    "IUSA_1": ("gas", "Cogeneración (gas)"),
    "IUSA_2": ("solar", "Granja solar"),
    "IUSA_ARAGON": ("solar", "Granja solar"),
}


def _etiqueta_fuente_generacion(sub_id: str, recurso) -> tuple[str | None, str | None]:
    """(tipo, etiqueta) para UI/PDF: gas | solar."""
    if not recurso:
        return None, None
    if sub_id in _FUENTE_GENERACION_SUB:
        return _FUENTE_GENERACION_SUB[sub_id]
    if recurso.tipo == "cogeneracion":
        return "gas", "Cogeneración (gas)"
    return "solar", "Granja solar"


@dataclass(frozen=True)
class FactoresEmision:
    base: float
    intermedio: float
    punta: float

    def as_dict(self) -> dict[str, float]:
        return {"base": self.base, "intermedio": self.intermedio, "punta": self.punta}


def factores_de_escenario(escenario_id: str) -> FactoresEmision:
    esc = ESCENARIOS_EF.get(escenario_id) or ESCENARIOS_EF[ESCENARIO_DEFAULT]
    return FactoresEmision(
        base=float(esc["base"]),
        intermedio=float(esc["intermedio"]),
        punta=float(esc["punta"]),
    )


def co2_toneladas(kwh_por_periodo: dict[str, float], ef: FactoresEmision | dict[str, float]) -> float:
    """Σ (kWh × kgCO2/kWh) → t CO2."""
    factores = ef.as_dict() if isinstance(ef, FactoresEmision) else ef
    total_kg = sum(float(kwh_por_periodo.get(p, 0) or 0) * float(factores[p]) for p in PERIODOS)
    return total_kg / 1000.0


def _cargar_energia_mes(fecha, prefijo: str) -> pd.DataFrame | None:
    ruta_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return None
    df = pd.read_csv(ruta_p, encoding="utf-8-sig")
    if "FECHA" not in df.columns:
        return None
    df["FECHA_DT"] = pd.to_datetime(df["FECHA"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["FECHA_DT"])
    inicio = fecha.replace(day=1)
    mask = (df["FECHA_DT"].dt.date >= inicio) & (df["FECHA_DT"].dt.date <= fecha)
    df_r = df[mask]
    return None if df_r.empty else df_r


def _total(d: dict[str, float]) -> float:
    return sum(float(d.get(p, 0) or 0) for p in PERIODOS)


def calcular_huella_carbono_mes(
    fecha,
    prefijo: str,
    *,
    escenario_id: str = ESCENARIO_DEFAULT,
) -> dict[str, Any] | None:
    """
    Huella mensual al día de corte.

    - Consumo con BESS: netmetering REC−ENT o REC según esquema.
    - Consumo sin BESS: columnas *_SIN_BESS si existen.
    - Generación: ENERGIA_Generacion_{sub}_POR_DIA (si hay recurso).
    - Si esos kWh vinieran de la red: gen × EF Marcado por periodo.
    - Cogeneración (gas): emisiones locales con EF plano 0.45 kg CO₂/kWh.
    - Solar: emisiones locales = 0. Neto = CO₂ red − CO₂ local.
    """
    escenario_id = ESCENARIO_DEFAULT
    df = _cargar_energia_mes(fecha, prefijo)
    if df is None:
        return None

    esquema = esquema_tarifa_prefijo(prefijo)
    sub = subestacion_por_prefijo(prefijo)
    sub_id = sub.id if sub else ""
    ef = factores_de_escenario(escenario_id)
    esc_meta = ESCENARIOS_EF[ESCENARIO_DEFAULT]

    consumo_con = sumar_consumo_por_periodo_df(df, esquema, con_bess=True)
    tiene_sin = energia_diaria_tiene_sin_bess(prefijo)
    consumo_sin = (
        sumar_consumo_por_periodo_df(df, esquema, con_bess=False) if tiene_sin else None
    )
    rec = sumar_rec_por_periodo_df(df)
    ent = sumar_ent_por_periodo_df(df) if usa_netmetering(esquema) else {p: 0.0 for p in PERIODOS}

    gen = {p: 0.0 for p in PERIODOS}
    tiene_gen = False
    gen_tipo = None
    gen_etiqueta = None
    recurso = recurso_generacion_subestacion(sub_id) if sub_id else None
    if recurso:
        gen_raw = sumar_generacion_por_periodo(sub_id, fecha.replace(day=1), fecha)
        if gen_raw is not None:
            gen = {p: float(gen_raw.get(p, 0) or 0) for p in PERIODOS}
            tiene_gen = True
            gen_tipo, gen_etiqueta = _etiqueta_fuente_generacion(sub_id, recurso)

    t_con = co2_toneladas(consumo_con, ef)
    t_sin = co2_toneladas(consumo_sin, ef) if consumo_sin is not None else None
    # Emisiones de red si esos kWh se tomaran de la red (Marcado por periodo)
    t_gen_desplazado = co2_toneladas(gen, ef) if tiene_gen else 0.0
    # Cogeneración: escenario plano (un solo EF, independiente del periodo)
    total_gen_kwh = _total(gen) if tiene_gen else 0.0
    if tiene_gen and gen_tipo == "gas":
        t_gen_local = total_gen_kwh * EF_GAS_PLANO_KG_KWH / 1000.0
    else:
        t_gen_local = 0.0
    t_gen_neto = t_gen_desplazado - t_gen_local
    t_gen_neto_pct = None
    if tiene_gen and t_gen_desplazado > 0:
        t_gen_neto_pct = 100.0 * t_gen_neto / t_gen_desplazado
    ahorro_bess = (t_sin - t_con) if t_sin is not None else None
    ahorro_bess_pct = None
    if t_sin is not None and t_sin > 0 and ahorro_bess is not None:
        ahorro_bess_pct = 100.0 * ahorro_bess / t_sin

    por_periodo = []
    for p in PERIODOS:
        co2_con_p = float(consumo_con.get(p, 0) or 0) * float(ef.as_dict()[p]) / 1000.0
        gen_kwh_p = float(gen.get(p, 0) or 0)
        ef_p = float(ef.as_dict()[p])
        co2_desp_p = gen_kwh_p * ef_p / 1000.0
        co2_local_p = (
            gen_kwh_p * EF_GAS_PLANO_KG_KWH / 1000.0 if gen_tipo == "gas" else 0.0
        )
        co2_neto_p = co2_desp_p - co2_local_p
        fila = {
            "periodo": p,
            "etiqueta": ETIQUETA_PERIODO[p],
            "consumo_con_kwh": float(consumo_con.get(p, 0) or 0),
            "rec_kwh": float(rec.get(p, 0) or 0),
            "ent_kwh": float(ent.get(p, 0) or 0),
            "generacion_kwh": gen_kwh_p,
            "ef_kg_kwh": ef_p,
            "ef_gas_plano_kg_kwh": EF_GAS_PLANO_KG_KWH if gen_tipo == "gas" else None,
            "co2_con_t": round(co2_con_p, 2),
            "co2_gen_desplazado_t": round(co2_desp_p, 2),
            "co2_gen_local_t": round(co2_local_p, 2),
            "co2_gen_neto_t": round(co2_neto_p, 2),
            "co2_gen_neto_pct": (
                round(100.0 * co2_neto_p / co2_desp_p, 2) if co2_desp_p > 0 else None
            ),
        }
        if consumo_sin is not None:
            co2_sin_p = float(consumo_sin.get(p, 0) or 0) * ef_p / 1000.0
            delta_p = co2_sin_p - co2_con_p
            fila["consumo_sin_kwh"] = float(consumo_sin.get(p, 0) or 0)
            fila["co2_sin_t"] = round(co2_sin_p, 2)
            fila["ahorro_t"] = round(delta_p, 2)
            fila["ahorro_pct"] = (
                round(100.0 * delta_p / co2_sin_p, 2) if co2_sin_p > 0 else None
            )
        por_periodo.append(fila)

    comparacion = []
    for sid, meta in ESCENARIOS_EF.items():
        ef_i = factores_de_escenario(sid)
        con_i = co2_toneladas(consumo_con, ef_i)
        sin_i = co2_toneladas(consumo_sin, ef_i) if consumo_sin is not None else None
        desp_i = co2_toneladas(gen, ef_i) if tiene_gen else 0.0
        local_i = (
            total_gen_kwh * EF_GAS_PLANO_KG_KWH / 1000.0
            if (tiene_gen and gen_tipo == "gas")
            else 0.0
        )
        ahorro_i = (sin_i - con_i) if sin_i is not None else None
        pct_i = (
            100.0 * ahorro_i / sin_i
            if sin_i is not None and sin_i > 0 and ahorro_i is not None
            else None
        )
        comparacion.append(
            {
                "id": sid,
                "etiqueta": meta["etiqueta"],
                "con_bess_t": round(con_i, 2),
                "sin_bess_t": round(sin_i, 2) if sin_i is not None else None,
                "ahorro_bess_t": round(ahorro_i, 2) if ahorro_i is not None else None,
                "ahorro_bess_pct": round(pct_i, 2) if pct_i is not None else None,
                "gen_evitada_t": round(desp_i - local_i, 2),
                "gen_desplazado_t": round(desp_i, 2),
                "gen_local_t": round(local_i, 2),
                "activo": sid == esc_meta["id"],
            }
        )

    return {
        "fecha": fecha,
        "fecha_inicio": fecha.replace(day=1),
        "prefijo": prefijo,
        "subestacion_id": sub_id,
        "subestacion_nombre": sub.nombre if sub else prefijo,
        "esquema": esquema,
        "netmetering": usa_netmetering(esquema),
        "dias_mes": dias_transcurridos_mes(fecha),
        "escenario_id": esc_meta["id"],
        "escenario_etiqueta": esc_meta["etiqueta"],
        "cita_factores": CITA_FACTORES_EMISION,
        "factores": ef.as_dict(),
        "factores_gas": (
            {"plano": EF_GAS_PLANO_KG_KWH} if gen_tipo == "gas" else None
        ),
        "tiene_sin_bess": tiene_sin,
        "tiene_generacion": tiene_gen,
        "generacion_tipo": gen_tipo,
        "generacion_etiqueta": gen_etiqueta,
        "consumo_con_kwh": consumo_con,
        "consumo_sin_kwh": consumo_sin,
        "rec_kwh": rec,
        "ent_kwh": ent,
        "generacion_kwh": gen,
        "total_consumo_con_kwh": _total(consumo_con),
        "total_consumo_sin_kwh": _total(consumo_sin) if consumo_sin else None,
        "total_generacion_kwh": _total(gen),
        "co2_con_t": round(t_con, 2),
        "co2_sin_t": round(t_sin, 2) if t_sin is not None else None,
        "ahorro_bess_t": round(ahorro_bess, 2) if ahorro_bess is not None else None,
        "ahorro_bess_pct": round(ahorro_bess_pct, 2) if ahorro_bess_pct is not None else None,
        # Compatibilidad: "evitada" = beneficio neto de generación
        "co2_gen_evitada_t": round(t_gen_neto, 2),
        "co2_gen_desplazado_t": round(t_gen_desplazado, 2),
        "co2_gen_local_t": round(t_gen_local, 2),
        "co2_gen_neto_t": round(t_gen_neto, 2),
        "co2_gen_neto_pct": (
            round(t_gen_neto_pct, 2) if t_gen_neto_pct is not None else None
        ),
        "por_periodo": por_periodo,
        "comparacion_escenarios": comparacion,
    }
