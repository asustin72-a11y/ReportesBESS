"""Catálogo de tarifas desde reportes CFE (formato plantilla IUSASOL).

Busca CSV en:
  1) <proyecto>/tarifas_cfe/AAAA-MM/{DIST|GDMTH}_AAAA_MM.csv
  2) ReporteadorIUSASOL/data/ReportesTarifasCFE/AAAA-MM/…

Columnas esperadas:
  AÑO, MES, REGIÓN, TARIFA, BASE, INTERMEDIO, SEMIPUNTA, PUNTA, FIJO, CAPACIDAD, HORARIA
"""

from __future__ import annotations

import csv
import re
import shutil
from datetime import date, datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
DIR_LOCAL = DIR / "tarifas_cfe"
try:
    from analisis_perfil.paths import DIR_REPORTES_TARIFAS_CFE as DIR_REPORTEADOR
except ImportError:
    from bess.config.paths import PROJECT_ROOT

    DIR_REPORTEADOR = PROJECT_ROOT / "data" / "ReportesTarifasCFE"

DIVISIONES_DISTRIBUCION = (
    "Baja California",
    "Baja California Sur",
    "Bajío",
    "Centro Occidente",
    "Centro Oriente",
    "Centro Sur",
    "Golfo Centro",
    "Golfo Norte",
    "Jalisco",
    "Noroeste",
    "Norte",
    "Oriente",
    "Peninsular",
    "Sureste",
    "Valle de México Centro",
    "Valle de México Norte",
    "Valle de México Sur",
)

_MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

# Región por defecto alineada al catálogo histórico local.
REGION_DEFAULT = {
    "DIST": "Centro Sur",
    "GDMTH": "Valle de México Norte",
}


def _parse_money(valor: str | float | None) -> float:
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    limpio = re.sub(r"[^\d.\-]", "", str(valor).strip())
    if not limpio:
        return 0.0
    return float(limpio)


def _mes_a_int(mes: str | int) -> int:
    if isinstance(mes, int):
        return mes
    t = str(mes).strip()
    if t.isdigit():
        return int(t)
    return _MESES[t.casefold()]


def _titulo_region(texto: str) -> str:
    partes = (texto or "").strip().split()
    out: list[str] = []
    for i, p in enumerate(partes):
        low = p.casefold()
        if i > 0 and low in {"de", "del", "la", "las", "los", "y", "e"}:
            out.append(low)
        else:
            out.append(p[:1].upper() + p[1:].lower() if p else p)
    return " ".join(out)


def _canon_region(texto: str) -> str:
    key = _titulo_region(texto).casefold()
    for d in DIVISIONES_DISTRIBUCION:
        if d.casefold() == key:
            return d
    return _titulo_region(texto)


def rutas_busqueda(anio: int, mes: int, esquema: str) -> list[Path]:
    codigo = esquema.upper()
    nombre = f"{codigo}_{anio}_{mes:02d}.csv"
    periodo = f"{anio}-{mes:02d}"
    return [
        DIR_LOCAL / periodo / nombre,
        DIR_LOCAL / nombre,
        DIR_REPORTEADOR / periodo / nombre,
    ]


def encontrar_csv(esquema: str, anio: int, mes: int) -> Path | None:
    for ruta in rutas_busqueda(anio, mes, esquema):
        if ruta.is_file():
            return ruta
    return None


def listar_periodos_disponibles(esquema: str) -> list[tuple[int, int, Path]]:
    """Lista (año, mes, ruta) disponibles para DIST/GDMTH."""
    codigo = esquema.upper()
    vistos: dict[tuple[int, int], Path] = {}
    patrones = [
        DIR_LOCAL.glob(f"**/{codigo}_*_*.csv"),
        DIR_REPORTEADOR.glob(f"**/{codigo}_*_*.csv"),
    ]
    for it in patrones:
        for ruta in it:
            m = re.match(rf"{codigo}_(\d{{4}})_(\d{{2}})\.csv$", ruta.name, re.I)
            if not m:
                continue
            clave = (int(m.group(1)), int(m.group(2)))
            if clave not in vistos:
                vistos[clave] = ruta
    return [(a, m, vistos[(a, m)]) for a, m in sorted(vistos)]


def leer_fila_region(ruta: Path, region: str) -> dict[str, str] | None:
    objetivo = _canon_region(region).casefold()
    with ruta.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            reg = _canon_region(row.get("REGIÓN") or row.get("REGION") or "")
            if reg.casefold() == objetivo:
                return {k: (v or "") for k, v in row.items()}
    return None


def precios_desde_reporte(
    esquema: str,
    region: str,
    fecha: str | date | datetime,
):
    """Devuelve PreciosDIST / PreciosGDMTH si hay CSV CFE del mes; si no, None."""
    if isinstance(fecha, datetime):
        dia = fecha.date()
    elif isinstance(fecha, date):
        dia = fecha
    else:
        dia = date.fromisoformat(str(fecha).strip()[:10])

    ruta = encontrar_csv(esquema, dia.year, dia.month)
    if ruta is None:
        return None
    fila = leer_fila_region(ruta, region)
    if fila is None:
        return None

    vigencia = date(dia.year, dia.month, 1)
    base = _parse_money(fila.get("BASE"))
    inter = _parse_money(fila.get("INTERMEDIO"))
    punta = _parse_money(fila.get("PUNTA"))
    fijo = _parse_money(fila.get("FIJO"))
    capacidad = _parse_money(fila.get("CAPACIDAD"))

    if esquema.upper() == "DIST":
        from tarifa_dist import PreciosDIST

        return PreciosDIST(
            fecha_vigencia=vigencia,
            base=base,
            intermedio=inter,
            punta=punta,
            capacidad=capacidad,
            cargo_fijo=fijo,
            suministro=fijo,
        )
    from tarifa_gdmth import PreciosGDMTH

    return PreciosGDMTH(
        fecha_vigencia=vigencia,
        base=base,
        intermedio=inter,
        punta=punta,
        cargo_fijo=fijo,
        capacidad=capacidad,
    )


def sincronizar_desde_reporteador(periodo: str | None = None) -> list[Path]:
    """Copia CSV DIST/GDMTH (y opcionalmente otros) a tarifas_cfe/ local."""
    if not DIR_REPORTEADOR.is_dir():
        raise FileNotFoundError(f"No existe carpeta Reporteador: {DIR_REPORTEADOR}")
    if periodo:
        carpetas = [DIR_REPORTEADOR / periodo]
    else:
        carpetas = sorted(p for p in DIR_REPORTEADOR.iterdir() if p.is_dir())
    copiados: list[Path] = []
    for carpeta in carpetas:
        if not carpeta.is_dir():
            continue
        dest = DIR_LOCAL / carpeta.name
        dest.mkdir(parents=True, exist_ok=True)
        for src in carpeta.glob("*.csv"):
            if src.name.startswith("_"):
                continue
            destino = dest / src.name
            shutil.copy2(src, destino)
            copiados.append(destino)
    return copiados
