"""
Proceso completo de analisis de perfil cincominutal.

Parametros:
  1) tarifa: 0=Tarifa 01, 1=GDMTH, 2=DIST
  2) servicio (opcional): consumo | generacion | bidireccional | neteo
  3+) archivos

Consumo:     KWH_REC (+ graficas). Varios archivos se suman.
Generacion:  KWH_ENT (+ graficas). Varios archivos se suman.
Bidireccional: requiere 2 archivos (consumo, generacion); combina
  KWH_REC y KWH_ENT del consumo + KWH_GEN (= KWH_ENT generacion).

Uso:
  python procesar_perfil_completo.py 2 consumo perfil.csv
  python procesar_perfil_completo.py 2 generacion perfil_gen.csv
  python procesar_perfil_completo.py 2 bidireccional consumo.csv generacion.csv
"""

from __future__ import annotations

import csv
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from deteccion_perfil import (
    FMT_CANONICO,
    inspeccionar_perfil,
    iter_filas_perfil,
    normalizar_perfil,
    parsear_fecha,
)
from servicio_config import (
    SERVICIOS,
    columna_fuente,
    es_bidireccional,
    es_neteo,
    genera_graficas,
    normalizar_servicio,
    usa_rec_ent,
)

DIR = Path(__file__).resolve().parent
PYTHON = sys.executable
FMT_FECHA = FMT_CANONICO

TARIFA_MAP = {
    "0": "T01",
    "1": "GDMTH",
    "2": "DIST",
}
COLS_ENERGIA = ("KWH_REC", "KWH_ENT", "KVARH_Q1", "KVARH_Q2", "KVARH_Q3", "KVARH_Q4")


def _es_reporte(nombre: str) -> bool:
    bajos = nombre.lower()
    sufijos = (
        "_suma.csv",
        "_energia_por_dia.csv",
        "_energia_por_mes.csv",
        "_gdmth_energia_por_dia.csv",
        "_gdmth_energia_por_mes.csv",
        "_t01_energia_por_dia.csv",
        "_t01_energia_por_mes.csv",
        "_consumo_tipico_semana.csv",
        "_gdmth_consumo_tipico_semana.csv",
        "_t01_consumo_tipico_semana.csv",
        "_sin_consumo_tipico_semana.csv",
        "_energia_por_hora_dist.csv",
        "_energia_por_hora_gdmth.csv",
        "_energia_por_hora_t01.csv",
        "_energia_por_hora_sin.csv",
        "_perfil_tipico_hora_dist.csv",
        "_perfil_tipico_hora_gdmth.csv",
        "_perfil_tipico_hora_t01.csv",
        "_perfil_tipico_hora_sin.csv",
    )
    return any(bajos.endswith(s) for s in sufijos)


def resolver_ruta(texto: str) -> Path:
    p = Path(texto.strip().strip('"').strip("'"))
    if not p.is_absolute():
        p = DIR / p
    return p


def pedir_tarifa() -> str:
    print("Tarifa:")
    print("  0 = Tarifa 01 (domestica, bloques 150/130/excedente)")
    print("  1 = GDMTH")
    print("  2 = DIST")
    print("(Enter=0 Tarifa 01)")
    r = input("> ").strip()
    if not r:
        return "0"
    if r not in TARIFA_MAP:
        raise SystemExit("Tarifa invalida. Use 0, 1 o 2.")
    return r


def pedir_servicio() -> str:
    print("\nServicio:")
    print("  consumo       = KWH_REC (+ graficas)")
    print("  generacion    = KWH_ENT (+ graficas)")
    print("  bidireccional = 2 perfiles (consumo + generacion)")
    print("  neteo         = 1 perfil con KWH_REC + KWH_ENT")
    print("(Enter=consumo)")
    r = input("> ").strip().lower()
    if not r:
        return "consumo"
    return normalizar_servicio(r)


