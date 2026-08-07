"""
Graficas de barras: energia diaria (suma por dia).

Lee el CSV diario y genera PNG:
  - consumo:     TOTAL_REC  (KWH_REC)
  - generacion:  TOTAL_REC  (KWH_ENT en el perfil)
  - bidireccional: TOTAL_REC, TOTAL_ENT, TOTAL_GEN

Uso:
  python graficar_energia_diaria.py --servicio=consumo diario.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt

from servicio_config import extraer_servicio, normalizar_servicio

COLORES = {
    "REC": "#1a5276",
    "ENT": "#2e86c1",
    "GEN": "#27ae60",
}

SERIES = {
    "consumo": [
        ("TOTAL_REC", "Energía Consumo (KWH_REC)", "REC", "rec"),
    ],
    "generacion": [
        ("TOTAL_REC", "Energía Recibida (KWH_ENT)", "GEN", "gen"),
    ],
    "bidireccional": [
        ("TOTAL_REC", "Energía Entregada (KWH_REC)", "REC", "rec"),
        ("TOTAL_ENT", "Energía Recibida (KWH_ENT)", "ENT", "ent"),
        ("TOTAL_GEN", "Energía Generada (KWH_GEN)", "GEN", "gen"),
    ],
    "neteo": [
        ("TOTAL_REC", "Energía Entregada (KWH_REC)", "REC", "rec"),
        ("TOTAL_ENT", "Energía Recibida (KWH_ENT)", "ENT", "ent"),
        ("CONSUMO_REAL", "Neteo (REC − ENT)", "GEN", "neteo"),
    ],
}


def cargar_diario(ruta: Path) -> tuple[list[str], dict[str, list[float]]]:
    with ruta.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Diario sin encabezado: {ruta}")
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos:
            raise ValueError(f"Falta FECHA en {ruta.name}")
        fechas: list[str] = []
        series: dict[str, list[float]] = {}
        for row in reader:
            fechas.append(row[campos["FECHA"]].strip()[:10])
            for clave, col in campos.items():
                if clave == "FECHA":
                    continue
                series.setdefault(clave, []).append(float(row[col] or 0))
        return fechas, series


def graficar_serie(
    fechas: list[str],
    valores: list[float],
    titulo: str,
    color: str,
    salida: Path,
) -> Path:
    n = len(fechas)
    fig_w = max(10.0, min(24.0, n * 0.28))
    fig, ax = plt.subplots(figsize=(fig_w, 4.5))
    x = list(range(n))
    ax.bar(x, valores, color=color, width=0.8, edgecolor="none")
    ax.set_title(titulo, fontsize=13, fontweight="bold", color="#1a202c", pad=10)
    ax.set_ylabel("kWh")
    ax.set_xlabel("Día")
    # Etiquetas de fecha: mostrar subset para no saturar
    paso = max(1, n // 15)
    ticks = list(range(0, n, paso))
    if n and ticks[-1] != n - 1:
        ticks.append(n - 1)
    ax.set_xticks(ticks)
    ax.set_xticklabels([fechas[i][5:] for i in ticks], rotation=45, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return salida


def generar(diario: Path, servicio: str) -> list[Path]:
    servicio = normalizar_servicio(servicio)
    fechas, series = cargar_diario(diario)
    if not fechas:
        raise ValueError(f"Diario vacio: {diario.name}")

    salidas: list[Path] = []
    base = diario.stem
    # quitar sufijo *_energia_por_dia / *_gdmth_energia_por_dia / *_t01_...
    for suf in (
        "_gdmth_energia_por_dia",
        "_t01_energia_por_dia",
        "_sin_energia_por_dia",
        "_energia_por_dia",
    ):
        if base.endswith(suf):
            base = base[: -len(suf)]
            break

    for col, titulo, color_key, slug in SERIES[servicio]:
        if col not in series:
            print(f"  (omitida {col}: no esta en el diario)")
            continue
        out = diario.with_name(f"{base}_grafica_energia_diaria_{slug}.png")
        graficar_serie(fechas, series[col], titulo, COLORES[color_key], out)
        print(f"  Grafica -> {out.name}")
        salidas.append(out)
    return salidas


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    servicio, resto = extraer_servicio(argv)
    if not resto:
        raise SystemExit(
            "Uso: python graficar_energia_diaria.py [--servicio=...] diario.csv"
        )
    diario = Path(resto[0])
    if not diario.is_absolute():
        diario = Path(__file__).resolve().parent / diario
    if not diario.exists():
        raise SystemExit(f"No existe: {diario}")
    print(f"\nGraficas energia diaria ({servicio}): {diario.name}")
    generar(diario, servicio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
