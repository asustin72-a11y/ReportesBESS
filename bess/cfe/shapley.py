"""Participación de capacidad CFE (Shapley) por subestación."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from bess.cfe.capacity import FACTOR_CFE_CAPACIDAD, calcular_criterio2_cfe_kw
from bess.config import rutas as rutas_mod
from bess.config.subestaciones import (
    Subestacion,
    medidor_testigo_subestacion,
    subestacion_por_id,
)
from bess.core.consumo import kwh_neto_consumo
from bess.core.demand import demanda_rodante_15min_por_mes
from bess.core.numbers import redondear_arriba_kw, redondear_arriba_mxn
from bess.tariffs.loader import cargar_tarifas


@dataclass(frozen=True)
class ConfigParticipacionCapacidad:
    subestacion_id: str
    nombre: str
    prefijo_testigo: str
    ruta_combinado: Path
    ruta_generacion: Path
    columna_generacion: str
    etiqueta_generacion: str


class ParticipacionCapacidadError(Exception):
    """Datos insuficientes o inconsistentes para Shapley."""


def resolver_config_participacion(subestacion_id: str) -> ConfigParticipacionCapacidad | None:
    sub = subestacion_por_id(subestacion_id)
    testigo = medidor_testigo_subestacion(subestacion_id)
    if not sub or not testigo:
        return None

    ruta_combinado = rutas_mod.resolver_ruta_procesado(testigo.ruta_combinado())
    if not ruta_combinado.exists():
        legacy = rutas_mod.ruta_reporte(sub.id, testigo.ruta_combinado().name)
        ruta_combinado = legacy if legacy.exists() else ruta_combinado

    if sub.granja_csv:
        ruta_gen = sub.ruta_generacion_lectura()
        return ConfigParticipacionCapacidad(
            subestacion_id=sub.id,
            nombre=sub.nombre,
            prefijo_testigo=testigo.prefijo,
            ruta_combinado=ruta_combinado,
            ruta_generacion=ruta_gen,
            columna_generacion="KWH_REC",
            etiqueta_generacion="Generación granja solar",
        )

    if sub.cogeneracion_csv:
        ruta_cogen = sub.ruta_cogeneracion_lectura()
        if ruta_cogen is None:
            return None
        return ConfigParticipacionCapacidad(
            subestacion_id=sub.id,
            nombre=sub.nombre,
            prefijo_testigo=testigo.prefijo,
            ruta_combinado=ruta_combinado,
            ruta_generacion=ruta_cogen,
            columna_generacion="KWH_ENT",
            etiqueta_generacion="Cogeneración",
        )

    return None


def _cargar_generacion(ruta: Path, columna: str) -> pd.DataFrame:
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    col_fecha = "Fecha" if "Fecha" in df.columns else "FECHA_HORA"
    df["ts"] = pd.to_datetime(df[col_fecha])
    if col_fecha == "FECHA_HORA":
        df["ts"] = pd.to_datetime(df["FECHA_HORA"], format="%d/%m/%Y %H:%M", errors="coerce")
    df["E_gen_kWh"] = pd.to_numeric(df[columna], errors="coerce").fillna(0)
    return df[["ts", "E_gen_kWh"]]


def _filtrar_mes_hasta(df: pd.DataFrame, fecha_corte: date) -> pd.DataFrame:
    fechas = pd.to_datetime(df["FECHA"], format="%d/%m/%Y", errors="coerce")
    mask = (
        (fechas.dt.month == fecha_corte.month)
        & (fechas.dt.year == fecha_corte.year)
        & (fechas.dt.date <= fecha_corte)
    )
    return df.loc[mask].copy()


def _max_punta_rodada(calc: pd.DataFrame, col_kw: str) -> float:
    col_dem = f"{col_kw}_DEM15"
    punta = calc.loc[calc["PERIODO"] == "Punta", col_dem]
    if punta.empty:
        return 0.0
    return float(punta.max())


def _energia_mes(calc: pd.DataFrame, col_e: str) -> float:
    return float(pd.to_numeric(calc[col_e], errors="coerce").fillna(0).sum())


def _capacidad_cfe(punta_kw_raw: float, energia_kwh: float, dias: int) -> dict:
    c1 = redondear_arriba_kw(punta_kw_raw)
    c2 = redondear_arriba_kw(calcular_criterio2_cfe_kw(energia_kwh, dias))
    cap = min(c1, c2)
    return {
        "demanda_punta_kw": c1,
        "demanda_calculada_cfe_kw": c2,
        "capacidad_kw": cap,
        "criterio_aplicado": "punta" if c1 <= c2 else "factor_carga",
        "energia_kwh": energia_kwh,
    }


def calcular_participacion_capacidad(
    subestacion_id: str,
    fecha_corte: date,
    *,
    tarifas: dict | None = None,
) -> dict:
    """
    Shapley de capacidad CFE (kW y MXN) para generación/cogeneración vs BESS.

    Escenarios (kWh/5 min):
    D0 = ION + Gen + Descarga − Carga
    Dc = ION + Descarga − Carga
    Db = ION + Gen
    Dcb = ION
    """
    cfg = resolver_config_participacion(subestacion_id)
    if cfg is None:
        raise ParticipacionCapacidadError(
            f"La subestación {subestacion_id} no tiene generación configurada."
        )
    if not cfg.ruta_combinado.exists():
        raise ParticipacionCapacidadError(
            f"No existe combinado ION+BESS: {cfg.ruta_combinado.name}"
        )
    if not cfg.ruta_generacion.exists():
        raise ParticipacionCapacidadError(
            f"No existe perfil de {cfg.etiqueta_generacion.lower()}: "
            f"{cfg.ruta_generacion.name}"
        )

    if tarifas is None:
        tarifas = cargar_tarifas()
    tarifa_cap = float(tarifas.get("Capacidad", {}).get(fecha_corte.month, 0))
    dias = fecha_corte.day

    raw = pd.read_csv(cfg.ruta_combinado, encoding="utf-8-sig")
    raw = _filtrar_mes_hasta(raw, fecha_corte)
    if raw.empty:
        raise ParticipacionCapacidadError(
            f"Sin datos de {fecha_corte.strftime('%m/%Y')} hasta {fecha_corte:%d/%m/%Y}."
        )

    raw["ts"] = pd.to_datetime(raw["FECHA_HORA"], format="%d/%m/%Y %H:%M")

    gen = _cargar_generacion(cfg.ruta_generacion, cfg.columna_generacion)
    merged = raw.merge(gen, on="ts", how="left", validate="one_to_one")
    faltantes = int(merged["E_gen_kWh"].isna().sum())
    if faltantes:
        raise ParticipacionCapacidadError(
            f"Generación sin emparejar en {faltantes} intervalos de 5 min."
        )
    merged = merged.reset_index(drop=True)

    prefijo = cfg.prefijo_testigo
    e_ion = kwh_neto_consumo(merged, prefijo)
    bess_rec = pd.to_numeric(merged["KWH_REC_BESS"], errors="coerce").fillna(0)
    bess_ent = pd.to_numeric(merged["KWH_ENT_BESS"], errors="coerce").fillna(0)
    e_gen = merged["E_gen_kWh"]

    calc = merged.copy()
    mes_op = pd.to_datetime(calc["FECHA"], format="%d/%m/%Y").dt.to_period("M")

    calc["E_Dcb_kWh"] = e_ion
    calc["E_Dc_kWh"] = e_ion + bess_ent - bess_rec
    calc["E_Db_kWh"] = e_ion + e_gen
    calc["E_D0_kWh"] = e_ion + e_gen + bess_ent - bess_rec

    for esc, col_e in (
        ("Dcb", "E_Dcb_kWh"),
        ("Dc", "E_Dc_kWh"),
        ("Db", "E_Db_kWh"),
        ("D0", "E_D0_kWh"),
    ):
        calc[f"P_{esc}_kW"] = calc[col_e] * 12

    for col in ("P_Dcb_kW", "P_Dc_kW", "P_Db_kW", "P_D0_kW"):
        calc[f"{col}_DEM15"] = demanda_rodante_15min_por_mes(calc[col], mes_op)

    escenarios = {
        "D0": ("P_D0_kW", "E_D0_kWh", "Sin recursos"),
        "Dc": ("P_Dc_kW", "E_Dc_kWh", f"Solo {cfg.etiqueta_generacion.lower()}"),
        "Db": ("P_Db_kW", "E_Db_kWh", "Solo BESS"),
        "Dcb": ("P_Dcb_kW", "E_Dcb_kWh", "Con recursos"),
    }

    cfe: dict[str, dict] = {}
    punta_max: dict[str, int] = {}
    for clave, (col_p, col_e, _) in escenarios.items():
        punta_raw = _max_punta_rodada(calc, col_p)
        energia = _energia_mes(calc, col_e)
        res = _capacidad_cfe(punta_raw, energia, dias)
        res["costo_capacidad_mxn"] = redondear_arriba_mxn(res["capacidad_kw"] * tarifa_cap)
        cfe[clave] = res
        punta_max[clave] = res["demanda_punta_kw"]

    c0, cc, cb, ccb = (cfe[k]["capacidad_kw"] for k in ("D0", "Dc", "Db", "Dcb"))
    s_g_cap = (c0 - cc + cb - ccb) / 2
    s_b_cap = (c0 - cb + cc - ccb) / 2

    d0, dc, db, dcb = (punta_max[k] for k in ("D0", "Dc", "Db", "Dcb"))
    s_g_punta = (d0 - dc + db - dcb) / 2
    s_b_punta = (d0 - db + dc - dcb) / 2

    ahorro_kw = c0 - ccb
    ahorro_mxn = redondear_arriba_mxn(ahorro_kw * tarifa_cap)
    s_g_mxn = redondear_arriba_mxn(s_g_cap * tarifa_cap)
    s_b_mxn = redondear_arriba_mxn(s_b_cap * tarifa_cap)

    pct_g = (s_g_cap / ahorro_kw * 100) if ahorro_kw else 0.0
    pct_b = (s_b_cap / ahorro_kw * 100) if ahorro_kw else 0.0

    criterio_cfe = pd.DataFrame(
        [
            {
                "Escenario": escenarios[k][2],
                "Energía (kWh)": round(cfe[k]["energia_kwh"], 2),
                "Demanda punta (kW)": cfe[k]["demanda_punta_kw"],
                "DemandaCalculadaCFE (kW)": cfe[k]["demanda_calculada_cfe_kw"],
                "Capacidad CFE (kW)": cfe[k]["capacidad_kw"],
                "Criterio aplicado": cfe[k]["criterio_aplicado"],
                "Costo capacidad (MXN)": cfe[k]["costo_capacidad_mxn"],
            }
            for k in ("D0", "Dc", "Db", "Dcb")
        ]
    )

    shapley = pd.DataFrame(
        {
            "Concepto": [
                f"Tarifa capacidad ({fecha_corte.strftime('%m/%Y')}) ($/kW)",
                "",
                "Capacidad D0 (sin recursos)",
                f"Capacidad Dc (solo {cfg.etiqueta_generacion.lower()})",
                "Capacidad Db (solo BESS)",
                "Capacidad Dcb (con recursos)",
                "Reducción capacidad D0−Dcb (kW)",
                f"Shapley {cfg.etiqueta_generacion} (kW)",
                "Shapley BESS (kW)",
                "Ahorro capacidad total (MXN)",
                f"Shapley {cfg.etiqueta_generacion} (MXN)",
                "Shapley BESS (MXN)",
                f"Participación {cfg.etiqueta_generacion} (%)",
                "Participación BESS (%)",
            ],
            "Valor": [
                tarifa_cap,
                "",
                c0,
                cc,
                cb,
                ccb,
                ahorro_kw,
                round(s_g_cap, 2),
                round(s_b_cap, 2),
                ahorro_mxn,
                s_g_mxn,
                s_b_mxn,
                round(pct_g, 1),
                round(pct_b, 1),
            ],
        }
    )

    metodologia = pd.DataFrame(
        {
            "Concepto": [
                "Subestación",
                "Periodo",
                "Recurso de generación",
                "Criterio CFE capacidad",
                "Factor de carga",
                "Shapley (sobre capacidad CFE)",
                "Demanda rodante",
            ],
            "Detalle": [
                cfg.nombre,
                f"Acumulado al {fecha_corte:%d/%m/%Y} ({dias} días)",
                cfg.etiqueta_generacion,
                "Capacidad = min(Demanda punta rodada, DemandaCalculadaCFE)",
                f"DemandaCalculadaCFE = Energía / ({FACTOR_CFE_CAPACIDAD} × 24 × días)",
                "S_g = ((C0−Cc)+(Cb−Ccb))/2 ; S_b = ((C0−Cb)+(Cc−Ccb))/2",
                "15 min, reinicio mensual, 00:05/00:10 = 0",
            ],
        }
    )

    return {
        "config": cfg,
        "fecha_corte": fecha_corte,
        "tarifa_cap": tarifa_cap,
        "dias": dias,
        "cfe": cfe,
        "cap": {"d0": c0, "dc": cc, "db": cb, "dcb": ccb},
        "shapley_kw": {"generacion": s_g_cap, "bess": s_b_cap, "total": ahorro_kw},
        "shapley_mxn": {"generacion": s_g_mxn, "bess": s_b_mxn, "total": ahorro_mxn},
        "shapley_punta_kw": {"generacion": s_g_punta, "bess": s_b_punta},
        "participacion_pct": {"generacion": pct_g, "bess": pct_b},
        "criterio_cfe": criterio_cfe,
        "shapley": shapley,
        "metodologia": metodologia,
        "criterio_limitante": cfe["Dcb"]["criterio_aplicado"],
    }
