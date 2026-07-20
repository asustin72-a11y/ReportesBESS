"""Carga los CSV del reporteador Consultas Usuarios."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from consultas_usuarios.paths import (
    CONTRATOS_VACIOS,
    REPORTE_PRINCIPAL,
)


def cargar_reporte_principal(ruta: Path | None = None) -> pd.DataFrame:
    archivo = ruta or REPORTE_PRINCIPAL
    if not archivo.is_file():
        return pd.DataFrame(columns=['Contrato', 'Serial', 'Ultimo_perfil', 'Nota'])
    df = pd.read_csv(archivo, encoding='utf-8-sig')
    for col in ('Contrato', 'Serial', 'Ultimo_perfil', 'Nota'):
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str).str.strip()
    return df[['Contrato', 'Serial', 'Ultimo_perfil', 'Nota']]


def cargar_contratos_vacios(ruta: Path | None = None) -> pd.DataFrame:
    archivo = ruta or CONTRATOS_VACIOS
    if not archivo.is_file():
        return pd.DataFrame(columns=['Contrato'])
    df = pd.read_csv(archivo, encoding='utf-8-sig')
    if 'Contrato' not in df.columns:
        return pd.DataFrame(columns=['Contrato'])
    df['Contrato'] = df['Contrato'].fillna('').astype(str).str.strip()
    return df[df['Contrato'] != ''].drop_duplicates().sort_values('Contrato')


def resumen(df: pd.DataFrame) -> dict[str, int]:
    if df.empty:
        return {
            'filas': 0,
            'contratos': 0,
            'con_perfil': 0,
            'sin_energia': 0,
        }
    return {
        'filas': int(len(df)),
        'contratos': int(df['Contrato'].replace('', pd.NA).nunique(dropna=True)),
        'con_perfil': int((df['Ultimo_perfil'] != '').sum()),
        'sin_energia': int(((df['Ultimo_perfil'] == '') & (df['Serial'] != '')).sum()),
    }


def filtrar_reporte(
    df: pd.DataFrame,
    *,
    texto: str = '',
    estado: str = 'todos',
) -> pd.DataFrame:
    out = df.copy()
    q = (texto or '').strip().casefold()
    if q:
        mask = (
            out['Contrato'].str.casefold().str.contains(q, na=False)
            | out['Serial'].str.casefold().str.contains(q, na=False)
        )
        out = out.loc[mask]
    if estado == 'con_perfil':
        out = out.loc[out['Ultimo_perfil'] != '']
    elif estado == 'sin_energia':
        out = out.loc[(out['Ultimo_perfil'] == '') & (out['Serial'] != '')]
    return out.reset_index(drop=True)


def agrupar_por_contrato(df: pd.DataFrame) -> list[dict]:
    """Lista de contratos, cada uno con sus medidores.

    Cada ítem: {
      'contrato': str,
      'n_medidores': int,
      'con_perfil': int,
      'medidores': DataFrame[Serial, Ultimo_perfil, Nota],
    }
    """
    if df.empty:
        return []

    grupos: list[dict] = []
    orden = sorted(
        (c for c in df['Contrato'].unique() if str(c).strip()),
        key=str.casefold,
    )
    # Filas sin nombre de contrato al final
    if (df['Contrato'] == '').any():
        orden.append('')

    for nombre in orden:
        bloque = df.loc[df['Contrato'] == nombre].copy()
        medidores = (
            bloque[['Serial', 'Ultimo_perfil', 'Nota']]
            .sort_values(['Serial'], key=lambda s: s.str.casefold())
            .reset_index(drop=True)
        )
        grupos.append({
            'contrato': nombre or '(sin nombre)',
            'n_medidores': int(len(medidores)),
            'con_perfil': int((medidores['Ultimo_perfil'] != '').sum()),
            'medidores': medidores,
        })
    return grupos
