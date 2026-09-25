"""Lectura de ACUMULADOS y ENERGIA_* para cálculos CFE."""

from __future__ import annotations

import os

import pandas as pd

from bess.config.subestaciones import (
    medidor_consumo_por_prefijo,
    ruta_acumulados_por_prefijo,
    ruta_energia_dia_por_prefijo,
)
from bess.core.kvarh import columnas_kvarh_prefijo, normalizar_columnas_kvarh
from bess.core.demand import aplicar_mascara_demanda_maximo
from bess.core.numbers import redondear_arriba_kw, sumar_energia
from bess.core.energia_periodo import sumar_consumo_por_periodo_df
from bess.config.esquema_tarifa import esquema_tarifa_prefijo

_PERIODOS_DEMANDA = (
    ("Base", "Base"),
    ("Intermedio", "Intermedio"),
    ("Punta", "Punta"),
)

def _fila_por_fecha(df, fecha):
    if df is None:
        return None
    fecha_str = fecha.strftime('%d/%m/%Y')
    filas = df[df['FECHA'] == fecha_str]
    return filas.iloc[0] if len(filas) > 0 else None


def _cargar_acumulados(prefijo):
    ruta_p = ruta_acumulados_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return None
    ruta = str(ruta_p)
    df = pd.read_csv(ruta)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    return df


def _filtrar_mes_hasta_fecha(df, fecha, col_fecha='FECHA_DT'):
    mes = fecha.month
    año = fecha.year
    return df[
        (df[col_fecha].dt.year == año)
        & (df[col_fecha].dt.month == mes)
        & (df[col_fecha].dt.date <= fecha)
    ]


def dias_transcurridos_mes(fecha):
    """Días transcurridos del mes a la fecha seleccionada."""
    return fecha.day


def obtener_demanda_kw_periodo_mes(fecha, prefijo, con_bess=True):
    """Demanda máxima acumulada del mes por periodo (ACUMULADOS_*.csv)."""
    fila = _fila_por_fecha(_cargar_acumulados(prefijo), fecha)
    if fila is None:
        return None
    tipo = 'CON_BESS' if con_bess else 'SIN_BESS'
    resultado = {}
    for clave in ('base', 'intermedio', 'punta'):
        col = f'{clave.upper()}_DEM_{tipo}_MAX'
        kw = pd.to_numeric(fila.get(col, 0), errors='coerce')
        resultado[clave] = redondear_arriba_kw(0 if pd.isna(kw) else kw)
    resultado['kw_max'] = max(resultado.values())
    return resultado


def obtener_demanda_max_mes(fecha, prefijo, con_bess=True):
    """Demanda máxima del mes en cualquier periodo horario (kW). Usada por cargo Distribución GDMTH."""
    demanda = obtener_demanda_kw_periodo_mes(fecha, prefijo, con_bess=con_bess)
    if demanda is None:
        return None
    return demanda['kw_max']


def obtener_kvarh_mes(fecha, prefijo):
    """kVArh acumulados del mes al día indicado (reportes BESS, sin truncar)."""
    fila = _fila_por_fecha(_cargar_acumulados(prefijo), fecha)
    if fila is not None and 'KVARH_ACUM' in fila.index:
        val = pd.to_numeric(fila.get('KVARH_ACUM', 0), errors='coerce')
        if not pd.isna(val):
            return float(val)

    ruta_p = ruta_energia_dia_por_prefijo(prefijo)
    if ruta_p and ruta_p.exists():
        ruta_dia = str(ruta_p)
        df = pd.read_csv(ruta_dia)
        if 'KVARH' in df.columns:
            df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
            df_r = _filtrar_mes_hasta_fecha(df, fecha, 'FECHA_DT')
            if not df_r.empty:
                return float(pd.to_numeric(df_r['KVARH'], errors='coerce').fillna(0).sum())

    med = medidor_consumo_por_prefijo(prefijo)
    if not med:
        return None
    ruta = str(med.ruta_consumo(filtrado=True))
    if not os.path.exists(ruta):
        ruta = str(med.ruta_consumo())
        if not os.path.exists(ruta):
            return None
    df = pd.read_csv(ruta)
    if 'Fecha' not in df.columns:
        return None
    df['FECHA_DT'] = pd.to_datetime(df['Fecha'])
    df_r = _filtrar_mes_hasta_fecha(df, fecha, 'FECHA_DT')
    if df_r.empty:
        return None
    cols = [c for c in columnas_kvarh_prefijo(prefijo) if c in df_r.columns]
    if not cols:
        return None
    df_r = normalizar_columnas_kvarh(df_r.copy())
    return float(df_r[cols].sum().sum())


