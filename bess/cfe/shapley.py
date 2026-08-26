"""Participación de capacidad CFE (Shapley) por subestación.

Participantes = cada recurso de generación (granja / tipo 5) + BESS.
Con cogeneración + solar individual: 3 jugadores y 8 coaliciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import combinations
from math import factorial
from pathlib import Path

import pandas as pd

from bess.config.esquema_tarifa import esquema_tarifa_subestacion, factor_cfe_capacidad
from bess.cfe.capacity import calcular_criterio2_cfe_kw
from bess.config.subestaciones import (
    medidor_testigo_subestacion,
    subestacion_por_id,
)
from bess.core.consumo import kwh_neto_consumo
from bess.core.demand import (
    aplicar_mascara_demanda_maximo,
    demanda_rodante_15min_por_mes,
)
from bess.core.numbers import redondear_arriba_kw, redondear_kw, redondear_mxn_energia
from bess.data.aggregates.generacion import fuente_energetica_medidor
from bess.tariffs.loader import cargar_tarifas

PLAYER_BESS = "bess"


@dataclass(frozen=True)
class FuenteGenParticipacion:
    clave: str
    etiqueta: str
    ruta: Path
    columna: str


@dataclass(frozen=True)
class ConfigParticipacionCapacidad:
    subestacion_id: str
    nombre: str
    prefijo_testigo: str
    ruta_combinado: Path
    fuentes_generacion: tuple[FuenteGenParticipacion, ...]

    @property
    def etiqueta_generacion(self) -> str:
        if len(self.fuentes_generacion) == 1:
            return self.fuentes_generacion[0].etiqueta
        return "Generación"

    @property
    def ruta_generacion(self) -> Path:
        return self.fuentes_generacion[0].ruta

    @property
    def columna_generacion(self) -> str:
        return self.fuentes_generacion[0].columna

    @property
    def etiquetas_participantes(self) -> tuple[str, ...]:
        return tuple(f.etiqueta for f in self.fuentes_generacion) + ("BESS",)


class ParticipacionCapacidadError(Exception):
    """Datos insuficientes o inconsistentes para Shapley."""


def _etiqueta_fuente(nombre_medidor: str | None, *, granja: bool) -> str:
    if granja:
        return "Generación"
    tipo, etiqueta = fuente_energetica_medidor(nombre_medidor or "")
    if tipo == "gas":
        return "Cogeneración"
    if nombre_medidor:
        return nombre_medidor.replace("_", " ")
    return etiqueta


def resolver_config_participacion(subestacion_id: str) -> ConfigParticipacionCapacidad | None:
    sub = subestacion_por_id(subestacion_id)
    testigo = medidor_testigo_subestacion(subestacion_id)
    if not sub or not testigo:
        return None

    fuentes: list[FuenteGenParticipacion] = []

    if sub.granja_csv:
        fuentes.append(
            FuenteGenParticipacion(
                clave="granja",
                etiqueta=_etiqueta_fuente(None, granja=True),
                ruta=sub.ruta_generacion_lectura(),
                columna="KWH_REC",
            )
        )

    for gen in sub.medidores_gen_individual:
        fuentes.append(
            FuenteGenParticipacion(
                clave=gen.nombre,
                etiqueta=_etiqueta_fuente(gen.nombre, granja=False),
                ruta=sub.ruta_gen_individual_lectura(gen),
                columna="KWH_ENT",
            )
        )

    if not fuentes:
        return None

    return ConfigParticipacionCapacidad(
        subestacion_id=sub.id,
        nombre=sub.nombre,
        prefijo_testigo=testigo.prefijo,
        ruta_combinado=testigo.ruta_combinado(),
        fuentes_generacion=tuple(fuentes),
    )


def _cargar_generacion(ruta: Path, columna: str) -> pd.DataFrame:
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    col_fecha = "Fecha" if "Fecha" in df.columns else "FECHA_HORA"
    if col_fecha == "FECHA_HORA":
        df["ts"] = pd.to_datetime(df["FECHA_HORA"], format="%d/%m/%Y %H:%M", errors="coerce")
    else:
        df["ts"] = pd.to_datetime(df[col_fecha])
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
    enmascarada = aplicar_mascara_demanda_maximo(calc[col_dem], calc["PERIODO"])
    punta = enmascarada.loc[calc["PERIODO"] == "Punta"]
    if punta.dropna().empty:
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


def _peso_shapley(tam_coalicion: int, n: int) -> float:
    return factorial(tam_coalicion) * factorial(n - tam_coalicion - 1) / factorial(n)


def _shapley_valores(
    valor: dict[frozenset[str], float],
    jugadores: tuple[str, ...],
) -> dict[str, float]:
    """φ_i = Σ_{S ⊆ N\\{i}} |S|!(n-|S|-1)!/n! · (v(S∪{i}) − v(S))."""
    n = len(jugadores)
    phi = {j: 0.0 for j in jugadores}
    for jugador in jugadores:
        otros = [j for j in jugadores if j != jugador]
        for r in range(len(otros) + 1):
            for subset in combinations(otros, r):
                s = frozenset(subset)
                peso = _peso_shapley(r, n)
                phi[jugador] += peso * (valor[s | {jugador}] - valor[s])
    return phi


def _etiqueta_coalicion(
    coalicion: frozenset[str],
    etiquetas: dict[str, str],
    jugadores: tuple[str, ...],
) -> str:
    if not coalicion:
        return "Sin recursos"
    if coalicion == frozenset(jugadores):
        return "Con todos los recursos"
    if len(coalicion) == 1:
        clave = next(iter(coalicion))
        return f"Solo {etiquetas[clave]}"
    nombres = [etiquetas[j] for j in jugadores if j in coalicion]
    return " + ".join(nombres)


def _codigo_coalicion(coalicion: frozenset[str], jugadores: tuple[str, ...]) -> str:
    if not coalicion:
        return "∅"
    if coalicion == frozenset(jugadores):
        return "N"
    indices = [str(i + 1) for i, j in enumerate(jugadores) if j in coalicion]
    return "{" + ",".join(indices) + "}"


def calcular_participacion_capacidad(
    subestacion_id: str,
    fecha_corte: date,
    *,
    tarifas: dict | None = None,
) -> dict:
    """
    Shapley de capacidad CFE (kW y MXN) entre recursos de generación y BESS.

    Valor de coalición S ⊆ N: capacidad CFE al reconstruir la demanda sumando
    al ION las contribuciones de los recursos en S (quitar su ayuda al medidor).
    Ahorro total = v(N) − v(∅).
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
    faltan = [f for f in cfg.fuentes_generacion if not f.ruta.exists()]
    if len(faltan) == len(cfg.fuentes_generacion):
        nombres = ", ".join(f.ruta.name for f in cfg.fuentes_generacion)
        raise ParticipacionCapacidadError(
            f"No existe perfil de generación: {nombres}"
        )
    if faltan:
        raise ParticipacionCapacidadError(
            "Faltan perfiles de generación para Shapley: "
            + ", ".join(f.etiqueta for f in faltan)
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
    merged = raw.reset_index(drop=True)

    contrib: dict[str, pd.Series] = {}
    etiquetas: dict[str, str] = {}

    for fuente in cfg.fuentes_generacion:
        gen = _cargar_generacion(fuente.ruta, fuente.columna)
        m = merged.merge(gen, on="ts", how="left", validate="one_to_one")
        faltantes = int(m["E_gen_kWh"].isna().sum())
        if faltantes:
            raise ParticipacionCapacidadError(
                f"{fuente.etiqueta}: sin emparejar en {faltantes} intervalos de 5 min."
            )
        contrib[fuente.clave] = m["E_gen_kWh"].fillna(0)
        etiquetas[fuente.clave] = fuente.etiqueta

    prefijo = cfg.prefijo_testigo
    e_ion = kwh_neto_consumo(merged, prefijo)
    bess_rec = pd.to_numeric(merged["KWH_REC_BESS"], errors="coerce").fillna(0)
    bess_ent = pd.to_numeric(merged["KWH_ENT_BESS"], errors="coerce").fillna(0)
    contrib[PLAYER_BESS] = bess_ent - bess_rec
    etiquetas[PLAYER_BESS] = "BESS"

    jugadores = tuple(f.clave for f in cfg.fuentes_generacion) + (PLAYER_BESS,)
    n = len(jugadores)

    if "PERIODO" not in merged.columns:
        raise ParticipacionCapacidadError(
            "El combinado no trae columna PERIODO; regenerar reportes."
        )
    if "FECHA" in merged.columns:
        mes_op = pd.to_datetime(
            merged["FECHA"], format="%d/%m/%Y", errors="coerce"
        ).dt.strftime("%Y-%m")
    else:
        mes_op = pd.to_datetime(
            merged["FECHA_HORA"], format="%d/%m/%Y %H:%M", errors="coerce"
        ).dt.strftime("%Y-%m")

    calc = merged.copy()
    cfe: dict[frozenset[str], dict] = {}
    punta_max: dict[frozenset[str], int] = {}
    orden_coaliciones: list[frozenset[str]] = []

    for r in range(n + 1):
        for subset in combinations(jugadores, r):
            coalicion = frozenset(subset)
            orden_coaliciones.append(coalicion)
            e = e_ion.copy()
            for clave in coalicion:
                e = e + contrib[clave]
            idx = len(orden_coaliciones) - 1
            col_e = f"E_coal_{idx}_kWh"
            col_p = f"P_coal_{idx}_kW"
            calc[col_e] = e
            calc[col_p] = e * 12
            calc[f"{col_p}_DEM15"] = demanda_rodante_15min_por_mes(calc[col_p], mes_op)

            punta_raw = _max_punta_rodada(calc, col_p)
            energia = _energia_mes(calc, col_e)
            res = _capacidad_cfe(punta_raw, energia, dias, esquema)
            res["costo_capacidad_mxn"] = redondear_mxn_energia(
                res["capacidad_kw"] * tarifa_cap
            )
            res["col_e"] = col_e
            res["col_p"] = col_p
            res["etiqueta"] = _etiqueta_coalicion(coalicion, etiquetas, jugadores)
            res["codigo"] = _codigo_coalicion(coalicion, jugadores)
            cfe[coalicion] = res
            punta_max[coalicion] = res["demanda_punta_kw"]

    vacio = frozenset()
    pleno = frozenset(jugadores)
    v_cap = {s: float(cfe[s]["capacidad_kw"]) for s in cfe}
    v_mxn = {s: float(cfe[s]["costo_capacidad_mxn"]) for s in cfe}
    v_punta = {s: float(punta_max[s]) for s in punta_max}

    phi_cap_raw = _shapley_valores(v_cap, jugadores)
    phi_mxn_raw = _shapley_valores(v_mxn, jugadores)
    phi_punta_raw = _shapley_valores(v_punta, jugadores)

    # Aportación por participante en kW: 3 decimales (no ceil).
    # El total N−∅ sigue en enteros de capacidad CFE; ceil por jugador
    # hacía que la suma de tarjetas superara el ahorro total.
    phi_cap = {j: redondear_kw(phi_cap_raw[j], 3) for j in jugadores}
    phi_mxn = {j: redondear_mxn_energia(phi_mxn_raw[j]) for j in jugadores}
    phi_punta = {j: redondear_arriba_kw(phi_punta_raw[j]) for j in jugadores}

    c0 = cfe[pleno]["capacidad_kw"]
    ccb = cfe[vacio]["capacidad_kw"]
    c0_mxn = cfe[pleno]["costo_capacidad_mxn"]
    ccb_mxn = cfe[vacio]["costo_capacidad_mxn"]
    ahorro_kw = c0 - ccb
    ahorro_mxn = redondear_mxn_energia(c0_mxn - ccb_mxn)
    ahorro_mxn_kw = redondear_mxn_energia(ahorro_kw * tarifa_cap)

    pct_mxn = {
        j: (phi_mxn[j] / ahorro_mxn * 100) if ahorro_mxn else 0.0 for j in jugadores
    }
    pct_kw = {
        j: (phi_cap[j] / ahorro_kw * 100) if ahorro_kw else 0.0 for j in jugadores
    }

    criterio_cfe = pd.DataFrame(
        [
            {
                "Código": cfe[s]["codigo"],
                "Escenario": cfe[s]["etiqueta"],
                "Energía (kWh)": round(cfe[s]["energia_kwh"], 2),
                "Demanda punta (kW)": cfe[s]["demanda_punta_kw"],
                "DemandaCalculadaCFE (kW)": cfe[s]["demanda_calculada_cfe_kw"],
                "Capacidad CFE (kW)": cfe[s]["capacidad_kw"],
                "Criterio aplicado": cfe[s]["criterio_aplicado"],
                "Costo capacidad (MXN)": cfe[s]["costo_capacidad_mxn"],
            }
            for s in orden_coaliciones
        ]
    )

    conceptos_mxn = [
        f"Tarifa capacidad ({fecha_corte.strftime('%m/%Y')}) ($/kW)",
        "",
        "Costo capacidad N (sin ayuda / con todos reconstruidos)",
        "Costo capacidad ∅ (solo ION / con recursos)",
        "Ahorro capacidad N−∅ (MXN)",
    ]
    valores_mxn = [
        f"${tarifa_cap:,.2f}",
        "",
        f"${c0_mxn:,.2f}",
        f"${ccb_mxn:,.2f}",
        f"${ahorro_mxn:,.2f}",
    ]
    for j in jugadores:
        conceptos_mxn.append(f"Shapley {etiquetas[j]} (MXN)")
        valores_mxn.append(f"${phi_mxn[j]:,.2f}")
    for j in jugadores:
        conceptos_mxn.append(f"Participación {etiquetas[j]} (%)")
        valores_mxn.append(f"{pct_mxn[j]:.1f} %")

    shapley_mxn = pd.DataFrame({"Concepto": conceptos_mxn, "Valor": valores_mxn})

    conceptos_kw = [
        "",
        "Capacidad N (sin ayuda)",
        "Capacidad ∅ (con recursos)",
        "Reducción capacidad N−∅ (kW)",
    ]
    valores_kw = [
        "",
        f"{c0:,}",
        f"{ccb:,}",
        f"{ahorro_kw:,}",
    ]
    for j in jugadores:
        conceptos_kw.append(f"Shapley {etiquetas[j]} (kW)")
        valores_kw.append(f"{phi_cap[j]:,.3f}")
    for j in jugadores:
        conceptos_kw.append(f"Participación {etiquetas[j]} (%)")
        valores_kw.append(f"{pct_kw[j]:.1f} %")
    conceptos_kw.extend(
        [
            "",
            "Referencia — solo demanda punta (sin criterio CFE)",
        ]
    )
    valores_kw.extend(["", ""])
    for j in jugadores:
        conceptos_kw.append(f"Shapley {etiquetas[j]} punta (kW)")
        valores_kw.append(f"{phi_punta[j]:,}")

    shapley_kw_tabla = pd.DataFrame({"Concepto": conceptos_kw, "Valor": valores_kw})

    filas_part = [
        {
            "Participante": "Total (reducción N − ∅)",
            "Ahorro capacidad (kW)": f"{ahorro_kw:,}",
            "Ahorro (MXN)": f"${ahorro_mxn:,.2f}",
            "Participación": "100.0 %",
        }
    ]
    for j in jugadores:
        filas_part.append(
            {
                "Participante": etiquetas[j],
                "Ahorro capacidad (kW)": f"{phi_cap[j]:,.3f}",
                "Ahorro (MXN)": f"${phi_mxn[j]:,.2f}",
                "Participación": f"{pct_mxn[j]:.1f} %",
            }
        )
    participantes = pd.DataFrame(filas_part)

    participantes_detalle = [
        {
            "id": j,
            "label": etiquetas[j],
            "kw": phi_cap[j],
            "mxn": phi_mxn[j],
            "pct": pct_mxn[j],
            "pct_kw": pct_kw[j],
            "punta_kw": phi_punta[j],
        }
        for j in jugadores
    ]

    n_gen = len(cfg.fuentes_generacion)
    formula = (
        "2 jugadores: S_i = ((v(N)−v(N\\\\{i}))+(v({i})−v(∅)))/2"
        if n == 2
        else f"{n} jugadores: φ_i = Σ |S|!(n−|S|−1)!/n! · (v(S∪{{i}})−v(S))"
    )

    metodologia = pd.DataFrame(
        {
            "Concepto": [
                "Subestación",
                "Periodo",
                "Participantes",
                "Coaliciones",
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
                " · ".join(cfg.etiquetas_participantes),
                f"{2 ** n} escenarios (2^{n})",
                "Capacidad = min(Demanda punta rodada, DemandaCalculadaCFE)",
                f"DemandaCalculadaCFE = Energía / ({factor_cfe_capacidad(esquema)} × 24 × días)",
                formula,
                "Equivalente en kW con tarifa del mes",
                "15 min, reinicio mensual, 00:05/00:10 = 0",
                "Cualquier decimal en demanda (kW) → entero superior (ceil)",
                "Dinero (MXN): ≥0.5 al entero superior, <0.5 hacia abajo (2 decimales)",
            ],
        }
    )

    # Compat: PDF / UI antigua (suma de generación vs BESS)
    gen_keys = [f.clave for f in cfg.fuentes_generacion]
    s_g_cap = sum(phi_cap[k] for k in gen_keys)
    s_g_mxn = redondear_mxn_energia(sum(phi_mxn[k] for k in gen_keys))
    s_g_punta = sum(phi_punta[k] for k in gen_keys)
    pct_g = (s_g_mxn / ahorro_mxn * 100) if ahorro_mxn else 0.0
    pct_g_kw = (s_g_cap / ahorro_kw * 100) if ahorro_kw else 0.0

    # Escenarios 2-jugador clásicos si n==2 (gen + bess)
    solo_gen = frozenset(gen_keys) if n_gen == 1 else None
    solo_bess = frozenset({PLAYER_BESS})
    cap_legacy = {
        "d0": c0,
        "dcb": ccb,
        "dc": cfe[solo_bess]["capacidad_kw"] if solo_bess in cfe else ccb,
        "db": cfe[solo_gen]["capacidad_kw"] if solo_gen and solo_gen in cfe else c0,
    }
    costo_legacy = {
        "d0": c0_mxn,
        "dcb": ccb_mxn,
        "dc": cfe[solo_bess]["costo_capacidad_mxn"] if solo_bess in cfe else ccb_mxn,
        "db": (
            cfe[solo_gen]["costo_capacidad_mxn"]
            if solo_gen and solo_gen in cfe
            else c0_mxn
        ),
    }

    return {
        "config": cfg,
        "fecha_corte": fecha_corte,
        "tarifa_cap": tarifa_cap,
        "dias": dias,
        "jugadores": jugadores,
        "etiquetas": etiquetas,
        "cfe_coaliciones": cfe,
        "cfe": {
            "N": cfe[pleno],
            "vacio": cfe[vacio],
            "Dcb": cfe[vacio],
            "D0": cfe[pleno],
        },
        "costo": costo_legacy,
        "cap": cap_legacy,
        "shapley_kw": {
            "generacion": s_g_cap,
            "bess": phi_cap[PLAYER_BESS],
            "total": ahorro_kw,
            "por_jugador": dict(phi_cap),
        },
        "shapley_mxn": {
            "generacion": s_g_mxn,
            "bess": phi_mxn[PLAYER_BESS],
            "total": ahorro_mxn,
            "por_jugador": dict(phi_mxn),
        },
        "shapley_mxn_ref": {"total": ahorro_mxn_kw},
        "shapley_punta_kw": {
            "generacion": s_g_punta,
            "bess": phi_punta[PLAYER_BESS],
            "por_jugador": dict(phi_punta),
        },
        "participacion_pct": {
            "generacion": pct_g,
            "bess": pct_mxn[PLAYER_BESS],
            "por_jugador": dict(pct_mxn),
        },
        "participacion_pct_kw": {
            "generacion": pct_g_kw,
            "bess": pct_kw[PLAYER_BESS],
            "por_jugador": dict(pct_kw),
        },
        "participantes_detalle": participantes_detalle,
        "criterio_cfe": criterio_cfe,
        "shapley": shapley_mxn,
        "shapley_mxn_tabla": shapley_mxn,
        "shapley_kw_tabla": shapley_kw_tabla,
        "participantes": participantes,
        "metodologia": metodologia,
        "criterio_limitante": cfe[vacio]["criterio_aplicado"],
    }
