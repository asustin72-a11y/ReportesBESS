"""
Perfil tipico por dia de la semana y hora.

Lee el CSV de energia por hora (FECHA, HORA, KWH_REC, ...) y promedia
KWH_REC para cada combinacion (dia de la semana, hora 0-23).

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


def _es_por_hora(nombre: str) -> bool:
    bajos = nombre.lower()
    return "_energia_por_hora_" in bajos and bajos.endswith(".csv")


def pedir_archivos(directorio: Path) -> list[Path]:
    csvs = [p for p in sorted(directorio.glob("*.csv")) if _es_por_hora(p.name)]
    print("Archivos de energia por hora:")
    if csvs:
        for i, p in enumerate(csvs, 1):
            print(f"  {i}. {p.name}")
    else:
        print("  (ninguno)")
    print()
    print("Indica que procesar (numero, ruta, o *):")
    respuesta = input("> ").strip()
    if not respuesta:
        raise SystemExit("No se indico ningun archivo.")
    if respuesta == "*":
        if not csvs:
            raise SystemExit("No hay CSV para procesar.")
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


def procesar(ruta: Path) -> tuple[list[dict[str, object]], list[str]]:
    sumas_rec: dict[tuple[int, int], float] = defaultdict(float)
    sumas_ent: dict[tuple[int, int], float] = defaultdict(float)
    sumas_gen: dict[tuple[int, int], float] = defaultdict(float)
    conteos: dict[tuple[int, int], int] = defaultdict(int)

    with ruta.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV sin encabezado: {ruta}")
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        for req in ("FECHA", "HORA", "KWH_REC"):
            if req not in campos:
                raise ValueError(
                    f"Se requieren FECHA, HORA y KWH_REC. Encontradas: {reader.fieldnames}"
                )
        col_fecha = campos["FECHA"]
        col_hora = campos["HORA"]
        col_rec = campos["KWH_REC"]
        col_ent = campos.get("KWH_ENT")
        col_gen = campos.get("KWH_GEN")
        col_real = campos.get("CONSUMO_REAL")
        bidi = col_ent is not None

        sumas_real: dict[tuple[int, int], float] = defaultdict(float)
        for row in reader:
            dia = date.fromisoformat(row[col_fecha].strip()[:10])
            hora = int(row[col_hora])
            if not 0 <= hora <= 23:
                raise ValueError(f"HORA fuera de rango: {hora}")
            clave = (dia.weekday(), hora)
            sumas_rec[clave] += float(row[col_rec])
            if bidi:
                sumas_ent[clave] += float(row[col_ent] or 0)
                if col_gen:
                    sumas_gen[clave] += float(row[col_gen] or 0)
            if col_real:
                sumas_real[clave] += float(row[col_real] or 0)
            conteos[clave] += 1

    filas: list[dict[str, object]] = []
    for wd, nombre in enumerate(DIAS):
        for hora in range(24):
            n = conteos.get((wd, hora), 0)
            fila: dict[str, object] = {
                "DIA_SEMANA": nombre,
                "HORA": hora,
                "N_DIAS": n,
                "CONSUMO_TIPICO": f"{(sumas_rec[(wd, hora)] / n) if n else 0.0:.6f}",
            }
            if bidi:
                fila["ENTREGA_TIPICA"] = (
                    f"{(sumas_ent[(wd, hora)] / n) if n else 0.0:.6f}"
                )
                if col_gen:
                    fila["GENERACION_TIPICA"] = (
                        f"{(sumas_gen[(wd, hora)] / n) if n else 0.0:.6f}"
                    )
            if col_real and n:
                fila["CONSUMO_REAL_TIPICO"] = f"{sumas_real[(wd, hora)] / n:.6f}"
            elif bidi:
                rec = float(fila["CONSUMO_TIPICO"])
                ent = float(fila.get("ENTREGA_TIPICA", 0) or 0)
                gen = float(fila.get("GENERACION_TIPICA", 0) or 0)
                fila["CONSUMO_REAL_TIPICO"] = f"{rec + gen - ent:.6f}"
            else:
                fila["CONSUMO_REAL_TIPICO"] = fila["CONSUMO_TIPICO"]
            filas.append(fila)

    campos_out = ["DIA_SEMANA", "HORA", "N_DIAS", "CONSUMO_TIPICO"]
    if bidi:
        campos_out.append("ENTREGA_TIPICA")
        if col_gen:
            campos_out.append("GENERACION_TIPICA")
    campos_out.append("CONSUMO_REAL_TIPICO")
    return filas, campos_out


def ruta_salida(entrada: Path) -> Path:
    stem = entrada.stem
    # ..._energia_por_hora_dist -> ..._perfil_tipico_hora_dist
    if "_energia_por_hora_" in stem:
        base, esquema = stem.rsplit("_energia_por_hora_", 1)
        return entrada.with_name(f"{base}_perfil_tipico_hora_{esquema}.csv")
    return entrada.with_name(f"{stem}_perfil_tipico_hora.csv")


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
        filas, campos = procesar(entrada)
        out = ruta_salida(entrada)
        escribir(out, filas, campos)
        print(f"  Salida -> {out.name}  ({len(filas)} filas = 7 dias x 24 horas)")
        print("  Totales tipicos del dia (suma 24 h):")
        bidi = "ENTREGA_TIPICA" in campos
        for wd, nombre in enumerate(DIAS):
            total_r = sum(
                float(filas[wd * 24 + h]["CONSUMO_TIPICO"]) for h in range(24)
            )
            linea = f"    {nombre:<10}  rec={total_r:.2f}"
            if bidi:
                total_e = sum(
                    float(filas[wd * 24 + h]["ENTREGA_TIPICA"]) for h in range(24)
                )
                linea += f"  ent={total_e:.2f}"
            print(linea)

    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
