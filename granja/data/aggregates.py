"""Agregados de energía e ingresos DIST por MEGA (perfil 5 min en SQLite)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from bess.cfe.periods import periodo_por_fecha_hora
from bess.config.esquema_tarifa import ESQUEMA_DIST
from bess.config.paths import RUTA_BD_PERFILES
from bess.core.numbers import redondear_kwh
from bess.data.ingest.ion import db
from bess.tariffs.loader import tarifa_por_fecha

from granja.config import ESQUEMA_TARIFA, FACTOR_KW_DESDE_KWH
from granja.config.meters import ETIQUETAS_POR_NOMBRE, NOMBRES_MEGA


_PERIODOS = ("Base", "Intermedio", "Punta")
ProgressCallback = Callable[[int, int, str], None]


def _prog(cb: ProgressCallback | None, step: int, total: int, label: str) -> None:
    if cb is not None:
        cb(step, total, label)


def _parse_dia(valor: date | datetime | str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(texto[:19] if " " in texto else texto[:10], fmt).date()
        except ValueError:
            continue
    return datetime.fromisoformat(texto[:10]).date()


def leer_perfil_megas(
    dia: date | datetime | str,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    medidores: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Perfil cincuminutal del día: medidor_id, fecha, kwh_rec."""
    dia_d = _parse_dia(dia)
    return leer_perfil_megas_rango(dia_d, dia_d, ruta_bd=ruta_bd, medidores=medidores)


