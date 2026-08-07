"""
Energia por hora a partir del perfil cincominutal.

Agrupa 12 perfiles de 5 min por hora (convencion CFE de hora de cierre),
suma KWH_REC y asigna el periodo tarifario (Base / Intermedio / Punta).

Dia operativo: 00:05 D ... 00:00 D+1.
Esquema: DIST o GDMTH (Region Central).
Script 100 % autonomo.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

FMT_FECHA = "%Y-%m-%d %H:%M:%S"
ESQUEMAS = ("DIST", "GDMTH", "T01", "SIN")

from servicio_config import (  # noqa: E402
    columna_fuente,
    es_bidireccional,
    es_neteo,
    extraer_servicio,
    usa_rec_ent,
)


# ---------------------------------------------------------------------------
# Festivos y dia operativo (comunes)
# ---------------------------------------------------------------------------

def es_festivo(fecha: date) -> bool:
    festivos_fijos = {(1, 1), (2, 5), (3, 21), (5, 1), (9, 16), (11, 20), (12, 25)}
    return (fecha.month, fecha.day) in festivos_fijos


def fecha_operativa(dt: datetime) -> date:
    if dt.hour == 0 and dt.minute < 5:
        return (dt - timedelta(days=1)).date()
    return dt.date()


def _bucket_hora(dt: datetime) -> tuple[date, int]:
    """Devuelve (fecha_para_periodo, hora_cfe 0..23) con la convencion de cierre.

    minuto == 0 -> esa hora de reloj;
    minuto != 0 -> hora + 1; si llega a 24 -> hora 0 del dia siguiente.
    """
    fecha = dt.date()
    hora_base = dt.hour if dt.minute == 0 else dt.hour + 1
    if hora_base == 24:
        hora_base = 0
        fecha = fecha + timedelta(days=1)
    hora_archivo = hora_base if hora_base > 0 else 24
    hora_cfe = hora_archivo - 1
    if hora_cfe < 0:
        hora_cfe = 0
    return fecha, hora_cfe


# ---------------------------------------------------------------------------
# DIST Region Central
# ---------------------------------------------------------------------------

def obtener_temporada_dist(fecha: date) -> int:
    mes, dia, anio = fecha.month, fecha.day, fecha.year

    primer_domingo_abril = 7
    for d in range(1, 8):
        if datetime(anio, 4, d).weekday() == 6:
            primer_domingo_abril = d
            break

    ultimo_domingo_octubre = 25
    for d in range(31, 24, -1):
        if datetime(anio, 10, d).weekday() == 6:
            ultimo_domingo_octubre = d
            break

    sabado_antes_abril = primer_domingo_abril - 1
    if mes == 2 or mes == 3 or (mes == 4 and dia <= sabado_antes_abril):
        return 1
    if (mes == 4 and dia >= primer_domingo_abril) or mes in (5, 6) or mes == 7:
        return 2
    sabado_antes_octubre = ultimo_domingo_octubre - 1
    if mes == 8 or mes == 9 or (mes == 10 and dia <= sabado_antes_octubre):
        return 3
    return 4


def periodo_dist(fecha: date, hora_cfe: int) -> str:
    temporada = obtener_temporada_dist(fecha)
    dia_semana = fecha.weekday()
    es_domingo = dia_semana == 6
    es_sabado = dia_semana == 5
    es_fest = es_festivo(fecha)
    hora = hora_cfe

    if es_domingo or es_fest:
        if temporada in (1, 3):
            return "Base" if (0 <= hora <= 18 or hora == 23) else "Intermedio"
        if temporada == 2:
            return "Base" if 0 <= hora <= 18 else "Intermedio"
        return "Base" if 0 <= hora <= 17 else "Intermedio"

    if es_sabado:
        if temporada in (1, 3):
            return "Base" if 0 <= hora <= 6 else "Intermedio"
        if temporada == 2:
            if hora == 0:
                return "Intermedio"
            if 1 <= hora <= 6:
                return "Base"
            return "Intermedio"
        if 0 <= hora <= 7:
            return "Base"
        if 8 <= hora <= 18:
            return "Intermedio"
        if 19 <= hora <= 20:
            return "Punta"
        return "Intermedio"

    if temporada in (1, 3):
        if 0 <= hora <= 5:
            return "Base"
        if 6 <= hora <= 18:
            return "Intermedio"
        if 19 <= hora <= 21:
            return "Punta"
        return "Intermedio"
    if temporada == 2:
        if hora == 0:
            return "Intermedio"
        if 1 <= hora <= 5:
            return "Base"
        if 6 <= hora <= 19:
            return "Intermedio"
        if 20 <= hora <= 21:
            return "Punta"
        return "Intermedio"
    if 0 <= hora <= 5:
        return "Base"
    if 6 <= hora <= 17:
        return "Intermedio"
    if 18 <= hora <= 21:
        return "Punta"
    return "Intermedio"


# ---------------------------------------------------------------------------
# GDMTH Region Central
# ---------------------------------------------------------------------------

def _primer_domingo_abril(anio: int) -> date:
    for dia in range(1, 8):
        if datetime(anio, 4, dia).weekday() == 6:
            return date(anio, 4, dia)
    return date(anio, 4, 7)


def _ultimo_domingo_octubre(anio: int) -> date:
    for dia in range(31, 24, -1):
        if datetime(anio, 10, dia).weekday() == 6:
            return date(anio, 10, dia)
    return date(anio, 10, 25)


def obtener_temporada_gdmth(fecha: date) -> int:
    inicio = _primer_domingo_abril(fecha.year)
    fin = _ultimo_domingo_octubre(fecha.year) - timedelta(days=1)
    return 1 if inicio <= fecha <= fin else 2


def _en_rango(hora: int, inicio: int, fin: int) -> bool:
    return inicio <= hora < fin


def periodo_gdmth(fecha: date, hora_cfe: int) -> str:
    temporada = obtener_temporada_gdmth(fecha)
    dia_semana = fecha.weekday()
    es_domingo_fest = dia_semana == 6 or es_festivo(fecha)
    es_sabado = dia_semana == 5 and not es_festivo(fecha)
    hora = hora_cfe

    if es_domingo_fest:
        if temporada == 1:
            return "Base" if _en_rango(hora, 0, 19) else "Intermedio"
        return "Base" if _en_rango(hora, 0, 18) else "Intermedio"

    if es_sabado:
        if temporada == 1:
            return "Base" if _en_rango(hora, 0, 7) else "Intermedio"
        if _en_rango(hora, 0, 8):
            return "Base"
        if _en_rango(hora, 19, 21):
            return "Punta"
        return "Intermedio"

    if temporada == 1:
        if _en_rango(hora, 0, 6):
            return "Base"
        if _en_rango(hora, 20, 22):
            return "Punta"
        return "Intermedio"

    if _en_rango(hora, 0, 6):
        return "Base"
    if _en_rango(hora, 18, 22):
        return "Punta"
    return "Intermedio"


def periodo_por_esquema(esquema: str, fecha: date, hora_cfe: int) -> str:
    if esquema in ("T01", "SIN"):
        return "T01"
    if esquema == "GDMTH":
        return periodo_gdmth(fecha, hora_cfe)
    return periodo_dist(fecha, hora_cfe)


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------

def procesar_perfil(
    ruta: Path, esquema: str, servicio: str = "consumo"
) -> list[tuple]:
    """Agrega por (dia operativo, hora 0-23)."""
    from deteccion_perfil import inspeccionar_perfil, iter_filas_perfil

    bidi = es_bidireccional(servicio)
    neteo = es_neteo(servicio)
    doble = usa_rec_ent(servicio)
    fuente = columna_fuente(servicio)
    acum_rec: dict[tuple[date, int], float] = defaultdict(float)
    acum_ent: dict[tuple[date, int], float] = defaultdict(float)
    acum_gen: dict[tuple[date, int], float] = defaultdict(float)
    meta_periodo: dict[tuple[date, int], tuple[date, str]] = {}
    n = 0

    meta = inspeccionar_perfil(ruta)
    energia = meta.columnas.energia
    if bidi:
        for req in ("KWH_REC", "KWH_ENT", "KWH_GEN"):
            if req not in energia:
                raise ValueError(
                    "Servicio bidireccional requiere KWH_REC, KWH_ENT y KWH_GEN "
                    f"(o alias). Encontradas: {meta.encabezados}"
                )
    elif neteo:
        for req in ("KWH_REC", "KWH_ENT"):
            if req not in energia:
                raise ValueError(
                    "Servicio neteo requiere KWH_REC y KWH_ENT "
                    f"(o alias). Encontradas: {meta.encabezados}"
                )
    elif fuente not in energia:
        raise ValueError(
            f"Servicio {servicio} requiere columna {fuente} (o alias). "
            f"Encontradas: {meta.encabezados}"
        )

    for dt, vals in iter_filas_perfil(ruta, meta):
        fecha_per, hora_cfe = _bucket_hora(dt)
        dia_op = fecha_operativa(dt)
        clave = (dia_op, hora_cfe)
        if doble:
            acum_rec[clave] += float(vals.get("KWH_REC", 0.0))
            acum_ent[clave] += float(vals.get("KWH_ENT", 0.0))
            if bidi:
                acum_gen[clave] += float(vals.get("KWH_GEN", 0.0))
        else:
            acum_rec[clave] += float(vals.get(fuente, 0.0))
        if clave not in meta_periodo:
            periodo = periodo_por_esquema(esquema, fecha_per, hora_cfe)
            meta_periodo[clave] = (fecha_per, periodo)
        n += 1
        if n % 100_000 == 0:
            print(f"  ... {n:,} filas")

    print(f"  Filas procesadas: {n:,}  (servicio={servicio})")

    filas = []
    for clave in sorted(acum_rec):
        dia_op, hora = clave
        _, periodo = meta_periodo[clave]
        if bidi:
            filas.append(
                (
                    dia_op,
                    hora,
                    acum_rec[clave],
                    acum_ent[clave],
                    acum_gen[clave],
                    periodo,
                )
            )
        elif neteo:
            filas.append(
                (dia_op, hora, acum_rec[clave], acum_ent[clave], periodo)
            )
        else:
            filas.append((dia_op, hora, acum_rec[clave], periodo))
    return filas


def escribir(ruta_out: Path, filas: list, servicio: str = "consumo") -> None:
    bidi = es_bidireccional(servicio)
    neteo = es_neteo(servicio)
    with ruta_out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if bidi:
            writer.writerow(
                [
                    "FECHA",
                    "HORA",
                    "KWH_REC",
                    "KWH_ENT",
                    "KWH_GEN",
                    "CONSUMO_REAL",
                    "PERIODO",
                ]
            )
            for dia, hora, kwh_r, kwh_e, kwh_g, periodo in filas:
                real = kwh_r + kwh_g - kwh_e
                writer.writerow(
                    [
                        dia.isoformat(),
                        hora,
                        f"{kwh_r:.6f}",
                        f"{kwh_e:.6f}",
                        f"{kwh_g:.6f}",
                        f"{real:.6f}",
                        periodo,
                    ]
                )
        elif neteo:
            writer.writerow(
                [
                    "FECHA",
                    "HORA",
                    "KWH_REC",
                    "KWH_ENT",
                    "CONSUMO_REAL",
                    "PERIODO",
                ]
            )
            for dia, hora, kwh_r, kwh_e, periodo in filas:
                writer.writerow(
                    [
                        dia.isoformat(),
                        hora,
                        f"{kwh_r:.6f}",
                        f"{kwh_e:.6f}",
                        f"{kwh_r - kwh_e:.6f}",
                        periodo,
                    ]
                )
        else:
            writer.writerow(["FECHA", "HORA", "KWH_REC", "CONSUMO_REAL", "PERIODO"])
            for dia, hora, kwh, periodo in filas:
                writer.writerow(
                    [dia.isoformat(), hora, f"{kwh:.6f}", f"{kwh:.6f}", periodo]
                )


def _es_reporte(nombre: str) -> bool:
    bajos = nombre.lower()
    return any(
        bajos.endswith(suf)
        for suf in (
            "_energia_por_dia.csv",
            "_energia_por_mes.csv",
            "_gdmth_energia_por_dia.csv",
            "_gdmth_energia_por_mes.csv",
            "_consumo_tipico_semana.csv",
            "_gdmth_consumo_tipico_semana.csv",
            "_energia_por_hora_dist.csv",
            "_energia_por_hora_gdmth.csv",
            "_energia_por_hora_sin.csv",
        )
    )


def pedir_archivos(directorio: Path) -> list[Path]:
    csvs = [p for p in sorted(directorio.glob("*.csv")) if not _es_reporte(p.name)]
    print("Archivos de perfil en el directorio:")
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


def pedir_esquema(argv_resto: list[str]) -> tuple[str, list[str]]:
    if argv_resto and argv_resto[0].upper() in ESQUEMAS:
        return argv_resto[0].upper(), argv_resto[1:]
    # Buscar --esquema X
    esquema = "DIST"
    resto: list[str] = []
    i = 0
    while i < len(argv_resto):
        if argv_resto[i] in ("--esquema", "-e") and i + 1 < len(argv_resto):
            esquema = argv_resto[i + 1].upper()
            i += 2
            continue
        resto.append(argv_resto[i])
        i += 1
    if esquema not in ESQUEMAS:
        raise SystemExit(f"Esquema invalido: {esquema}. Use DIST, GDMTH o T01.")
    if not resto and sys.stdin.isatty():
        print("Esquema tarifario [DIST/GDMTH/T01] (Enter=DIST):")
        r = input("> ").strip().upper()
        if r:
            if r not in ESQUEMAS:
                raise SystemExit(f"Esquema invalido: {r}")
            esquema = r
    return esquema, resto


def ruta_salida(entrada: Path, esquema: str) -> Path:
    return entrada.with_name(f"{entrada.stem}_energia_por_hora_{esquema.lower()}.csv")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    directorio = Path(__file__).resolve().parent
    servicio, argv = extraer_servicio(argv)
    esquema, resto = pedir_esquema(argv)

    if resto:
        entradas = []
        for a in resto:
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
        print(f"\nProcesando ({esquema}, {servicio}): {entrada.name}")
        filas = procesar_perfil(entrada, esquema, servicio)
        out = ruta_salida(entrada, esquema)
        escribir(out, filas, servicio)
        print(f"  Salida -> {out.name}  ({len(filas)} horas)")

    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
