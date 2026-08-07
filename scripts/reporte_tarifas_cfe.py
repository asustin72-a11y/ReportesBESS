#!/usr/bin/env python3
"""Genera un CSV por tarifa CFE en formato de catálogo IUSASOL.

Columnas:
  AÑO, MES, REGIÓN, TARIFA, BASE, INTERMEDIO, SEMIPUNTA, PUNTA, FIJO, CAPACIDAD, HORARIA

  python scripts/reporte_tarifas_cfe.py --anio 2026 --mes 8
  python scripts/reporte_tarifas_cfe.py --anio 2026 --mes 8 --codigos DAC,PDBT
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import DIRECTORIO_BASE
from bess.data.ingest.cfe import (
    CfeTarifasError,
    FamiliaForm,
    consultar_geo_por_divisiones,
    consultar_tarifa_catalogo,
    enumerar_geo_completo,
    tarifa_por_codigo,
)
from bess.data.ingest.cfe.catalog import BASE_INDUSTRIA, BASE_NEGOCIO

CODIGOS_REPORTE = ("DAC", "PDBT", "GDBT", "GDMTO", "GDMTH", "DIST")
DIR_REPORTES = DIRECTORIO_BASE / "ReportesTarifasCFE"

# 17 divisiones / regiones de distribución (oficio CNE TFSB).
# Se excluyen etiquetas compuestas del portal CFE ("X y Y", "X, Y y Z").
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
_DIVISIONES_CF = {d.casefold(): d for d in DIVISIONES_DISTRIBUCION}

COLUMNAS = (
    "AÑO",
    "MES",
    "REGIÓN",
    "TARIFA",
    "BASE",
    "INTERMEDIO",
    "SEMIPUNTA",
    "PUNTA",
    "FIJO",
    "CAPACIDAD",
    "HORARIA",
)

_MESES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

# Tarifas con periodos horarios Base / Intermedio / Punta.
_TARIFAS_HORARIAS = frozenset({"GDMTH", "DIST", "DIT"})


def _log(msg: str) -> None:
    print(msg, flush=True)


def _ruta_csv(salida: Path, codigo: str, anio: int, mes: int) -> Path:
    return salida / f"{codigo}_{anio}_{mes:02d}.csv"


def _hub_geo(defn) -> str:
    if BASE_INDUSTRIA in defn.url:
        return "industria"
    if BASE_NEGOCIO in defn.url:
        return "negocio"
    return "otro"


def _ruta_cache_geo(salida: Path, hub: str, anio: int, mes: int) -> Path:
    return salida / f"_cache_geo_{hub}_{anio}_{mes:02d}.json"


def _fmt_money(valor: Any) -> str:
    if valor is None or valor == "":
        return ""
    try:
        num = float(valor)
    except (TypeError, ValueError):
        return ""
    return f"${num:.4f}"


def _titulo_region(texto: str) -> str:
    """BAJÍO → Bajío; VALLE DE MÉXICO NORTE → Valle de México Norte."""
    partes = (texto or "").strip().split()
    out: list[str] = []
    for i, p in enumerate(partes):
        low = p.casefold()
        if i > 0 and low in {"de", "del", "la", "las", "los", "y", "e"}:
            out.append(low)
        else:
            out.append(p[:1].upper() + p[1:].lower() if p else p)
    return " ".join(out)


def _es_division_oficial(division: str) -> bool:
    """True solo para las 17 divisiones de distribución CNE (sin compuestos)."""
    return _titulo_region(division).casefold() in _DIVISIONES_CF


def _nombre_division_oficial(division: str) -> str:
    """Normaliza al nombre canónico del oficio CNE."""
    key = _titulo_region(division).casefold()
    return _DIVISIONES_CF.get(key, _titulo_region(division))


def _fila_vacia(anio: int, mes: int, region: str, tarifa: str) -> dict[str, str]:
    return {
        "AÑO": str(anio),
        "MES": _MESES[mes],
        "REGIÓN": region,
        "TARIFA": tarifa,
        "BASE": "",
        "INTERMEDIO": "",
        "SEMIPUNTA": "",
        "PUNTA": "",
        "FIJO": "",
        "CAPACIDAD": "",
        "HORARIA": "SI" if tarifa.upper() in _TARIFAS_HORARIAS else "NO",
    }


def _fila_desde_cargos(
    *,
    anio: int,
    mes: int,
    region: str,
    tarifa: str,
    cargos: dict[str, float],
) -> dict[str, str]:
    fila = _fila_vacia(anio, mes, region, tarifa)
    # Energía de un solo bloque → BASE.
    if "Energia" in cargos and "Base" not in cargos:
        fila["BASE"] = _fmt_money(cargos["Energia"])
    if "Base" in cargos:
        fila["BASE"] = _fmt_money(cargos["Base"])
    if "Intermedio" in cargos:
        fila["INTERMEDIO"] = _fmt_money(cargos["Intermedio"])
    if "Semipunta" in cargos:
        fila["SEMIPUNTA"] = _fmt_money(cargos["Semipunta"])
    if "Punta" in cargos:
        fila["PUNTA"] = _fmt_money(cargos["Punta"])
    if "CargoFijo" in cargos:
        fila["FIJO"] = _fmt_money(cargos["CargoFijo"])
    elif "Suministro" in cargos:
        fila["FIJO"] = _fmt_money(cargos["Suministro"])
    if "Capacidad" in cargos:
        fila["CAPACIDAD"] = _fmt_money(cargos["Capacidad"])
    # Si hay Base+Intermedio+Punta, marcar horaria aunque el código no esté listado.
    if fila["INTERMEDIO"] and fila["PUNTA"]:
        fila["HORARIA"] = "SI"
    return fila


def _escribir_csv(ruta: Path, filas: list[dict[str, str]]) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNAS), extrasaction="ignore")
        writer.writeheader()
        for fila in filas:
            writer.writerow({c: fila.get(c, "") for c in COLUMNAS})
    return ruta


def _cargar_o_enumerar_geo(
    defn,
    *,
    anio: int,
    mes: int,
    salida: Path,
    cache: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    hub = _hub_geo(defn)
    if hub in cache:
        return cache[hub]
    ruta = _ruta_cache_geo(salida, hub, anio, mes)
    if ruta.is_file():
        data = json.loads(ruta.read_text(encoding="utf-8"))
        triples = data.get("triples") or []
        _log(f"  cache geo {hub}: {len(triples)} combinaciones ({ruta.name})")
        cache[hub] = triples
        return triples

    _log(f"  enumerando geo hub={hub}…")
    triples = enumerar_geo_completo(
        defn.url,
        anio=anio,
        mes=mes,
        progreso=lambda m: _log(f"    {m}"),
    )
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(
            {"hub": hub, "anio": anio, "mes": mes, "triples": triples},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cache[hub] = triples
    _log(f"  cache guardado: {ruta.name} ({len(triples)} combinaciones)")
    return triples


def _representantes_por_division(
    triples: list[dict[str, str]],
    *,
    solo_oficiales: bool = True,
) -> list[dict[str, str]]:
    """Un representante por división. Por defecto solo las 17 del oficio CNE."""
    vistos: set[str] = set()
    reps: list[dict[str, str]] = []
    for t in triples:
        div = t["division"]
        if solo_oficiales and not _es_division_oficial(div):
            continue
        clave = _titulo_region(div).casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        reps.append(t)
    if solo_oficiales and len(reps) < len(DIVISIONES_DISTRIBUCION):
        faltan = [
            d
            for d in DIVISIONES_DISTRIBUCION
            if d.casefold() not in vistos
        ]
        if faltan:
            _log(
                "  AVISO: no se localizaron en CFE: " + ", ".join(faltan)
            )
    return reps


def _base_dac_para_mes(fila_tabla: dict[str, Any], mes: int) -> Any:
    """Una sola BASE: energía plana, o verano/fuera según mes (May–Oct ≈ verano)."""
    if fila_tabla.get("Energía ($/kWh)") not in (None, ""):
        return fila_tabla["Energía ($/kWh)"]
    verano = fila_tabla.get("Energía Verano ($/kWh)")
    fuera = fila_tabla.get("Energía Fuera de Verano ($/kWh)")
    if verano in (None, "") and fuera in (None, ""):
        return ""
    if 5 <= mes <= 10:
        return verano if verano not in (None, "") else fuera
    return fuera if fuera not in (None, "") else verano


def generar_dac(anio: int, mes: int, salida: Path) -> Path:
    _log(f"[{anio}-{mes:02d}] DAC: consultando regiones…")
    resultado = consultar_tarifa_catalogo("DAC", anio=anio, mes=mes)
    filas: list[dict[str, str]] = []
    for tabla in resultado.tablas:
        for fila in tabla.filas:
            region = _titulo_region(str(fila.get("Región") or ""))
            out = _fila_vacia(anio, mes, region, "DAC")
            out["BASE"] = _fmt_money(_base_dac_para_mes(fila, mes))
            out["FIJO"] = _fmt_money(fila.get("Cargo Fijo ($/mes)"))
            filas.append(out)
    ruta = _ruta_csv(salida, "DAC", anio, mes)
    _escribir_csv(ruta, filas)
    _log(f"  → {ruta.name} ({len(filas)} regiones DAC)")
    return ruta


def generar_geo(
    codigo: str,
    anio: int,
    mes: int,
    salida: Path,
    cache_geo: dict[str, list[dict[str, str]]],
) -> Path:
    defn = tarifa_por_codigo(codigo)
    if defn is None or defn.familia != FamiliaForm.GEO:
        raise CfeTarifasError(f"{codigo} no es una tarifa GEO del catálogo.")

    _log(f"[{anio}-{mes:02d}] {codigo}: 17 divisiones de distribución…")
    triples = _cargar_o_enumerar_geo(
        defn, anio=anio, mes=mes, salida=salida, cache=cache_geo
    )
    reps = _representantes_por_division(triples, solo_oficiales=True)
    _log(f"  {len(reps)} divisiones oficiales a consultar")

    tasas = consultar_geo_por_divisiones(
        defn,
        anio=anio,
        mes=mes,
        representantes=reps,
        progreso=lambda m: _log(f"  {m}"),
    )

    filas: list[dict[str, str]] = []
    for rep in reps:
        division = rep["division"]
        region = _nombre_division_oficial(division)
        res = tasas.get(division)
        if res is None:
            filas.append(_fila_vacia(anio, mes, region, codigo))
            continue
        filas.append(
            _fila_desde_cargos(
                anio=anio,
                mes=mes,
                region=region,
                tarifa=codigo,
                cargos=res.cargos,
            )
        )

    # Orden del oficio CNE.
    orden = {d.casefold(): i for i, d in enumerate(DIVISIONES_DISTRIBUCION)}
    filas.sort(key=lambda f: orden.get(f["REGIÓN"].casefold(), 999))
    ruta = _ruta_csv(salida, codigo, anio, mes)
    _escribir_csv(ruta, filas)
    _log(f"  → {ruta.name} ({len(filas)} divisiones)")
    return ruta


def generar_reporte(
    *,
    anio: int,
    mes: int,
    codigos: list[str],
    salida: Path,
) -> list[Path]:
    rutas: list[Path] = []
    cache_geo: dict[str, list[dict[str, str]]] = {}
    for codigo in codigos:
        codigo = codigo.strip().upper()
        defn = tarifa_por_codigo(codigo)
        if defn is None:
            raise CfeTarifasError(f"Código desconocido: {codigo}")
        if defn.familia == FamiliaForm.DAC:
            rutas.append(generar_dac(anio, mes, salida))
        elif defn.familia == FamiliaForm.GEO:
            rutas.append(
                generar_geo(codigo, anio, mes, salida, cache_geo=cache_geo)
            )
        else:
            raise CfeTarifasError(
                f"{codigo} no soportada en este reporte (familia {defn.familia.value})."
            )
    return rutas


def main() -> int:
    hoy = date.today()
    parser = argparse.ArgumentParser(
        description="Reporte CSV por tarifa CFE (formato AÑO/MES/REGIÓN/…).",
    )
    parser.add_argument("--anio", type=int, default=hoy.year)
    parser.add_argument("--mes", type=int, default=hoy.month)
    parser.add_argument(
        "--codigos",
        default=",".join(CODIGOS_REPORTE),
        help=f"Lista separada por comas (default: {','.join(CODIGOS_REPORTE)})",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help="Carpeta de salida (default: data/ReportesTarifasCFE/AAAA-MM)",
    )
    args = parser.parse_args()
    codigos = [c.strip() for c in args.codigos.split(",") if c.strip()]
    salida = args.salida or (DIR_REPORTES / f"{args.anio}-{args.mes:02d}")
    salida.mkdir(parents=True, exist_ok=True)

    _log(f"Salida: {salida}")
    try:
        rutas = generar_reporte(
            anio=int(args.anio),
            mes=int(args.mes),
            codigos=codigos,
            salida=salida,
        )
    except CfeTarifasError as exc:
        _log(f"ERROR CFE: {exc}")
        return 1
    except Exception as exc:
        _log(f"ERROR: {exc}")
        return 1

    _log("")
    _log("Archivos generados:")
    for ruta in rutas:
        _log(f"  {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
