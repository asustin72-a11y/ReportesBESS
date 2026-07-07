"""Participación de capacidad CFE (Shapley) por subestación."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from bess.config.esquema_tarifa import esquema_tarifa_subestacion, factor_cfe_capacidad
from bess.cfe.capacity import calcular_criterio2_cfe_kw
from bess.config.subestaciones import (
    Subestacion,
    medidor_testigo_subestacion,
    subestacion_por_id,
)
from bess.core.consumo import kwh_neto_consumo
from bess.core.demand import demanda_rodante_15min_por_mes
from bess.core.numbers import redondear_arriba_kw, redondear_mxn_energia
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

    ruta_combinado = testigo.ruta_combinado()

    if sub.granja_csv:
        ruta_gen = sub.ruta_generacion_lectura()
        return ConfigParticipacionCapacidad(
            subestacion_id=sub.id,
            nombre=sub.nombre,
            prefijo_testigo=testigo.prefijo,
            ruta_combinado=ruta_combinado,
            ruta_generacion=ruta_gen,
            columna_generacion="KWH_REC",
            etiqueta_generacion="Generación",
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
            etiqueta_generacion="Generación",
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


def _capacidad_cfe(
    punta_kw_raw: float,
    energia_kwh: float,
    dias: int,
    esquema_tarifa_id: str,
) -> dict:
    c1 = redondear_arriba_kw(punta_kw_raw)
    c2 = redondear_arriba_kw(
        calcular_criterio2_cfe_kw(energia_kwh, dias, esquema_tarifa_id=esquema_tarifa_id)
    )
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
    Shapley de capacidad CFE (kW y MXN) para generación vs BESS.

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
        tarifas = cargar_tarifas(esquema_tarifa_subestacion(subestacion_id))
    esquema = esquema_tarifa_subestacion(subestacion_id)
    tarifa_cap = redondear_mxn_energia(
        float(tarifas.get("Capacidad", {}).get(fecha_corte.month, 0))
    )
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
        res = _capacidad_cfe(punta_raw, energia, dias, esquema)
        res["costo_capacidad_mxn"] = redondear_mxn_energia(res["capacidad_kw"] * tarifa_cap)
        cfe[clave] = res
        punta_max[clave] = res["demanda_punta_kw"]

    c0, cc, cb, ccb = (cfe[k]["capacidad_kw"] for k in ("D0", "Dc", "Db", "Dcb"))
    c0_mxn, cc_mxn, cb_mxn, ccb_mxn = (
        cfe[k]["costo_capacidad_mxn"] for k in ("D0", "Dc", "Db", "Dcb")
    )

    # Shapley sobre capacidad (kW) — referencia técnica (demanda: ceil al entero)
    s_g_cap = redondear_arriba_kw((c0 - cc + cb - ccb) / 2)
    s_b_cap = redondear_arriba_kw((c0 - cb + cc - ccb) / 2)

    # Shapley sobre costo de capacidad (MXN) — atribución en dinero
    ahorro_mxn = redondear_mxn_energia(c0_mxn - ccb_mxn)
    s_g_mxn = redondear_mxn_energia((c0_mxn - cc_mxn + cb_mxn - ccb_mxn) / 2)
    s_b_mxn = redondear_mxn_energia((c0_mxn - cb_mxn + cc_mxn - ccb_mxn) / 2)

    ahorro_kw = c0 - ccb
    ahorro_mxn_kw = redondear_mxn_energia(ahorro_kw * tarifa_cap)

    d0, dc, db, dcb = (punta_max[k] for k in ("D0", "Dc", "Db", "Dcb"))
    s_g_punta = redondear_arriba_kw((d0 - dc + db - dcb) / 2)
    s_b_punta = redondear_arriba_kw((d0 - db + dc - dcb) / 2)

    pct_g = (s_g_mxn / ahorro_mxn * 100) if ahorro_mxn else 0.0
    pct_b = (s_b_mxn / ahorro_mxn * 100) if ahorro_mxn else 0.0
    pct_g_kw = (s_g_cap / ahorro_kw * 100) if ahorro_kw else 0.0
    pct_b_kw = (s_b_cap / ahorro_kw * 100) if ahorro_kw else 0.0

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

    shapley_mxn = pd.DataFrame(
        {
            "Concepto": [
                f"Tarifa capacidad ({fecha_corte.strftime('%m/%Y')}) ($/kW)",
                "",
                "Costo capacidad D0 (sin recursos)",
                f"Costo capacidad Dc (solo {cfg.etiqueta_generacion.lower()})",
                "Costo capacidad Db (solo BESS)",
                "Costo capacidad Dcb (con recursos)",
                "Ahorro capacidad D0−Dcb (MXN)",
                f"Shapley {cfg.etiqueta_generacion} (MXN)",
                "Shapley BESS (MXN)",
                f"Participación {cfg.etiqueta_generacion} (%)",
                "Participación BESS (%)",
            ],
            "Valor": [
                f"${tarifa_cap:,.2f}",
                "",
                f"${c0_mxn:,.2f}",
                f"${cc_mxn:,.2f}",
                f"${cb_mxn:,.2f}",
                f"${ccb_mxn:,.2f}",
                f"${ahorro_mxn:,.2f}",
                f"${s_g_mxn:,.2f}",
                f"${s_b_mxn:,.2f}",
                f"{pct_g:.1f} %",
                f"{pct_b:.1f} %",
            ],
        }
    )

    shapley_kw = pd.DataFrame(
        {
            "Concepto": [
                "",
                "Capacidad D0 (sin recursos)",
                f"Capacidad Dc (solo {cfg.etiqueta_generacion.lower()})",
                "Capacidad Db (solo BESS)",
                "Capacidad Dcb (con recursos)",
                "Reducción capacidad D0−Dcb (kW)",
                f"Shapley {cfg.etiqueta_generacion} (kW)",
                "Shapley BESS (kW)",
                f"Participación {cfg.etiqueta_generacion} (%)",
                "Participación BESS (%)",
                "",
                "Referencia — solo demanda punta (sin criterio CFE)",
                f"Shapley {cfg.etiqueta_generacion} punta (kW)",
                "Shapley BESS punta (kW)",
            ],
            "Valor": [
                "",
                f"{c0:,}",
                f"{cc:,}",
                f"{cb:,}",
                f"{ccb:,}",
                f"{ahorro_kw:,}",
                f"{s_g_cap:,}",
                f"{s_b_cap:,}",
                f"{pct_g_kw:.1f} %",
                f"{pct_b_kw:.1f} %",
                "",
                "",
                f"{s_g_punta:,}",
                f"{s_b_punta:,}",
            ],
        }
    )

    shapley = shapley_mxn

    participantes = pd.DataFrame(
        [
            {
                "Participante": "Total (reducción D0 − Dcb)",
                "Ahorro capacidad (kW)": f"{ahorro_kw:,}",
                "Ahorro (MXN)": f"${ahorro_mxn:,.2f}",
                "Participación": "100.0 %",
            },
            {
                "Participante": cfg.etiqueta_generacion,
                "Ahorro capacidad (kW)": f"{s_g_cap:,}",
                "Ahorro (MXN)": f"${s_g_mxn:,.2f}",
                "Participación": f"{pct_g:.1f} %",
            },
            {
                "Participante": "BESS",
                "Ahorro capacidad (kW)": f"{s_b_cap:,}",
                "Ahorro (MXN)": f"${s_b_mxn:,.2f}",
                "Participación": f"{pct_b:.1f} %",
            },
        ]
    )

    metodologia = pd.DataFrame(
        {
            "Concepto": [
                "Subestación",
                "Periodo",
                "Recurso de generación",
                "Criterio CFE capacidad",
                "Factor de carga",
                "Shapley (sobre costo capacidad CFE en MXN)",
                "Shapley kW (referencia técnica)",
                "Demanda rodante",
                "Redondeo demanda (kW)",
                "Redondeo dinero (MXN)",
            ],
            "Detalle": [
                cfg.nombre,
                f"Acumulado al {fecha_corte:%d/%m/%Y} ({dias} días)",
                cfg.etiqueta_generacion,
                "Capacidad = min(Demanda punta rodada, DemandaCalculadaCFE)",
                f"DemandaCalculadaCFE = Energía / ({factor_cfe_capacidad(esquema)} × 24 × días)",
                "S_g = ((C0−Cc)+(Cb−Ccb))/2 ; S_b = ((C0−Cb)+(Cc−Ccb))/2 (costos MXN)",
                "Equivalente en kW con tarifa del mes",
                "15 min, reinicio mensual, 00:05/00:10 = 0",
                "Cualquier decimal en demanda (kW) → entero superior (ceil)",
                "Dinero (MXN): ≥0.5 al entero superior, <0.5 hacia abajo (2 decimales)",
            ],
        }
    )

    return {
        "config": cfg,
        "fecha_corte": fecha_corte,
        "tarifa_cap": tarifa_cap,
        "dias": dias,
        "cfe": cfe,
        "costo": {"d0": c0_mxn, "dc": cc_mxn, "db": cb_mxn, "dcb": ccb_mxn},
        "cap": {"d0": c0, "dc": cc, "db": cb, "dcb": ccb},
        "shapley_kw": {"generacion": s_g_cap, "bess": s_b_cap, "total": ahorro_kw},
        "shapley_mxn": {"generacion": s_g_mxn, "bess": s_b_mxn, "total": ahorro_mxn},
        "shapley_mxn_ref": {"total": ahorro_mxn_kw},
        "shapley_punta_kw": {"generacion": s_g_punta, "bess": s_b_punta},
        "participacion_pct": {"generacion": pct_g, "bess": pct_b},
        "participacion_pct_kw": {"generacion": pct_g_kw, "bess": pct_b_kw},
        "criterio_cfe": criterio_cfe,
        "shapley": shapley,
        "shapley_mxn_tabla": shapley_mxn,
        "shapley_kw_tabla": shapley_kw,
        "participantes": participantes,
        "metodologia": metodologia,
        "criterio_limitante": cfe["Dcb"]["criterio_aplicado"],
    }