def leer_perfil_megas_rango(
    desde: date | datetime | str,
    hasta: date | datetime | str,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    medidores: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Perfil cincuminutal del rango inclusive: medidor_id, fecha, kwh_rec."""
    inicio_d = _parse_dia(desde)
    fin_d = _parse_dia(hasta)
    if fin_d < inicio_d:
        inicio_d, fin_d = fin_d, inicio_d
    inicio = f"{inicio_d.isoformat()} 00:00:00"
    fin = f"{fin_d.isoformat()} 23:59:59"
    nombres = medidores or NOMBRES_MEGA
    db.init_db(ruta_bd)
    placeholders = ",".join("?" * len(nombres))
    with db.conectar_bd(ruta_bd) as conn:
        df = pd.read_sql_query(
            f"""
            SELECT medidor_id, fecha, kwh_rec
            FROM perfil_carga
            WHERE medidor_id IN ({placeholders})
              AND fecha >= ? AND fecha <= ?
            ORDER BY medidor_id, fecha
            """,
            conn,
            params=[*nombres, inicio, fin],
        )
    if df.empty:
        return pd.DataFrame(columns=["medidor_id", "fecha", "kwh_rec"])
    return df


def _agregar_periodo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        out = df.copy()
        out["periodo"] = pd.Series(dtype=str)
        return out
    out = df.copy()
    out["fecha_dt"] = pd.to_datetime(out["fecha"])
    out["periodo"] = out["fecha_dt"].dt.strftime("%d/%m/%Y %H:%M").map(
        lambda fh: periodo_por_fecha_hora(fh, ESQUEMA_TARIFA or ESQUEMA_DIST)
    )
    return out


def energia_dia_por_mega(
    dia: date | datetime | str,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
) -> pd.DataFrame:
    """Una fila por MEGA con kWh Base/Intermedio/Punta/Total del día."""
    df = _agregar_periodo(leer_perfil_megas(dia, ruta_bd=ruta_bd))
    columnas = ["medidor_id", "etiqueta", "Base", "Intermedio", "Punta", "Total"]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    pivot = (
        df.groupby(["medidor_id", "periodo"], as_index=False)["kwh_rec"]
        .sum()
        .pivot_table(index="medidor_id", columns="periodo", values="kwh_rec", fill_value=0.0)
        .reindex(columns=list(_PERIODOS), fill_value=0.0)
        .reset_index()
    )
    for p in _PERIODOS:
        if p not in pivot.columns:
            pivot[p] = 0.0
    pivot["Total"] = pivot[list(_PERIODOS)].sum(axis=1)
    pivot["etiqueta"] = pivot["medidor_id"].map(lambda n: ETIQUETAS_POR_NOMBRE.get(n, n))
    # Conservar orden Mega01…Mega21
    orden = {n: i for i, n in enumerate(NOMBRES_MEGA)}
    pivot["_ord"] = pivot["medidor_id"].map(lambda n: orden.get(n, 999))
    pivot = pivot.sort_values("_ord").drop(columns="_ord")
    return pivot[columnas]


def ingresos_desde_energia(df_energia: pd.DataFrame, dia: date | datetime | str) -> pd.DataFrame:
    """Aplica precios DIST del año-mes del día consultado."""
    if df_energia.empty:
        cols = [
            "medidor_id", "etiqueta",
            "Base", "Intermedio", "Punta", "Total",
            "Ingreso_Base", "Ingreso_Intermedio", "Ingreso_Punta", "Ingreso_Total",
        ]
        return pd.DataFrame(columns=cols)

    fecha_d = _parse_dia(dia)
    out = df_energia.copy()
    for periodo in _PERIODOS:
        precio = tarifa_por_fecha(periodo, fecha_d, ESQUEMA_TARIFA)
        col_ing = f"Ingreso_{periodo}"
        out[col_ing] = out[periodo].astype(float) * precio
    out["Ingreso_Total"] = (
        out["Ingreso_Base"] + out["Ingreso_Intermedio"] + out["Ingreso_Punta"]
    )
    return out


def resumen_dia(dia: date | datetime | str, *, ruta_bd: Path = RUTA_BD_PERFILES) -> dict:
    """Totales del día (energía + ingresos DIST) y desglose por MEGA."""
    energia = energia_dia_por_mega(dia, ruta_bd=ruta_bd)
    detalle = ingresos_desde_energia(energia, dia)
    if detalle.empty:
        return {
            "fecha": _parse_dia(dia).isoformat(),
            "energia_base": 0.0,
            "energia_intermedio": 0.0,
            "energia_punta": 0.0,
            "energia_total": 0.0,
            "ingreso_base": 0.0,
            "ingreso_intermedio": 0.0,
            "ingreso_punta": 0.0,
            "ingreso_total": 0.0,
            "detalle": detalle,
            "precios": {},
        }
    fecha_d = _parse_dia(dia)
    precios = {p: tarifa_por_fecha(p, fecha_d, ESQUEMA_TARIFA) for p in _PERIODOS}
    return {
        "fecha": _parse_dia(dia).isoformat(),
        "energia_base": float(detalle["Base"].sum()),
        "energia_intermedio": float(detalle["Intermedio"].sum()),
        "energia_punta": float(detalle["Punta"].sum()),
        "energia_total": float(detalle["Total"].sum()),
        "ingreso_base": float(detalle["Ingreso_Base"].sum()),
        "ingreso_intermedio": float(detalle["Ingreso_Intermedio"].sum()),
        "ingreso_punta": float(detalle["Ingreso_Punta"].sum()),
        "ingreso_total": float(detalle["Ingreso_Total"].sum()),
        "detalle": detalle,
        "precios": precios,
    }


def perfil_potencia_dia(
    dia: date | datetime | str,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
) -> pd.DataFrame:
    """Curva de potencia estimada (kW) por MEGA a partir de kWh 5 min."""
    df = leer_perfil_megas(dia, ruta_bd=ruta_bd)
    if df.empty:
        return pd.DataFrame(columns=["fecha", "medidor_id", "kw"])
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["fecha"])
    out["kw"] = out["kwh_rec"].astype(float) * FACTOR_KW_DESDE_KWH
    out["etiqueta"] = out["medidor_id"].map(lambda n: ETIQUETAS_POR_NOMBRE.get(n, n))
    return out[["fecha", "medidor_id", "etiqueta", "kw", "kwh_rec"]]


def acumulado_mes(
    dia: date | datetime | str,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
) -> dict[str, float]:
    """Suma energía e ingresos DIST del 1° del mes hasta `dia` inclusive."""
    dia_d = _parse_dia(dia)
    r = resumen_rango(date(dia_d.year, dia_d.month, 1), dia_d, ruta_bd=ruta_bd)
    return {
        "energia_kwh": r["energia_total"],
        "ingreso_mxn": r["ingreso_total"],
        "energia_kwh_redondeada": float(redondear_kwh(r["energia_total"])),
        "ingreso_mxn_redondeado": float(redondear_kwh(r["ingreso_total"])),
    }


def _resumen_vacio(
    desde: date,
    hasta: date,
    detalle: pd.DataFrame | None = None,
    por_dia: pd.DataFrame | None = None,
) -> dict:
    cols_det = [
        "medidor_id", "etiqueta",
        "Base", "Intermedio", "Punta", "Total",
        "Ingreso_Base", "Ingreso_Intermedio", "Ingreso_Punta", "Ingreso_Total",
    ]
    cols_dia = [
        "fecha",
        "Base", "Intermedio", "Punta", "Total",
        "Ingreso_Base", "Ingreso_Intermedio", "Ingreso_Punta", "Ingreso_Total",
    ]
    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "energia_base": 0.0,
        "energia_intermedio": 0.0,
        "energia_punta": 0.0,
        "energia_total": 0.0,
        "ingreso_base": 0.0,
        "ingreso_intermedio": 0.0,
        "ingreso_punta": 0.0,
        "ingreso_total": 0.0,
        "detalle": detalle if detalle is not None else pd.DataFrame(columns=cols_det),
        "por_dia": por_dia if por_dia is not None else pd.DataFrame(columns=cols_dia),
        "precios": {},
    }


def resumen_rango(
    desde: date | datetime | str,
    hasta: date | datetime | str,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
) -> dict:
    """
    Energía e ingresos DIST del rango inclusive.

    Aplica la tarifa del mes de cada slot (válido si el rango cruza meses).
    """
    inicio_d = _parse_dia(desde)
    fin_d = _parse_dia(hasta)
    if fin_d < inicio_d:
        inicio_d, fin_d = fin_d, inicio_d

    df = _agregar_periodo(leer_perfil_megas_rango(inicio_d, fin_d, ruta_bd=ruta_bd))
    if df.empty:
        return _resumen_vacio(inicio_d, fin_d)

    out = df.copy()
    out["anio"] = out["fecha_dt"].dt.year
    out["mes"] = out["fecha_dt"].dt.month
    out["dia"] = out["fecha_dt"].dt.date
    out = _aplicar_precios_eficientes(out)

    # Por MEGA
    energia_mega = (
        out.groupby(["medidor_id", "periodo"], as_index=False)["kwh_rec"]
        .sum()
        .pivot_table(index="medidor_id", columns="periodo", values="kwh_rec", fill_value=0.0)
        .reindex(columns=list(_PERIODOS), fill_value=0.0)
        .reset_index()
    )
    ingreso_mega = (
        out.groupby(["medidor_id", "periodo"], as_index=False)["ingreso"]
        .sum()
        .pivot_table(index="medidor_id", columns="periodo", values="ingreso", fill_value=0.0)
        .reindex(columns=list(_PERIODOS), fill_value=0.0)
        .reset_index()
    )
    for p in _PERIODOS:
        if p not in energia_mega.columns:
            energia_mega[p] = 0.0
        if p not in ingreso_mega.columns:
            ingreso_mega[p] = 0.0
    detalle = energia_mega.merge(
        ingreso_mega.rename(columns={p: f"Ingreso_{p}" for p in _PERIODOS}),
        on="medidor_id",
        how="outer",
    ).fillna(0.0)
    detalle["Total"] = detalle[list(_PERIODOS)].sum(axis=1)
    detalle["Ingreso_Total"] = detalle[[f"Ingreso_{p}" for p in _PERIODOS]].sum(axis=1)
    detalle["etiqueta"] = detalle["medidor_id"].map(lambda n: ETIQUETAS_POR_NOMBRE.get(n, n))
    orden = {n: i for i, n in enumerate(NOMBRES_MEGA)}
    detalle["_ord"] = detalle["medidor_id"].map(lambda n: orden.get(n, 999))
    detalle = detalle.sort_values("_ord").drop(columns="_ord")
    cols_det = [
        "medidor_id", "etiqueta",
        "Base", "Intermedio", "Punta", "Total",
        "Ingreso_Base", "Ingreso_Intermedio", "Ingreso_Punta", "Ingreso_Total",
    ]
    detalle = detalle[cols_det]

    # Por día
    energia_dia = (
        out.groupby(["dia", "periodo"], as_index=False)["kwh_rec"]
        .sum()
        .pivot_table(index="dia", columns="periodo", values="kwh_rec", fill_value=0.0)
        .reindex(columns=list(_PERIODOS), fill_value=0.0)
        .reset_index()
    )
    ingreso_dia = (
        out.groupby(["dia", "periodo"], as_index=False)["ingreso"]
        .sum()
        .pivot_table(index="dia", columns="periodo", values="ingreso", fill_value=0.0)
        .reindex(columns=list(_PERIODOS), fill_value=0.0)
        .reset_index()
    )
    for p in _PERIODOS:
        if p not in energia_dia.columns:
            energia_dia[p] = 0.0
        if p not in ingreso_dia.columns:
            ingreso_dia[p] = 0.0
    por_dia = energia_dia.merge(
        ingreso_dia.rename(columns={p: f"Ingreso_{p}" for p in _PERIODOS}),
        on="dia",
        how="outer",
    ).fillna(0.0)
    por_dia = por_dia.rename(columns={"dia": "fecha"})
    por_dia["Total"] = por_dia[list(_PERIODOS)].sum(axis=1)
    por_dia["Ingreso_Total"] = por_dia[[f"Ingreso_{p}" for p in _PERIODOS]].sum(axis=1)
    por_dia = por_dia.sort_values("fecha").reset_index(drop=True)
    cols_dia = [
        "fecha",
        "Base", "Intermedio", "Punta", "Total",
        "Ingreso_Base", "Ingreso_Intermedio", "Ingreso_Punta", "Ingreso_Total",
    ]
    por_dia = por_dia[cols_dia]

    precios: dict[str, float] = {}
    if inicio_d.month == fin_d.month and inicio_d.year == fin_d.year:
        precios = {p: tarifa_por_fecha(p, inicio_d, ESQUEMA_TARIFA) for p in _PERIODOS}

    return {
        "desde": inicio_d.isoformat(),
        "hasta": fin_d.isoformat(),
        "energia_base": float(detalle["Base"].sum()),
        "energia_intermedio": float(detalle["Intermedio"].sum()),
        "energia_punta": float(detalle["Punta"].sum()),
        "energia_total": float(detalle["Total"].sum()),
        "ingreso_base": float(detalle["Ingreso_Base"].sum()),
        "ingreso_intermedio": float(detalle["Ingreso_Intermedio"].sum()),
        "ingreso_punta": float(detalle["Ingreso_Punta"].sum()),
        "ingreso_total": float(detalle["Ingreso_Total"].sum()),
        "detalle": detalle,
        "por_dia": por_dia,
        "precios": precios,
    }


def fechas_disponibles(*, ruta_bd: Path = RUTA_BD_PERFILES) -> list[date]:
    """
    Rango de días con datos MEGA (min y max).

    Antes hacía DISTINCT sobre todo el histórico (~millones de filas);
    ahora solo consulta MIN/MAX por medidor (usa el índice medidor_id, fecha).
    """
    rango = rango_fechas_disponibles(ruta_bd=ruta_bd)
    if rango is None:
        return []
    return [rango[0], rango[1]]


def rango_fechas_disponibles(
    *, ruta_bd: Path = RUTA_BD_PERFILES
) -> tuple[date, date] | None:
    """(min_dia, max_dia) con datos MEGA, o None si no hay perfiles."""
    db.init_db(ruta_bd)
    min_g: date | None = None
    max_g: date | None = None
    with db.conectar_bd(ruta_bd) as conn:
        for nombre in NOMBRES_MEGA:
            row = conn.execute(
                """
                SELECT MIN(fecha) AS mn, MAX(fecha) AS mx
                FROM perfil_carga
                WHERE medidor_id = ?
                """,
                (nombre,),
            ).fetchone()
            if not row or not row["mn"] or not row["mx"]:
                continue
            d0 = date.fromisoformat(str(row["mn"])[:10])
            d1 = date.fromisoformat(str(row["mx"])[:10])
            min_g = d0 if min_g is None else min(min_g, d0)
            max_g = d1 if max_g is None else max(max_g, d1)
    if min_g is None or max_g is None:
        return None
    return min_g, max_g


_MESES_ES = (
    "",
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)


def anios_con_datos(*, ruta_bd: Path = RUTA_BD_PERFILES) -> list[int]:
    """Años con al menos un perfil MEGA (desde MIN/MAX, sin DISTINCT global)."""
    rango = rango_fechas_disponibles(ruta_bd=ruta_bd)
    if rango is None:
        return []
    return list(range(rango[0].year, rango[1].year + 1))


def _leer_perfil_total_rango(
    desde: date,
    hasta: date,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
) -> pd.DataFrame:
    """Suma kWh de los 21 MEGAs por slot de 5 min (reduce filas ×21)."""
    nombres = NOMBRES_MEGA
    db.init_db(ruta_bd)
    placeholders = ",".join("?" * len(nombres))
    with db.conectar_bd(ruta_bd) as conn:
        rows = conn.execute(
            f"""
            SELECT fecha, SUM(kwh_rec) AS kwh_rec
            FROM perfil_carga
            WHERE medidor_id IN ({placeholders})
              AND fecha >= ? AND fecha <= ?
            GROUP BY fecha
            ORDER BY fecha
            """,
            [*nombres, f"{desde.isoformat()} 00:00:00", f"{hasta.isoformat()} 23:59:59"],
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["fecha", "kwh_rec"])
    return pd.DataFrame([dict(r) for r in rows])


def _aplicar_precios_eficientes(out: pd.DataFrame) -> pd.DataFrame:
    """Asigna precio DIST por (año, mes, periodo) sin aplicar fila a fila."""
    if out.empty:
        out = out.copy()
        out["precio"] = pd.Series(dtype=float)
        out["ingreso"] = pd.Series(dtype=float)
        return out

    claves = (
        out[["anio", "mes", "periodo"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    mapa: dict[tuple[int, int, str], float] = {}
    for anio, mes, periodo in claves:
        if periodo not in _PERIODOS:
            mapa[(int(anio), int(mes), str(periodo))] = 0.0
            continue
        mapa[(int(anio), int(mes), str(periodo))] = tarifa_por_fecha(
            str(periodo), date(int(anio), int(mes), 1), ESQUEMA_TARIFA
        )
    out = out.copy()
    out["precio"] = [
        mapa.get((int(a), int(m), str(p)), 0.0)
        for a, m, p in zip(out["anio"], out["mes"], out["periodo"])
    ]
    out["ingreso"] = out["kwh_rec"].astype(float) * out["precio"].astype(float)
    return out


def ingresos_mensuales_por_anio(
    anios: list[int] | tuple[int, ...] | None = None,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    on_progress: ProgressCallback | None = None,
) -> dict:
    """
    Comparativo de ingresos DIST mensuales por año.

    Retorna:
      - anios: lista de años incluidos
      - tabla: DataFrame Mes | 2023 | 2024 | … | (filas Enero…Diciembre)
      - totales: {año: mxn}
      - total_acumulado: suma de todos los importes
    """
    _prog(on_progress, 0, 1, "Preparando años…")
    disponibles = anios_con_datos(ruta_bd=ruta_bd)
    if anios is None:
        anios_sel = list(disponibles)
    else:
        anios_sel = sorted({int(a) for a in anios if int(a) in set(disponibles)})

    vacia = pd.DataFrame({"Mes": list(_MESES_ES[1:])})
    if not anios_sel:
        _prog(on_progress, 1, 1, "Sin datos")
        return {
            "anios": [],
            "tabla": vacia,
            "totales": {},
            "total_acumulado": 0.0,
        }

    total_pasos = len(anios_sel) + 1
    filas_mes: list[dict] = []
    for i, anio in enumerate(anios_sel, start=1):
        _prog(on_progress, i - 1, total_pasos, f"Calculando ingresos {anio}…")
        desde = date(anio, 1, 1)
        hasta = date(anio, 12, 31)
        df = _leer_perfil_total_rango(desde, hasta, ruta_bd=ruta_bd)
        if df.empty:
            for mes in range(1, 13):
                filas_mes.append({"anio": anio, "mes": mes, "ingreso": 0.0})
            _prog(on_progress, i, total_pasos, f"{anio} sin datos")
            continue

        out = _agregar_periodo(df)
        out["anio"] = out["fecha_dt"].dt.year
        out["mes"] = out["fecha_dt"].dt.month
        out = _aplicar_precios_eficientes(out)
        agrupado = out.groupby(["anio", "mes"], as_index=False)["ingreso"].sum()
        presentes = {
            (int(r.anio), int(r.mes)): float(r.ingreso)
            for r in agrupado.itertuples(index=False)
        }
        for mes in range(1, 13):
            filas_mes.append({
                "anio": anio,
                "mes": mes,
                "ingreso": presentes.get((anio, mes), 0.0),
            })
        _prog(on_progress, i, total_pasos, f"{anio} listo")

    _prog(on_progress, len(anios_sel), total_pasos, "Armando tabla…")
    agrupado = pd.DataFrame(filas_mes)
    pivot = (
        agrupado.pivot_table(index="mes", columns="anio", values="ingreso", fill_value=0.0)
        .reindex(index=list(range(1, 13)), fill_value=0.0)
        .reindex(columns=anios_sel, fill_value=0.0)
    )
    tabla = pivot.reset_index().rename(columns={"mes": "Mes"})
    tabla["Mes"] = tabla["Mes"].map(lambda m: _MESES_ES[int(m)])
    rename_cols = {a: str(a) for a in anios_sel}
    for a in anios_sel:
        tabla[a] = tabla[a].astype(float)
    tabla = tabla.rename(columns=rename_cols)

    totales = {a: float(pivot[a].sum()) for a in anios_sel}
    total_acumulado = float(sum(totales.values()))
    _prog(on_progress, total_pasos, total_pasos, "Cálculo de ingresos listo")
    return {
        "anios": anios_sel,
        "tabla": tabla,
        "totales": totales,
        "total_acumulado": total_acumulado,
    }


def energia_mensuales_por_anio(
    anios: list[int] | tuple[int, ...] | None = None,
    *,
    ruta_bd: Path = RUTA_BD_PERFILES,
    on_progress: ProgressCallback | None = None,
) -> dict:
    """
    Comparativo de energía (kWh) mensual por año.

    Más rápido que ingresos: agrega en SQL por año-mes (sin periodos/tarifas).
    """
    total_pasos = 3
    _prog(on_progress, 0, total_pasos, "Preparando años…")
    disponibles = anios_con_datos(ruta_bd=ruta_bd)
    if anios is None:
        anios_sel = list(disponibles)
    else:
        anios_sel = sorted({int(a) for a in anios if int(a) in set(disponibles)})

    vacia = pd.DataFrame({"Mes": list(_MESES_ES[1:])})
    if not anios_sel:
        _prog(on_progress, total_pasos, total_pasos, "Sin datos")
        return {
            "anios": [],
            "tabla": vacia,
            "totales": {},
            "total_acumulado": 0.0,
        }

    nombres = NOMBRES_MEGA
    db.init_db(ruta_bd)
    placeholders = ",".join("?" * len(nombres))
    desde = f"{min(anios_sel)}-01-01 00:00:00"
    hasta = f"{max(anios_sel)}-12-31 23:59:59"
    _prog(on_progress, 1, total_pasos, "Consultando energía en base…")
    with db.conectar_bd(ruta_bd) as conn:
        rows = conn.execute(
            f"""
            SELECT
                CAST(substr(fecha, 1, 4) AS INTEGER) AS anio,
                CAST(substr(fecha, 6, 2) AS INTEGER) AS mes,
                SUM(kwh_rec) AS kwh
            FROM perfil_carga
            WHERE medidor_id IN ({placeholders})
              AND fecha >= ? AND fecha <= ?
            GROUP BY anio, mes
            ORDER BY anio, mes
            """,
            [*nombres, desde, hasta],
        ).fetchall()

    _prog(on_progress, 2, total_pasos, "Armando tabla mensual…")
    presentes = {
        (int(r["anio"]), int(r["mes"])): float(r["kwh"] or 0)
        for r in rows
        if r["anio"] in anios_sel
    }
    filas_mes = [
        {
            "anio": anio,
            "mes": mes,
            "kwh": presentes.get((anio, mes), 0.0),
        }
        for anio in anios_sel
        for mes in range(1, 13)
    ]
    agrupado = pd.DataFrame(filas_mes)
    pivot = (
        agrupado.pivot_table(index="mes", columns="anio", values="kwh", fill_value=0.0)
        .reindex(index=list(range(1, 13)), fill_value=0.0)
        .reindex(columns=anios_sel, fill_value=0.0)
    )
    tabla = pivot.reset_index().rename(columns={"mes": "Mes"})
    tabla["Mes"] = tabla["Mes"].map(lambda m: _MESES_ES[int(m)])
    rename_cols = {a: str(a) for a in anios_sel}
    for a in anios_sel:
        tabla[a] = tabla[a].astype(float)
    tabla = tabla.rename(columns=rename_cols)

    totales = {a: float(pivot[a].sum()) for a in anios_sel}
    _prog(on_progress, total_pasos, total_pasos, "Cálculo de energía listo")
    return {
        "anios": anios_sel,
        "tabla": tabla,
        "totales": totales,
        "total_acumulado": float(sum(totales.values())),
    }