def obtener_demanda_rolada_punta(fecha, prefijo, con_bess=True):
    """Demanda máxima del mes en horario punta (kW). Usada por cargo Capacidad."""
    fila = _fila_por_fecha(_cargar_acumulados(prefijo), fecha)
    if fila is None:
        return None
    tipo = 'CON_BESS' if con_bess else 'SIN_BESS'
    col = f'PUNTA_DEM_{tipo}_MAX'
    if col not in fila.index:
        return None
    kw = pd.to_numeric(fila.get(col, 0), errors='coerce')
    if pd.isna(kw):
        return 0
    return redondear_arriba_kw(kw)


def _obtener_energia_mes_desde_diario(fecha, prefijo, con_bess=True):
    """Suma energía de consumo por periodo desde ENERGIA_*_POR_DIA.csv (mes al día indicado)."""
    ruta_p = ruta_energia_dia_por_prefijo(prefijo)
    if not ruta_p or not ruta_p.exists():
        return None
    ruta = str(ruta_p)
    df = pd.read_csv(ruta)
    df['FECHA_DT'] = pd.to_datetime(df['FECHA'], format='%d/%m/%Y')
    df_r = _filtrar_mes_hasta_fecha(df, fecha)
    if df_r.empty:
        return None
    esquema = esquema_tarifa_prefijo(prefijo)
    por_periodo = sumar_consumo_por_periodo_df(df_r, esquema, con_bess=con_bess)
    return {'total': sum(por_periodo.values()), 'por_periodo': por_periodo}


def obtener_energia_con_bess_mes(fecha, prefijo):
    """Energía con BESS por periodos (medidor), del mes al día indicado."""
    return _obtener_energia_mes_desde_diario(fecha, prefijo, con_bess=True)


def obtener_energia_sin_bess_mes(fecha, prefijo):
    """Energía sin BESS por periodos, del mes al día indicado (ENERGIA_*_POR_DIA.csv)."""
    return _obtener_energia_mes_desde_diario(fecha, prefijo, con_bess=False)


def acumulados_tiene_demanda_sin_bess(prefijo):
    df = _cargar_acumulados(prefijo)
    if df is None:
        return False
    return 'PUNTA_DEM_SIN_BESS_MAX' in df.columns


def _filtrar_combinado_mes_hasta(df: pd.DataFrame, fecha) -> pd.DataFrame:
    """Filas del combinado en el mes calendario hasta la fecha de corte (inclusive)."""
    fechas = pd.to_datetime(df["FECHA"], format="%d/%m/%Y", errors="coerce")
    mask = (
        (fechas.dt.year == fecha.year)
        & (fechas.dt.month == fecha.month)
        & (fechas.dt.date <= fecha)
    )
    return df.loc[mask].copy()


def _pico_demanda_rolada(df: pd.DataFrame, col_dem: str, periodo: str):
    """Máximo de demanda rolada 15 min en un periodo TOU (máscara en bordes)."""
    if col_dem not in df.columns or "PERIODO" not in df.columns:
        return None, None
    dem = pd.to_numeric(df[col_dem], errors="coerce")
    enmasc = aplicar_mascara_demanda_maximo(dem, df["PERIODO"])
    etiqueta = df["PERIODO"].astype(str).str.strip()
    subset = enmasc.loc[etiqueta == periodo].dropna()
    if subset.empty:
        return None, None
    idx = subset.idxmax()
    kw = redondear_arriba_kw(float(subset.loc[idx]))
    fh = df.loc[idx, "FECHA_HORA"] if "FECHA_HORA" in df.columns else "—"
    if pd.isna(fh) or fh == "":
        fh = "—"
    return kw, fh


def construir_tabla_demanda_rolada_max_mes(df, fecha, prefijo):
    """
    Resumen de máximos de demanda rolada 15 min por periodo, hasta `fecha`.

    Usa las columnas ``*_kW_DEM_15min`` del combinado (misma serie que la
    gráfica diaria) y excluye los dos primeros intervalos de cada racha
    tarifaria, igual que Capacidad CFE / Shapley.
    """
    if df is None or getattr(df, "empty", True) or "FECHA" not in df.columns:
        return None
    col_con = f"IUSA_CON_BESS_{prefijo}_kW_DEM_15min"
    col_sin = f"IUSA_SIN_BESS_{prefijo}_kW_DEM_15min"
    if col_con not in df.columns:
        return None
    mes = _filtrar_combinado_mes_hasta(df, fecha)
    if mes.empty:
        return None

    filas = []
    for nombre, clave_periodo in _PERIODOS_DEMANDA:
        con_kw, con_fh = _pico_demanda_rolada(mes, col_con, clave_periodo)
        sin_kw, sin_fh = _pico_demanda_rolada(mes, col_sin, clave_periodo)
        filas.append({
            "Periodo": nombre,
            "Con BESS (kW, 15 min)": "—" if con_kw is None else f"{con_kw:,}",
            "Hora con BESS": "—" if con_fh is None else con_fh,
            "Sin BESS (kW, 15 min)": "—" if sin_kw is None else f"{sin_kw:,}",
            "Hora sin BESS": "—" if sin_fh is None else sin_fh,
        })
    return pd.DataFrame(filas)
