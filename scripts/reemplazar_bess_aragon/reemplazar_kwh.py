#!/usr/bin/env python3
"""
Copia Carga (kWh) y Descarga (kWh) de BESS_ARAGON.csv a KWH_REC y KWH_ENT
en BESS_IUSA_ARAGON_Filtrado.csv, fila a fila.

Mapeo:
  Origen  Carga (kWh)    ->  Destino KWH_REC  (col 2)
  Origen  Descarga (kWh) ->  Destino KWH_ENT  (col 3)

La columna Fecha del filtrado no se modifica.

Uso:
  python reemplazar_kwh.py --diagnostico
  python reemplazar_kwh.py --dry-run
  python reemplazar_kwh.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FILTRADO = SCRIPT_DIR / "BESS_IUSA_ARAGON_Filtrado.csv"
DEFAULT_ORIGEN = SCRIPT_DIR / "BESS_ARAGON.csv"

COL_ORIGEN_CARGA = "Carga (kWh)"
COL_ORIGEN_DESCARGA = "Descarga (kWh)"
COL_DESTINO_REC = 2  # KWH_REC (1-based)
COL_DESTINO_ENT = 3  # KWH_ENT (1-based)

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def _leer_csv(ruta: Path) -> pd.DataFrame:
    ultimo_error: Exception | None = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(ruta, encoding=enc)
        except UnicodeDecodeError as exc:
            ultimo_error = exc
    raise ultimo_error or OSError(f"No se pudo leer {ruta}")


def _buscar_columna(df: pd.DataFrame, nombre: str, *, palabras: tuple[str, ...]) -> str:
    if nombre in df.columns:
        return nombre
    norm = {c: str(c).strip().lower() for c in df.columns}
    objetivo = nombre.strip().lower()
    for col, clave in norm.items():
        if clave == objetivo:
            return col
    for col, clave in norm.items():
        if all(p in clave for p in palabras):
            return col
    raise ValueError(
        f"No se encontro la columna {nombre!r}. Columnas disponibles: {list(df.columns)}"
    )


def _leer_origen_datos(ruta: Path) -> tuple[pd.DataFrame, str, str]:
    """Lee BESS_ARAGON con encabezado; devuelve df y nombres de columnas carga/descarga."""
    df = _leer_csv(ruta)
    col_carga = _buscar_columna(df, COL_ORIGEN_CARGA, palabras=("carga", "kwh"))
    col_descarga = _buscar_columna(df, COL_ORIGEN_DESCARGA, palabras=("descarga", "kwh"))
    return df, col_carga, col_descarga


def _nombre_columna_destino(df: pd.DataFrame, indice_1based: int) -> str:
    if indice_1based < 1 or indice_1based > len(df.columns):
        raise ValueError(
            f"Columna destino {indice_1based} invalida; "
            f"el filtrado tiene {len(df.columns)} columnas: {list(df.columns)}"
        )
    return df.columns[indice_1based - 1]


def diagnosticar(ruta_filtrado: Path, ruta_origen: Path) -> None:
    print("=" * 60)
    print("DIAGNOSTICO PASO A PASO")
    print("=" * 60)

    print(f"\n1. Archivo FILTRADO: {ruta_filtrado}")
    df_f = _leer_csv(ruta_filtrado)
    print(f"   Columnas ({len(df_f.columns)}): {list(df_f.columns)}")
    for i, c in enumerate(df_f.columns, start=1):
        print(f"      col {i} (1-based) = {c!r}")
    print(f"   Filas de datos: {len(df_f)}")

    print(f"\n2. Archivo ORIGEN: {ruta_origen}")
    df_o, col_carga, col_descarga = _leer_origen_datos(ruta_origen)
    print(f"   Columnas ({len(df_o.columns)}): {list(df_o.columns)}")
    print(f"   Filas de datos: {len(df_o)}")

    print(f"\n3. MAPEO")
    print(f"   Origen {col_carga!r} -> Destino col {COL_DESTINO_REC} (KWH_REC)")
    print(f"   Origen {col_descarga!r} -> Destino col {COL_DESTINO_ENT} (KWH_ENT)")

    n_f = len(df_f)
    n_o = len(df_o)
    n_usar = min(n_f, n_o)
    print(f"\n4. FILAS")
    print(f"   Filas a copiar: {n_usar}")
    if n_o < n_f:
        print(f"   ADVERTENCIA: el origen tiene {n_f - n_o} filas menos; "
              f"las ultimas {n_f - n_o} del filtrado no se modifican")
    elif n_o > n_f:
        print(f"   ADVERTENCIA: origen tiene {n_o - n_f} filas MAS; se ignoran")

    print(f"\n5. VISTA PREVIA (primeras 5 filas)")
    print(f"   {'Fila':>4}  {'Carga origen':>14}  {'Descarga orig.':>14}  ->  {'KWH_REC':>10}  {'KWH_ENT':>10}")
    for i in range(min(5, n_usar)):
        v_c = df_o.iloc[i][col_carga]
        v_d = df_o.iloc[i][col_descarga]
        print(f"   {i+1:4d}  {str(v_c):>14}  {str(v_d):>14}  ->  {str(v_c):>10}  {str(v_d):>10}")

    carga = pd.to_numeric(df_o.iloc[:n_usar][col_carga], errors="coerce")
    desc = pd.to_numeric(df_o.iloc[:n_usar][col_descarga], errors="coerce")
    print(f"\n6. RESUMEN VALORES A COPIAR")
    print(f"   KWH_REC (carga): {(carga.fillna(0) != 0).sum()} valores distintos de cero")
    print(f"   KWH_ENT (descarga): {(desc.fillna(0) != 0).sum()} valores distintos de cero")
    print(f"   NaN en carga: {carga.isna().sum()}")
    print(f"   NaN en descarga: {desc.isna().sum()}")
    print("=" * 60)


def reemplazar_kwh(
    ruta_filtrado: Path,
    ruta_origen: Path,
    *,
    dry_run: bool = False,
    sin_respaldo: bool = False,
) -> dict:
    if not ruta_filtrado.exists():
        raise FileNotFoundError(f"No existe: {ruta_filtrado}")
    if not ruta_origen.exists():
        raise FileNotFoundError(f"No existe: {ruta_origen}")

    df_filtrado = _leer_csv(ruta_filtrado)
    df_origen, col_carga, col_descarga = _leer_origen_datos(ruta_origen)

    nombre_rec = _nombre_columna_destino(df_filtrado, COL_DESTINO_REC)
    nombre_ent = _nombre_columna_destino(df_filtrado, COL_DESTINO_ENT)

    n_filtrado = len(df_filtrado)
    n_origen = len(df_origen)
    n_usar = min(n_filtrado, n_origen)
    if n_usar == 0:
        raise ValueError("Alguno de los archivos no tiene filas de datos.")

    valores_rec = pd.to_numeric(df_origen.iloc[:n_usar][col_carga], errors="coerce")
    valores_ent = pd.to_numeric(df_origen.iloc[:n_usar][col_descarga], errors="coerce")

    df_filtrado = df_filtrado.copy()
    df_filtrado.loc[: n_usar - 1, nombre_rec] = valores_rec.values
    df_filtrado.loc[: n_usar - 1, nombre_ent] = valores_ent.values

    resumen = {
        "filas_copiadas": n_usar,
        "filas_filtrado": n_filtrado,
        "filas_origen": n_origen,
        "origen_col_carga": col_carga,
        "origen_col_descarga": col_descarga,
        "destino_nombre_rec": nombre_rec,
        "destino_nombre_ent": nombre_ent,
        "filas_filtrado_sin_cambio": max(0, n_filtrado - n_usar),
        "filas_origen_ignoradas": max(0, n_origen - n_usar),
        "salida": str(ruta_filtrado),
    }

    if dry_run:
        print("[DRY-RUN] No se escribio el archivo.")
        diagnosticar(ruta_filtrado, ruta_origen)
        return resumen

    if not sin_respaldo:
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        respaldo = ruta_filtrado.with_suffix(f".bak_{marca}.csv")
        shutil.copy2(ruta_filtrado, respaldo)
        resumen["respaldo"] = str(respaldo)

    df_filtrado.to_csv(ruta_filtrado, index=False)
    return resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Carga/Descarga (kWh) del origen -> KWH_REC/KWH_ENT del filtrado."
    )
    parser.add_argument("--filtrado", type=Path, default=DEFAULT_FILTRADO)
    parser.add_argument("--origen", type=Path, default=DEFAULT_ORIGEN)
    parser.add_argument("--diagnostico", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sin-respaldo", action="store_true")
    args = parser.parse_args(argv)

    filtrado = args.filtrado.resolve()
    origen = args.origen.resolve()

    if args.diagnostico:
        try:
            diagnosticar(filtrado, origen)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        resumen = reemplazar_kwh(
            filtrado, origen, dry_run=args.dry_run, sin_respaldo=args.sin_respaldo
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        print("Listo.")
        print(f"  Salida: {resumen['salida']}")
        print(f"  Filas copiadas: {resumen['filas_copiadas']} de {resumen['filas_filtrado']}")
        print(f"  {resumen['origen_col_carga']!r} -> {resumen['destino_nombre_rec']}")
        print(f"  {resumen['origen_col_descarga']!r} -> {resumen['destino_nombre_ent']}")
        if resumen["filas_filtrado_sin_cambio"]:
            print(f"  Filas del filtrado sin cambio (faltan en origen): {resumen['filas_filtrado_sin_cambio']}")
        if resumen["filas_origen_ignoradas"]:
            print(f"  Filas del origen ignoradas (sobran): {resumen['filas_origen_ignoradas']}")
        if resumen.get("respaldo"):
            print(f"  Respaldo: {resumen['respaldo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
