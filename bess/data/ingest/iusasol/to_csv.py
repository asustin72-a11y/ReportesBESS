"""Convierte perfil JSON ISOL (Profiles/Gral) a CSV compatible con BESS."""

from __future__ import annotations

from typing import Any

from pathlib import Path

import pandas as pd

COLUMNAS_PERFIL = [
    'Fecha',
    'KWH_REC',
    'KWH_ENT',
    'KVARH_Q1',
    'KVARH_Q2',
    'KVARH_Q3',
    'KVARH_Q4',
]

# tym: escala de unidad. tye: E=energía, P=potencia (misma escala, distinta magnitud).
# Tabla IUSASOL: 0=W, 1=Wh, 2=kWh, 3=MWh, 4=GWh (con tye=E; con tye=P → W/kW/MW/GW).
TYM_ESCALA: dict[str, str] = {
    '0': 'W',
    '1': 'Wh',
    '2': 'kWh',
    '3': 'MWh',
    '4': 'GWh',
}
TYM_KWH = '2'
TYE_ENERGIA = 'E'
TYE_POTENCIA = 'P'


def perfil_json_a_dataframe(perfil: Any) -> pd.DataFrame:
    """JSON de Profiles/Gral → DataFrame con columnas estándar BESS."""
    if not isinstance(perfil, dict):
        raise ValueError('El perfil debe ser un objeto JSON (dict).')

    filas = perfil.get('profiles')
    if not isinstance(filas, list) or not filas:
        raise ValueError('El perfil no incluye registros en "profiles".')

    registros: list[dict[str, float | str]] = []
    for item in filas:
        if not isinstance(item, dict):
            continue
        tiempo = item.get('time')
        canales = item.get('channels')
        if not tiempo or not isinstance(canales, list) or len(canales) < 6:
            continue
        registros.append({
            'Fecha': str(tiempo).replace('T', ' '),
            'KWH_REC': float(canales[0] or 0),
            'KWH_ENT': float(canales[1] or 0),
            'KVARH_Q1': float(canales[2] or 0),
            'KVARH_Q2': float(canales[3] or 0),
            'KVARH_Q3': float(canales[4] or 0),
            'KVARH_Q4': float(canales[5] or 0),
        })

    if not registros:
        raise ValueError('No se pudieron interpretar filas del perfil.')

    df = pd.DataFrame(registros, columns=COLUMNAS_PERFIL)
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df = df.dropna(subset=['Fecha']).sort_values('Fecha').reset_index(drop=True)
    return df


def _preparar_dataframe(perfil: Any) -> pd.DataFrame:
    """JSON → DataFrame con Fecha formateada para CSV."""
    df = perfil_json_a_dataframe(perfil)
    df = df.copy()
    df['Fecha'] = df['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S')
    return df


def perfil_json_a_csv(perfil: Any) -> str:
    """Serializa el perfil a CSV utf-8-sig (mismo formato que ArchivosFuente)."""
    df = _preparar_dataframe(perfil)
    # CRLF: Excel en Windows interpreta mal CSV solo con LF (filas vacías alternas).
    return df.to_csv(index=False, lineterminator='\r\n')


def guardar_perfil_csv(perfil: Any, ruta: Path | str) -> Path:
    """Guarda CSV con BOM y CRLF, igual que verify.py."""
    df = _preparar_dataframe(perfil)
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False, encoding='utf-8-sig', lineterminator='\r\n')
    return destino
