"""
Consumo tipico por dia de la semana a partir del reporte diario.

Lee un CSV diario (FECHA, ..., TOTAL_REC) y genera un CSV con el promedio
de TOTAL_REC para cada dia de la semana (Lunes..Domingo).

Script 100 % autonomo.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

DIAS = (
    "Lunes",
    "Martes",
    "Miercoles",
    "Jueves",
    "Viernes",
    "Sabado",
    "Domingo",
)


def _es_diario(nombre: str) -> bool:
    return nombre.endswith("_energia_por_dia.csv") or nombre.endswith(
        "_gdmth_energia_por_dia.csv"
    )


def pedir_archivos(directorio: Path) -> list[Path]:
    csvs = [p for p in sorted(directorio.glob("*.csv")) if _es_diario(p.name)]

    print("Archivos diarios en el directorio:")
    if csvs:
        for i, p in enumerate(csvs, 1):
            print(f"  {i}. {p.name}")
    else:
        print("  (ninguno)")

    print()
    print("Indica que procesar:")
    print("  - numeros separados por coma (ej. 1 o 1,2)")
    print("  - rutas absolutas/relativas separadas por coma")
    print("  - * para todos los listados")
    respuesta = input("> ").strip()
    if not respuesta:
        raise SystemExit("No se indico ningun archivo.")

    if respuesta == "*":
        if not csvs:
            raise SystemExit("No hay CSV diarios para procesar.")
        return csvs

    seleccionados: list[Path] = []
    for parte in respuesta.split(","):
        parte = parte.strip().strip('"').strip("'")
        if not parte:
            continue
        if parte.isdigit():
            idx = int(parte)
            if idx < 1 or idx > len(csvs):
                raise SystemExit(f"Indice fuera de rango: {idx}")
            seleccionados.append(csvs[idx - 1])
        else:
            p = Path(parte)
            if not p.is_absolute():
                p = directorio / p
            if not p.exists():
                raise SystemExit(f"No existe: {p}")
            seleccionados.append(p)
    if not seleccionados:
        raise SystemExit("No se indico ningun archivo valido.")
    return seleccionados


def procesar_diario(ruta: Path) -> tuple[list[dict[str, object]], list[str]]:
    sumas_rec: dict[int, float] = defaultdict(float)
    sumas_ent: dict[int, float] = defaultdict(float)
    sumas_gen: dict[int, float] = defaultdict(float)
    conteos: dict[int, int] = defaultdict(int)

    with ruta.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV sin encabezado: {ruta}")
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos or "TOTAL_REC" not in campos:
            raise ValueError(
                f"Se requieren columnas FECHA y TOTAL_REC. Encontradas: {reader.fieldnames}"
            )
        col_fecha = campos["FECHA"]
        col_rec = campos["TOTAL_REC"]
        col_ent = campos.get("TOTAL_ENT")
        col_gen = campos.get("TOTAL_GEN")
        col_real = campos.get("CONSUMO_REAL")
        bidi = col_ent is not None

        sumas_real: dict[int, float] = defaultdict(float)
        for row in reader:
            dia = date.fromisoformat(row[col_fecha].strip()[:10])
            wd = dia.weekday()
            sumas_rec[wd] += float(row[col_rec])
            if bidi:
                sumas_ent[wd] += float(row[col_ent] or 0)
                if col_gen:
                    sumas_gen[wd] += float(row[col_gen] or 0)
            if col_real:
                sumas_real[wd] += float(row[col_real] or 0)
            conteos[wd] += 1

    filas = []
    for wd, nombre in enumerate(DIAS):
        n = conteos.get(wd, 0)
        fila: dict[str, object] = {
            "DIA_SEMANA": nombre,
            "N_DIAS": n,
            "CONSUMO_TIPICO": f"{(sumas_rec[wd] / n) if n else 0.0:.6f}",
        }
        if bidi:
            fila["ENTREGA_TIPICA"] = f"{(sumas_ent[wd] / n) if n else 0.0:.6f}"
            if col_gen:
                fila["GENERACION_TIPICA"] = f"{(sumas_gen[wd] / n) if n else 0.0:.6f}"
        if col_real and n:
            fila["CONSUMO_REAL_TIPICO"] = f"{sumas_real[wd] / n:.6f}"
        elif bidi:
            rec = float(fila["CONSUMO_TIPICO"])
            ent = float(fila.get("ENTREGA_TIPICA", 0) or 0)
            gen = float(fila.get("GENERACION_TIPICA", 0) or 0)
            fila["CONSUMO_REAL_TIPICO"] = f"{rec + gen - ent:.6f}"
        else:
            fila["CONSUMO_REAL_TIPICO"] = fila["CONSUMO_TIPICO"]
        filas.append(fila)

    campos_out = ["DIA_SEMANA", "N_DIAS", "CONSUMO_TIPICO"]
    if bidi:
        campos_out.append("ENTREGA_TIPICA")
        if col_gen:
            campos_out.append("GENERACION_TIPICA")
    campos_out.append("CONSUMO_REAL_TIPICO")
    return filas, campos_out


def ruta_salida(entrada: Path) -> Path:
    stem = entrada.stem
    # Evita duplicar sufijos largos: ..._energia_por_dia -> ..._consumo_tipico_semana
    if stem.endswith("_energia_por_dia"):
        base = stem[: -len("_energia_por_dia")]
    elif stem.endswith("_gdmth_energia_por_dia"):
        base = stem[: -len("_energia_por_dia")]  # conserva _gdmth
    else:
        base = stem
    return entrada.with_name(f"{base}_consumo_tipico_semana.csv")


def escribir(
    ruta_out: Path, filas: list[dict[str, object]], campos: list[str]
) -> None:
    with ruta_out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    directorio = Path(__file__).resolve().parent

    if argv:
        entradas = []
        for a in argv:
            p = Path(a)
            if not p.is_absolute():
                p = directorio / p
            if not p.exists():
                print(f"ERROR: no existe {p}", file=sys.stderr)
                return 1
            entradas.append(p)
    else:
        entradas = pedir_archivos(directorio)

    for entrada in entradas:
        print(f"\nProcesando: {entrada.name}")
        filas, campos = procesar_diario(entrada)
        out = ruta_salida(entrada)
        escribir(out, filas, campos)
        print(f"  Salida -> {out.name}")
        for fila in filas:
            linea = (
                f"    {fila['DIA_SEMANA']:<10}  "
                f"n={fila['N_DIAS']:<4}  "
                f"rec={fila['CONSUMO_TIPICO']}"
            )
            if "ENTREGA_TIPICA" in fila:
                linea += f"  ent={fila['ENTREGA_TIPICA']}"
            if "GENERACION_TIPICA" in fila:
                linea += f"  gen={fila['GENERACION_TIPICA']}"
            print(linea)

    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