def pedir_archivos() -> list[Path]:
    csvs = [p for p in sorted(DIR.glob("*.csv")) if not _es_reporte(p.name)]
    print("\nArchivos de perfil en el directorio:")
    if csvs:
        for i, p in enumerate(csvs, 1):
            print(f"  {i}. {p.name}")
    else:
        print("  (ninguno)")
    print()
    print("Indica archivos (numeros/rutas separados por coma, o *):")
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
            p = resolver_ruta(parte)
            if not p.exists():
                raise SystemExit(f"No existe: {p}")
            seleccionados.append(p)
    if not seleccionados:
        raise SystemExit("No se indico ningun archivo valido.")
    return seleccionados


def parse_argv(argv: list[str]) -> tuple[str, str, list[Path]]:
    """Devuelve (codigo_tarifa, servicio, perfiles)."""
    if not argv:
        codigo = pedir_tarifa()
        servicio = pedir_servicio()
        if es_bidireccional(servicio):
            print("\nBidireccional: indica 2 archivos (consumo, luego generacion).")
        return codigo, servicio, pedir_archivos()

    codigo = argv[0].strip()
    if codigo not in TARIFA_MAP:
        raise SystemExit(
            "El primer parametro debe ser la tarifa: 0 (Tarifa 01), 1 (GDMTH) o 2 (DIST).\n"
            f"Recibido: {codigo!r}"
        )
    resto = argv[1:]
    servicio = "consumo"
    if resto and resto[0].lower().replace("ó", "o") in set(SERVICIOS) | {"generación"}:
        servicio = normalizar_servicio(resto[0])
        resto = resto[1:]

    if not resto:
        raise SystemExit("Indica al menos un archivo de perfil despues de la tarifa.")

    perfiles: list[Path] = []
    for a in resto:
        p = resolver_ruta(a)
        if not p.exists():
            raise SystemExit(f"No existe: {p}")
        perfiles.append(p)

    if es_bidireccional(servicio) and len(perfiles) != 2:
        raise SystemExit(
            "Bidireccional requiere exactamente 2 archivos: "
            "perfil de consumo y perfil de generacion."
        )
    return codigo, servicio, perfiles


def correr(script: str, *args: str) -> None:
    ruta = DIR / script
    if not ruta.exists():
        raise SystemExit(f"No se encuentra el script: {ruta}")
    cmd = [PYTHON, str(ruta), *args]
    print(f"\n>>> {script} " + " ".join(Path(a).name for a in args))
    r = subprocess.run(cmd, cwd=str(DIR))
    if r.returncode != 0:
        raise SystemExit(f"Fallo {script} (codigo {r.returncode})")


# ---------------------------------------------------------------------------
# Suma renglon a renglon
# ---------------------------------------------------------------------------

def _parse_fecha_perfil(texto: str) -> datetime:
    """Acepta 'YYYY-MM-DD HH:MM:SS' o ISO con 'T' (perfil ya canónico)."""
    t = (texto or "").strip()
    if not t:
        raise ValueError("FECHA vacia")
    if "T" in t:
        t = t.replace("T", " ", 1)
    if len(t) == 16:  # YYYY-MM-DD HH:MM
        t = t + ":00"
    try:
        return datetime.strptime(t[:19], FMT_FECHA)
    except ValueError:
        # Respaldo: detectar formato del valor
        from deteccion_perfil import detectar_formato_fecha

        fmt = detectar_formato_fecha(t)
        return parsear_fecha(t, fmt)


