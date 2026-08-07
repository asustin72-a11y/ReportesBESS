"""
Estadísticas de energía por horario tarifario CFE DIST (Región Central).

Lee perfiles cincominutales (FECHA, KWH_REC, ...) y genera:
  - CSV diario:  FECHA, BASE_REC, INTERMEDIO_REC, PUNTA_REC
  - CSV mensual: AÑO, MES, BASE_REC, INTERMEDIO_REC, PUNTA_REC

Día operativo: 00:05 del día D hasta 00:00 del día D+1 (inclusive).
Script 100 % autónomo (sin dependencias del repo BESS).
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

FMT_FECHA = "%Y-%m-%d %H:%M:%S"

from servicio_config import (  # noqa: E402
    PERIODO_A_ENT,
    PERIODO_A_GEN,
    PERIODO_A_REC,
    columna_fuente,
    columnas_periodo,
    es_bidireccional,
    es_neteo,
    extraer_servicio,
    fila_vacia,
    usa_rec_ent,
    valores_con_totales,
)


# ---------------------------------------------------------------------------
# Reglas DIST Región Central (equivalentes a bess/cfe/periods.py)
# ---------------------------------------------------------------------------

def obtener_temporada(fecha: date) -> int:
    """Temporada 1..4 según fronteras del primer domingo de abril
    y el último domingo de octubre."""
    mes, dia, año = fecha.month, fecha.day, fecha.year

    primer_domingo_abril = 7
    for d in range(1, 8):
        if datetime(año, 4, d).weekday() == 6:
            primer_domingo_abril = d
            break

    ultimo_domingo_octubre = 25
    for d in range(31, 24, -1):
        if datetime(año, 10, d).weekday() == 6:
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


def es_festivo(fecha: date) -> bool:
    festivos_fijos = {(1, 1), (2, 5), (3, 21), (5, 1), (9, 16), (11, 20), (12, 25)}
    return (fecha.month, fecha.day) in festivos_fijos


def obtener_periodo_por_hora(fecha: date, hora_archivo: int) -> str:
    """Base / Intermedio / Punta según tabla oficial DIST Central.

    hora_archivo usa la convención 1..24 (hora_reloj + 1; 24 = medianoche).
    """
    hora = hora_archivo - 1
    if hora == 24:
        hora = 0

    temporada = obtener_temporada(fecha)
    dia_semana = fecha.weekday()
    es_domingo = dia_semana == 6
    es_sabado = dia_semana == 5
    es_fest = es_festivo(fecha)

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
        # temporada 4
        if 0 <= hora <= 7:
            return "Base"
        if 8 <= hora <= 18:
            return "Intermedio"
        if 19 <= hora <= 20:
            return "Punta"
        return "Intermedio"

    # Lunes a viernes
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
    # temporada 4
    if 0 <= hora <= 5:
        return "Base"
    if 6 <= hora <= 17:
        return "Intermedio"
    if 18 <= hora <= 21:
        return "Punta"
    return "Intermedio"


def periodo_por_timestamp(dt: datetime) -> str:
    """Asigna periodo al sello cincominutal.

    minuto == 0 → pertenece a esa hora de reloj;
    minuto != 0 → pertenece a la hora de cierre (hora + 1).
    Si eso cae en 24 → hora 0 del día calendario siguiente.
    """
    fecha = dt.date()
    hora_base = dt.hour if dt.minute == 0 else dt.hour + 1
    if hora_base == 24:
        hora_base = 0
        fecha = fecha + timedelta(days=1)
    return obtener_periodo_por_hora(fecha, hora_base if hora_base > 0 else 24)


def fecha_operativa(dt: datetime) -> date:
    """Día D = 00:05 D … 00:00 D+1 (el 00:00 cuenta para el día anterior)."""
    if dt.hour == 0 and dt.minute < 5:
        return (dt - timedelta(days=1)).date()
    return dt.date()


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------

def procesar_perfil(
    ruta: Path, servicio: str = "consumo"
) -> tuple[dict[date, dict[str, float]], dict[tuple[int, int], dict[str, float]]]:
    bidi = es_bidireccional(servicio)
    neteo = es_neteo(servicio)
    doble = usa_rec_ent(servicio)
    fuente = columna_fuente(servicio)
    diarios: dict[date, dict[str, float]] = defaultdict(lambda: fila_vacia(servicio))
    mensuales: dict[tuple[int, int], dict[str, float]] = defaultdict(
        lambda: fila_vacia(servicio)
    )
    n = 0

    with ruta.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV sin encabezado: {ruta}")
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos:
            raise ValueError(f"Se requiere columna FECHA. Encontradas: {reader.fieldnames}")
        if bidi:
            if "KWH_REC" not in campos or "KWH_ENT" not in campos or "KWH_GEN" not in campos:
                raise ValueError(
                    "Servicio bidireccional requiere KWH_REC, KWH_ENT y KWH_GEN."
                )
        elif neteo:
            if "KWH_REC" not in campos or "KWH_ENT" not in campos:
                raise ValueError(
                    "Servicio neteo requiere KWH_REC y KWH_ENT."
                )
        elif fuente not in campos:
            raise ValueError(
                f"Servicio {servicio} requiere columna {fuente}. "
                f"Encontradas: {reader.fieldnames}"
            )
        col_fecha = campos["FECHA"]
        col_rec = campos.get("KWH_REC")
        col_ent = campos.get("KWH_ENT")
        col_gen = campos.get("KWH_GEN")
        col_uni = campos.get(fuente)

        for row in reader:
            dt = datetime.strptime(row[col_fecha].strip(), FMT_FECHA)
            periodo = periodo_por_timestamp(dt)
            dia = fecha_operativa(dt)
            if doble:
                col_r = PERIODO_A_REC[periodo]
                col_e = PERIODO_A_ENT[periodo]
                diarios[dia][col_r] += float(row[col_rec] or 0)
                diarios[dia][col_e] += float(row[col_ent] or 0)
                clave_m = (dia.year, dia.month)
                mensuales[clave_m][col_r] += float(row[col_rec] or 0)
                mensuales[clave_m][col_e] += float(row[col_ent] or 0)
                if bidi:
                    col_g = PERIODO_A_GEN[periodo]
                    diarios[dia][col_g] += float(row[col_gen] or 0)
                    mensuales[clave_m][col_g] += float(row[col_gen] or 0)
            else:
                col_r = PERIODO_A_REC[periodo]
                kwh = float(row[col_uni] or 0)
                diarios[dia][col_r] += kwh
                mensuales[(dia.year, dia.month)][col_r] += kwh
            n += 1
            if n % 100_000 == 0:
                print(f"  ... {n:,} filas")

    print(f"  Filas procesadas: {n:,}  (servicio={servicio})")
    return dict(diarios), dict(mensuales)


def escribir_diario(
    ruta_out: Path, diarios: dict[date, dict[str, float]], servicio: str
) -> None:
    cols = columnas_periodo(servicio)
    with ruta_out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["FECHA", *cols])
        writer.writeheader()
        for dia in sorted(diarios):
            fila = {"FECHA": dia.isoformat()}
            fila.update(valores_con_totales(diarios[dia], servicio))
            writer.writerow(fila)


def escribir_mensual(
    ruta_out: Path,
    mensuales: dict[tuple[int, int], dict[str, float]],
    servicio: str,
) -> None:
    cols = columnas_periodo(servicio)
    with ruta_out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["ANIO", "MES", *cols])
        writer.writeheader()
        for anio, mes in sorted(mensuales):
            fila = {"ANIO": anio, "MES": mes}
            fila.update(valores_con_totales(mensuales[(anio, mes)], servicio))
            writer.writerow(fila)


def pedir_archivos(directorio: Path) -> list[Path]:
    csvs = sorted(directorio.glob("*.csv"))
    # Excluir reportes ya generados
    csvs = [
        p for p in csvs
        if not p.name.endswith("_energia_por_dia.csv")
        and not p.name.endswith("_energia_por_mes.csv")
    ]

    print("Archivos CSV en el directorio del script:")
    if csvs:
        for i, p in enumerate(csvs, 1):
            print(f"  {i}. {p.name}")
    else:
        print("  (ninguno)")

    print()
    print("Indica qué procesar:")
    print("  - números separados por coma (ej. 1 o 1,2)")
    print("  - rutas absolutas/relativas separadas por coma")
    print("  - * para todos los listados")
    respuesta = input("> ").strip()
    if not respuesta:
        raise SystemExit("No se indicó ningún archivo.")

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
                raise SystemExit(f"Índice fuera de rango: {idx}")
            seleccionados.append(csvs[idx - 1])
        else:
            p = Path(parte)
            if not p.is_absolute():
                p = directorio / p
            if not p.exists():
                raise SystemExit(f"No existe: {p}")
            seleccionados.append(p)
    if not seleccionados:
        raise SystemExit("No se indicó ningún archivo válido.")
    return seleccionados


def rutas_salida(entrada: Path) -> tuple[Path, Path]:
    stem = entrada.stem
    return (
        entrada.with_name(f"{stem}_energia_por_dia.csv"),
        entrada.with_name(f"{stem}_energia_por_mes.csv"),
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    servicio, argv = extraer_servicio(argv)
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
        print(f"\nProcesando ({servicio}): {entrada.name}")
        diarios, mensuales = procesar_perfil(entrada, servicio)
        out_dia, out_mes = rutas_salida(entrada)
        escribir_diario(out_dia, diarios, servicio)
        escribir_mensual(out_mes, mensuales, servicio)
        print(f"  Diario  -> {out_dia.name}  ({len(diarios)} dias)")
        print(f"  Mensual -> {out_mes.name}  ({len(mensuales)} meses)")

    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
