"""
Graficas del perfil tipico por dia de la semana y hora.

Acepta:
  - perfil tipico: DIA_SEMANA, HORA, CONSUMO_TIPICO
  - energia por hora: FECHA, HORA, KWH_REC  (promedia por dia de semana)

Genera 8 PNG: una por dia + una comparativa.
Script 100 % autonomo (requiere matplotlib).
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt

DIAS = (
    "Lunes",
    "Martes",
    "Miercoles",
    "Jueves",
    "Viernes",
    "Sabado",
    "Domingo",
)

COLORES = {
    "Lunes": "#1f4e79",
    "Martes": "#c45c26",
    "Miercoles": "#548235",
    "Jueves": "#7030a0",
    "Viernes": "#5b9bd5",
    "Sabado": "#ed7d31",
    "Domingo": "#7f8fa6",
}


def _es_entrada_grafica(nombre: str) -> bool:
    bajos = nombre.lower()
    if not bajos.endswith(".csv"):
        return False
    return (
        "_perfil_tipico_hora_" in bajos
        or "_energia_por_hora_" in bajos
    )


def pedir_archivos(directorio: Path) -> list[Path]:
    csvs = [p for p in sorted(directorio.glob("*.csv")) if _es_entrada_grafica(p.name)]
    print("Archivos de perfil tipico o energia por hora:")
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


def _perfil_desde_tipico(
    campos: dict[str, str], reader: csv.DictReader
) -> dict[str, list[float]]:
    datos: dict[str, dict[int, float]] = defaultdict(dict)
    col_dia = campos["DIA_SEMANA"]
    col_hora = campos["HORA"]
    col_kwh = campos["CONSUMO_TIPICO"]
    for row in reader:
        dia = row[col_dia].strip()
        hora = int(row[col_hora])
        datos[dia][hora] = float(row[col_kwh])

    perfil: dict[str, list[float]] = {}
    for dia in DIAS:
        if dia not in datos:
            raise ValueError(f"Falta el dia '{dia}' en el archivo")
        perfil[dia] = [datos[dia].get(h, 0.0) for h in range(24)]
    return perfil


def _perfil_desde_energia_hora(
    campos: dict[str, str], reader: csv.DictReader
) -> dict[str, list[float]]:
    """Promedia KWH_REC por (dia de semana, hora) a partir de FECHA,HORA,KWH_REC."""
    sumas: dict[tuple[int, int], float] = defaultdict(float)
    conteos: dict[tuple[int, int], int] = defaultdict(int)
    col_fecha = campos["FECHA"]
    col_hora = campos["HORA"]
    col_kwh = campos["KWH_REC"]

    for row in reader:
        dia = date.fromisoformat(row[col_fecha].strip()[:10])
        hora = int(row[col_hora])
        if not 0 <= hora <= 23:
            raise ValueError(f"HORA fuera de rango: {hora}")
        clave = (dia.weekday(), hora)
        sumas[clave] += float(row[col_kwh])
        conteos[clave] += 1

    perfil: dict[str, list[float]] = {}
    for wd, nombre in enumerate(DIAS):
        valores = []
        for hora in range(24):
            n = conteos.get((wd, hora), 0)
            valores.append((sumas[(wd, hora)] / n) if n else 0.0)
        if all(v == 0.0 for v in valores) and not any(
            conteos.get((wd, h), 0) for h in range(24)
        ):
            raise ValueError(f"No hay datos para '{nombre}' en el archivo")
        perfil[nombre] = valores
    return perfil


def cargar_perfil(ruta: Path) -> dict[str, list[float]]:
    """dia -> lista de 24 consumos (indice = HORA 0..23)."""
    with ruta.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV sin encabezado: {ruta}")
        campos = {c.strip().upper(): c for c in reader.fieldnames}

        if {"DIA_SEMANA", "HORA", "CONSUMO_TIPICO"} <= campos.keys():
            print("  Entrada: perfil tipico (ya promediado)")
            return _perfil_desde_tipico(campos, reader)

        if {"FECHA", "HORA", "KWH_REC"} <= campos.keys():
            print("  Entrada: energia por hora (se promedia por dia de semana)")
            return _perfil_desde_energia_hora(campos, reader)

        raise ValueError(
            "Formato no reconocido. Se acepta:\n"
            "  - DIA_SEMANA, HORA, CONSUMO_TIPICO\n"
            "  - FECHA, HORA, KWH_REC\n"
            f"Encontradas: {reader.fieldnames}"
        )


def _estilo_ejes(ax, ymax: float) -> None:
    ax.set_xlabel("Hora")
    ax.set_ylabel("Consumo tipico (kWh)")
    ax.set_xticks(range(0, 24))
    ax.set_xlim(-0.5, 23.5)
    ax.set_ylim(0, ymax * 1.08 if ymax > 0 else 1)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def graficar_dia(dia: str, valores: list[float], ruta_out: Path, ymax: float) -> None:
    horas = list(range(24))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(
        horas,
        valores,
        color=COLORES[dia],
        linewidth=2.2,
        marker="o",
        markersize=4,
        label=dia,
    )
    ax.set_title(f"Perfil tipico — {dia}")
    _estilo_ejes(ax, ymax)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(ruta_out, dpi=140)
    plt.close(fig)


def graficar_comparativa(perfil: dict[str, list[float]], ruta_out: Path, ymax: float) -> None:
    horas = list(range(24))
    fig, ax = plt.subplots(figsize=(11, 6))
    for dia in DIAS:
        ax.plot(
            horas,
            perfil[dia],
            color=COLORES[dia],
            linewidth=2.0,
            label=dia,
        )
    ax.set_title("Perfil tipico por dia de la semana")
    _estilo_ejes(ax, ymax)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(ruta_out, dpi=140, bbox_inches="tight")
    plt.close(fig)


def carpeta_salida(entrada: Path) -> Path:
    stem = entrada.stem
    if "_perfil_tipico_hora_" in stem:
        base, esquema = stem.rsplit("_perfil_tipico_hora_", 1)
        nombre = f"{base}_graficas_perfil_tipico_{esquema}"
    elif "_energia_por_hora_" in stem:
        base, esquema = stem.rsplit("_energia_por_hora_", 1)
        nombre = f"{base}_graficas_perfil_tipico_{esquema}"
    else:
        nombre = f"{stem}_graficas_perfil_tipico"
    out = entrada.with_name(nombre)
    out.mkdir(parents=True, exist_ok=True)
    return out


def generar(entrada: Path) -> Path:
    perfil = cargar_perfil(entrada)
    ymax = max(max(v) for v in perfil.values())
    carpeta = carpeta_salida(entrada)

    for dia in DIAS:
        ruta = carpeta / f"perfil_{dia.lower()}.png"
        graficar_dia(dia, perfil[dia], ruta, ymax)
        print(f"  {ruta.name}")

    ruta_cmp = carpeta / "perfil_comparativa.png"
    graficar_comparativa(perfil, ruta_cmp, ymax)
    print(f"  {ruta_cmp.name}")
    return carpeta


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
        print(f"\nGraficando: {entrada.name}")
        carpeta = generar(entrada)
        print(f"  Carpeta -> {carpeta}")

    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