def _leer_perfil(ruta: Path) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Devuelve (fieldnames canónicos, {FECHA: {col_energia: valor}})."""
    meta = inspeccionar_perfil(ruta)
    print(f"  [lectura] {ruta.name}: frecuencia≈{meta.frecuencia_min} min")
    datos: dict[str, dict[str, float]] = {}
    cols_presentes: set[str] = set()
    for dt, vals in iter_filas_perfil(ruta, meta):
        fh = dt.strftime(FMT_FECHA)
        cols_presentes |= set(vals)
        if fh in datos:
            for k, v in vals.items():
                datos[fh][k] = datos[fh].get(k, 0.0) + v
        else:
            datos[fh] = dict(vals)
    if "KWH_REC" not in cols_presentes and "KWH_ENT" not in cols_presentes:
        raise ValueError(f"Falta columna KWH_REC o KWH_ENT en {ruta.name}")
    orden = (
        "KWH_REC",
        "KWH_ENT",
        "KWH_GEN",
        "KVARH_Q1",
        "KVARH_Q2",
        "KVARH_Q3",
        "KVARH_Q4",
    )
    fieldnames = ["FECHA", *[c for c in orden if c in cols_presentes]]
    return fieldnames, datos


def sumar_perfiles(archivos: list[Path]) -> Path:
    """Suma por FECHA las columnas de energia. Escribe *_suma.csv junto al primero."""
    if len(archivos) < 2:
        raise ValueError("sumar_perfiles requiere al menos 2 archivos")
    print(f"\nSumando {len(archivos)} archivos renglon a renglon (por FECHA)...")
    _, base = _leer_perfil(archivos[0])
    cols_presentes = set(next(iter(base.values())).keys()) if base else set()
    if not cols_presentes:
        cols_presentes = {"KWH_REC"}

    for extra in archivos[1:]:
        print(f"  + {extra.name}")
        _, datos = _leer_perfil(extra)
        fechas_base = set(base)
        fechas_extra = set(datos)
        solo_base = fechas_base - fechas_extra
        solo_extra = fechas_extra - fechas_base
        if solo_base or solo_extra:
            print(
                f"  ADVERTENCIA {extra.name}: "
                f"{len(solo_base)} fechas solo en acumulado, "
                f"{len(solo_extra)} fechas solo en este archivo "
                "(se rellenan con 0)."
            )
        cols_presentes |= set(next(iter(datos.values())).keys()) if datos else set()
        todas = fechas_base | fechas_extra
        nuevo: dict[str, dict[str, float]] = {}
        for fh in todas:
            a = base.get(fh, {})
            b = datos.get(fh, {})
            nuevo[fh] = {
                c: float(a.get(c, 0.0)) + float(b.get(c, 0.0))
                for c in cols_presentes
            }
        base = nuevo

    fechas_ord = sorted(base.keys(), key=_parse_fecha_perfil)
    out = archivos[0].with_name(f"{archivos[0].stem}_suma.csv")
    orden = (
        "KWH_REC",
        "KWH_ENT",
        "KWH_GEN",
        "KVARH_Q1",
        "KVARH_Q2",
        "KVARH_Q3",
        "KVARH_Q4",
    )
    fieldnames = ["FECHA", *[c for c in orden if c in cols_presentes]]
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for fh in fechas_ord:
            fila = {"FECHA": fh}
            for c in fieldnames[1:]:
                fila[c] = f"{base[fh].get(c, 0.0):.10g}"
            writer.writerow(fila)

    print(f"  Suma -> {out.name}  ({len(fechas_ord):,} filas)")
    return out


def combinar_consumo_generacion(consumo: Path, generacion: Path) -> Path:
    """Une perfiles bidireccionales:
    KWH_REC = KWH_REC del archivo de consumo
    KWH_ENT = KWH_ENT del archivo de consumo
    KWH_GEN = KWH_ENT del archivo de generacion
    """
    print("\nCombinando consumo + generacion...")
    print(f"  Consumo   : {consumo.name} -> KWH_REC + KWH_ENT")
    print(f"  Generacion: {generacion.name} -> KWH_GEN(=KWH_ENT)")

    _, datos_c = _leer_perfil(consumo)
    _, datos_g = _leer_perfil(generacion)

    fechas = set(datos_c) | set(datos_g)
    solo_c = set(datos_c) - set(datos_g)
    solo_g = set(datos_g) - set(datos_c)
    if solo_c or solo_g:
        print(
            f"  ADVERTENCIA: {len(solo_c)} fechas solo en consumo, "
            f"{len(solo_g)} solo en generacion (se rellenan con 0)."
        )

    def _key(fh: str) -> datetime:
        return datetime.strptime(fh, FMT_FECHA)

    out = consumo.with_name(f"{consumo.stem}_bidi_{generacion.stem}.csv")
    if len(out.name) > 120:
        out = consumo.with_name(f"{consumo.stem}_bidireccional.csv")

    fieldnames = [
        "FECHA",
        "KWH_REC",
        "KWH_ENT",
        "KWH_GEN",
        "KVARH_Q1",
        "KVARH_Q2",
        "KVARH_Q3",
        "KVARH_Q4",
    ]
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for fh in sorted(fechas, key=_key):
            c = datos_c.get(fh, {})
            g = datos_g.get(fh, {})
            writer.writerow(
                {
                    "FECHA": fh,
                    "KWH_REC": f"{float(c.get('KWH_REC', 0.0) or 0.0):.10g}",
                    "KWH_ENT": f"{float(c.get('KWH_ENT', 0.0) or 0.0):.10g}",
                    "KWH_GEN": f"{float(g.get('KWH_ENT', 0.0) or 0.0):.10g}",
                    "KVARH_Q1": f"{float(c.get('KVARH_Q1', 0.0) or 0.0):.10g}",
                    "KVARH_Q2": f"{float(c.get('KVARH_Q2', 0.0) or 0.0):.10g}",
                    "KVARH_Q3": f"{float(c.get('KVARH_Q3', 0.0) or 0.0):.10g}",
                    "KVARH_Q4": f"{float(c.get('KVARH_Q4', 0.0) or 0.0):.10g}",
                }
            )

    print(f"  Combinado -> {out.name}  ({len(fechas):,} filas)")
    return out


# ---------------------------------------------------------------------------
# Sin tarifa horaria: diario / mensual solo TOTAL
# ---------------------------------------------------------------------------

def fecha_operativa(dt: datetime) -> date:
    if dt.hour == 0 and dt.minute < 5:
        return (dt - timedelta(days=1)).date()
    return dt.date()


def generar_diario_mensual_t01(perfil: Path, servicio: str = "consumo") -> Path:
    """Genera diario/mensual: TOTAL_REC (+ ENT/GEN según servicio)."""
    bidi = es_bidireccional(servicio)
    neteo = es_neteo(servicio)
    doble = usa_rec_ent(servicio)
    fuente = columna_fuente(servicio)
    diarios_r: dict[date, float] = defaultdict(float)
    diarios_e: dict[date, float] = defaultdict(float)
    diarios_g: dict[date, float] = defaultdict(float)
    mensuales_r: dict[tuple[int, int], float] = defaultdict(float)
    mensuales_e: dict[tuple[int, int], float] = defaultdict(float)
    mensuales_g: dict[tuple[int, int], float] = defaultdict(float)
    n = 0

    with perfil.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        campos = {c.strip().upper(): c for c in (reader.fieldnames or [])}
        if "FECHA" not in campos:
            raise SystemExit(f"Se requiere FECHA en {perfil.name}")
        if bidi:
            for req in ("KWH_REC", "KWH_ENT", "KWH_GEN"):
                if req not in campos:
                    raise SystemExit(
                        "Bidireccional requiere KWH_REC, KWH_ENT y KWH_GEN."
                    )
        elif neteo:
            for req in ("KWH_REC", "KWH_ENT"):
                if req not in campos:
                    raise SystemExit(
                        "Neteo requiere KWH_REC y KWH_ENT en el mismo perfil."
                    )
        elif fuente not in campos:
            raise SystemExit(f"Servicio {servicio} requiere {fuente} en {perfil.name}")
        col_fecha = campos["FECHA"]
        col_rec = campos.get("KWH_REC")
        col_ent = campos.get("KWH_ENT")
        col_gen = campos.get("KWH_GEN")
        col_uni = campos.get(fuente)
        for row in reader:
            dt = datetime.strptime(row[col_fecha].strip(), FMT_FECHA)
            dia = fecha_operativa(dt)
            if doble:
                diarios_r[dia] += float(row[col_rec] or 0)
                diarios_e[dia] += float(row[col_ent] or 0)
                mensuales_r[(dia.year, dia.month)] += float(row[col_rec] or 0)
                mensuales_e[(dia.year, dia.month)] += float(row[col_ent] or 0)
                if bidi:
                    diarios_g[dia] += float(row[col_gen] or 0)
                    mensuales_g[(dia.year, dia.month)] += float(row[col_gen] or 0)
            else:
                kwh = float(row[col_uni] or 0)
                diarios_r[dia] += kwh
                mensuales_r[(dia.year, dia.month)] += kwh
            n += 1
            if n % 100_000 == 0:
                print(f"  ... {n:,} filas")

    print(f"  Filas procesadas: {n:,}")

    if bidi:
        extras = ["TOTAL_ENT", "TOTAL_GEN", "CONSUMO_REAL"]
    elif neteo:
        extras = ["TOTAL_ENT", "CONSUMO_REAL"]
    else:
        extras = ["CONSUMO_REAL"]
    campos_dia = ["FECHA", "TOTAL_REC", *extras]
    diario = perfil.with_name(f"{perfil.stem}_t01_energia_por_dia.csv")
    with diario.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos_dia)
        w.writeheader()
        for dia in sorted(diarios_r):
            rec = diarios_r[dia]
            fila = {"FECHA": dia.isoformat(), "TOTAL_REC": f"{rec:.6f}"}
            if doble:
                ent = diarios_e[dia]
                fila["TOTAL_ENT"] = f"{ent:.6f}"
                if bidi:
                    gen = diarios_g[dia]
                    fila["TOTAL_GEN"] = f"{gen:.6f}"
                    fila["CONSUMO_REAL"] = f"{rec + gen - ent:.6f}"
                else:
                    fila["CONSUMO_REAL"] = f"{rec - ent:.6f}"
            else:
                fila["CONSUMO_REAL"] = f"{rec:.6f}"
            w.writerow(fila)

    campos_mes = ["ANIO", "MES", "TOTAL_REC", *extras]
    mensual = perfil.with_name(f"{perfil.stem}_t01_energia_por_mes.csv")
    with mensual.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos_mes)
        w.writeheader()
        for anio, mes in sorted(mensuales_r):
            rec = mensuales_r[(anio, mes)]
            fila = {
                "ANIO": anio,
                "MES": mes,
                "TOTAL_REC": f"{rec:.6f}",
            }
            if doble:
                ent = mensuales_e[(anio, mes)]
                fila["TOTAL_ENT"] = f"{ent:.6f}"
                if bidi:
                    gen = mensuales_g[(anio, mes)]
                    fila["TOTAL_GEN"] = f"{gen:.6f}"
                    fila["CONSUMO_REAL"] = f"{rec + gen - ent:.6f}"
                else:
                    fila["CONSUMO_REAL"] = f"{rec - ent:.6f}"
            else:
                fila["CONSUMO_REAL"] = f"{rec:.6f}"
            w.writerow(fila)

    print(f"  Diario  -> {diario.name}  ({len(diarios_r)} dias)")
    print(f"  Mensual -> {mensual.name}  ({len(mensuales_r)} meses)")
    return diario


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def diario_de(perfil: Path, esquema: str) -> Path:
    if esquema == "GDMTH":
        return perfil.with_name(f"{perfil.stem}_gdmth_energia_por_dia.csv")
    if esquema in ("T01", "SIN"):
        return perfil.with_name(f"{perfil.stem}_t01_energia_por_dia.csv")
    return perfil.with_name(f"{perfil.stem}_energia_por_dia.csv")


def por_hora_de(perfil: Path, esquema: str) -> Path:
    return perfil.with_name(f"{perfil.stem}_energia_por_hora_{esquema.lower()}.csv")


def tipico_hora_de(perfil: Path, esquema: str) -> Path:
    return perfil.with_name(f"{perfil.stem}_perfil_tipico_hora_{esquema.lower()}.csv")


def procesar_perfil(
    perfil: Path,
    esquema: str,
    servicio: str = "consumo",
    *,
    region: str | None = None,
    fecha_desde=None,
    fecha_hasta=None,
) -> dict:
    from resumen_energia import imprimir_resumen, resumen_desde_diario

    if fecha_desde is not None or fecha_hasta is not None:
        from filtrar_perfil import filtrar_perfil_fechas

        perfil = filtrar_perfil_fechas(perfil, fecha_desde, fecha_hasta)

    print("\n" + "=" * 60)
    print(f"Perfil  : {perfil.name}")
    print(f"Tarifa  : {esquema}")
    print(f"Servicio: {servicio}")
    if region:
        print(f"Región  : {region}")
    if fecha_desde or fecha_hasta:
        print(f"Rango   : {fecha_desde or '...'} -> {fecha_hasta or '...'}")
    print("=" * 60)

    flag_srv = f"--servicio={servicio}"

    if esquema in ("T01", "SIN"):
        print("\n>>> diario/mensual Tarifa 01")
        diario = generar_diario_mensual_t01(perfil, servicio)
    elif esquema == "DIST":
        correr("energia_por_horario_dist.py", flag_srv, str(perfil))
        diario = diario_de(perfil, esquema)
    else:
        correr("energia_por_horario_gdmth.py", flag_srv, str(perfil))
        diario = diario_de(perfil, esquema)

    if not diario.exists():
        raise SystemExit(f"No se genero el diario esperado: {diario.name}")

    correr("consumo_tipico_semana.py", str(diario))

    correr("energia_por_hora.py", flag_srv, esquema, str(perfil))
    por_hora = por_hora_de(perfil, esquema)
    if not por_hora.exists():
        raise SystemExit(f"No se genero el por-hora esperado: {por_hora.name}")

    correr("perfil_tipico_hora_semana.py", str(por_hora))
    tipico = tipico_hora_de(perfil, esquema)
    if not tipico.exists():
        raise SystemExit(f"No se genero el perfil tipico esperado: {tipico.name}")

    if genera_graficas(servicio):
        correr("graficar_perfil_tipico.py", str(tipico))

    resumen = resumen_desde_diario(diario, esquema, servicio, region=region)
    imprimir_resumen(resumen)

    print(f"\nCompletado ({esquema}, {servicio}): {perfil.name}")
    return resumen


def preparar_perfil(servicio: str, archivos: list[Path]) -> Path:
    archivos = [normalizar_perfil(p) for p in archivos]
    if es_bidireccional(servicio):
        if len(archivos) != 2:
            raise SystemExit(
                "Bidireccional requiere exactamente 2 archivos "
                "(consumo y generacion)."
            )
        return combinar_consumo_generacion(archivos[0], archivos[1])
    if len(archivos) >= 2:
        return sumar_perfiles(archivos)
    return archivos[0]


def preparar_perfil_bidireccional(
    consumos: list[Path], generaciones: list[Path]
) -> Path:
    """Suma medidores de cada lado (si hay varios) y combina consumo+generacion."""
    if not consumos:
        raise SystemExit("Bidireccional: falta al menos un perfil de consumo.")
    if not generaciones:
        raise SystemExit("Bidireccional: falta al menos un perfil de generacion.")
    consumos = [normalizar_perfil(p) for p in consumos]
    generaciones = [normalizar_perfil(p) for p in generaciones]
    consumo = sumar_perfiles(consumos) if len(consumos) >= 2 else consumos[0]
    if len(consumos) >= 2:
        print(f"  Consumo sumado ({len(consumos)} archivos): {consumo.name}")
    generacion = (
        sumar_perfiles(generaciones) if len(generaciones) >= 2 else generaciones[0]
    )
    if len(generaciones) >= 2:
        print(f"  Generacion sumada ({len(generaciones)} archivos): {generacion.name}")
    return combinar_consumo_generacion(consumo, generacion)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    codigo, servicio, archivos = parse_argv(argv)
    esquema = TARIFA_MAP[codigo]

    print(f"Tarifa seleccionada: {codigo} ({esquema})")
    print(f"Servicio: {servicio}")
    print(f"Archivos ({len(archivos)}):")
    for i, p in enumerate(archivos):
        rol = ""
        if es_bidireccional(servicio):
            rol = " [consumo]" if i == 0 else " [generacion]"
        print(f"  - {p.name}{rol}")

    perfil = preparar_perfil(servicio, archivos)
    procesar_perfil(perfil, esquema, servicio)

    print("\n" + "=" * 60)
    print("Proceso completo finalizado.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
