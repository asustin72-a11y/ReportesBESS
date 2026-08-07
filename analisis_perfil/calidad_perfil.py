"""Rango de fechas y calidad de datos de perfiles cincominutales."""

from __future__ import annotations

import csv
import io
import tempfile
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from deteccion_perfil import FMT_CANONICO, inspeccionar_perfil, parsear_fecha
from filtrar_perfil import fecha_operativa, rango_fechas_perfil


def _parse_dt(texto: str, fmt_hint: str | None = None) -> datetime:
    t = (texto or "").strip().replace("T", " ", 1)
    if len(t) == 16:
        t = t + ":00"
    try:
        return datetime.strptime(t[:19], FMT_CANONICO)
    except ValueError:
        from deteccion_perfil import detectar_formato_fecha

        fmt = fmt_hint or detectar_formato_fecha(t)
        return parsear_fecha(t, fmt)


def rango_fechas_desde_bytes(data: bytes, nombre: str = "perfil.csv") -> tuple[date, date] | None:
    """Inspecciona un CSV (o el primer CSV de un ZIP) y devuelve rango operativo."""
    nombre_l = Path(nombre).name.lower()
    if nombre_l.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base = Path(info.filename).name
                low = base.lower()
                if not low.endswith(".csv") or base.startswith("."):
                    continue
                if "__macosx" in info.filename.lower():
                    continue
                if any(
                    x in low
                    for x in ("energia_por", "consumo_tipico", "perfil_tipico", "grafica")
                ):
                    continue
                return rango_fechas_desde_bytes(zf.read(info), base)
        return None

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    try:
        return rango_fechas_perfil(path)
    finally:
        path.unlink(missing_ok=True)


def rango_fechas_desde_fuentes(archivos) -> tuple[date, date] | None:
    """Une el rango operativo de varios UploadedFile / MemFile."""
    minimo: date | None = None
    maximo: date | None = None
    for uf in archivos or []:
        try:
            data = uf.getvalue()
            nombre = Path(uf.name).name
        except Exception:
            continue
        r = rango_fechas_desde_bytes(data, nombre)
        if not r:
            continue
        a, b = r
        if minimo is None or a < minimo:
            minimo = a
        if maximo is None or b > maximo:
            maximo = b
    if minimo is None or maximo is None:
        return None
    return minimo, maximo


def analizar_calidad_perfil(
    perfil: Path,
    *,
    columnas: tuple[str, ...] | None = None,
) -> dict:
    """Huecos, frecuencia, cobertura y presencia de canales."""
    meta = inspeccionar_perfil(perfil)
    freq = int(meta.frecuencia_min or 5)
    if freq <= 0:
        freq = 5
    cols_objetivo = list(columnas) if columnas else []
    if not cols_objetivo:
        energia = getattr(meta.columnas, "energia", {}) or {}
        for c in ("KWH_REC", "KWH_ENT", "KWH_GEN"):
            if c in energia:
                cols_objetivo.append(c)
        if not cols_objetivo:
            cols_objetivo = ["KWH_REC"]

    timestamps: list[datetime] = []
    n_invalidas = 0
    sumas = {c: 0.0 for c in cols_objetivo}
    presentes = {c: False for c in cols_objetivo}

    with perfil.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return {
                "ok": False,
                "error": "Perfil sin encabezado",
                "n_filas": 0,
            }
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        if "FECHA" not in campos:
            return {"ok": False, "error": "Falta columna FECHA", "n_filas": 0}
        col_f = campos["FECHA"]
        map_cols = {c: campos[c] for c in cols_objetivo if c in campos}
        for c in cols_objetivo:
            presentes[c] = c in map_cols
        fmt = getattr(meta, "formato_fecha", None)
        for row in reader:
            try:
                dt = _parse_dt(row.get(col_f) or "", fmt)
            except Exception:
                n_invalidas += 1
                continue
            timestamps.append(dt)
            for c, col in map_cols.items():
                try:
                    sumas[c] += float(row.get(col) or 0)
                except ValueError:
                    pass

    n = len(timestamps)
    if n == 0:
        return {
            "ok": False,
            "error": "Sin filas con fecha válida",
            "n_filas": 0,
            "n_invalidas": n_invalidas,
        }

    timestamps.sort()
    dia_min = fecha_operativa(timestamps[0])
    dia_max = fecha_operativa(timestamps[-1])
    n_dias_calendario = (dia_max - dia_min).days + 1

    # Huecos: delta > 1.5 × frecuencia esperada
    umbral = timedelta(minutes=freq) * 1.5
    huecos: list[dict] = []
    minutos_faltantes = 0.0
    for a, b in zip(timestamps, timestamps[1:]):
        delta = b - a
        if delta > umbral:
            faltan = max(0.0, (delta.total_seconds() / 60.0) - freq)
            minutos_faltantes += faltan
            if len(huecos) < 25:
                huecos.append(
                    {
                        "desde": a.strftime("%Y-%m-%d %H:%M"),
                        "hasta": b.strftime("%Y-%m-%d %H:%M"),
                        "minutos": round(faltan, 1),
                    }
                )

    esperados = max(1, int((n_dias_calendario * 24 * 60) / freq))
    cobertura_pct = min(100.0, 100.0 * n / esperados)

    alertas: list[str] = []
    if n_invalidas:
        alertas.append(f"{n_invalidas} fila(s) con fecha inválida")
    if huecos:
        alertas.append(
            f"{len(huecos)} hueco(s) detectado(s) "
            f"(≥ {freq * 1.5:.0f} min; muestra hasta 25)"
        )
    for c, ok in presentes.items():
        if not ok:
            alertas.append(f"Falta columna {c}")
    if cobertura_pct < 95:
        alertas.append(f"Cobertura estimada {cobertura_pct:.1f}% del periodo")

    return {
        "ok": len(alertas) == 0,
        "n_filas": n,
        "n_invalidas": n_invalidas,
        "frecuencia_min": freq,
        "fecha_min": dia_min.isoformat(),
        "fecha_max": dia_max.isoformat(),
        "n_dias": n_dias_calendario,
        "cobertura_pct": round(cobertura_pct, 1),
        "n_huecos": len(huecos),
        "minutos_faltantes": round(minutos_faltantes, 1),
        "huecos": huecos,
        "columnas": presentes,
        "sumas_kwh": {c: round(v, 3) for c, v in sumas.items()},
        "alertas": alertas,
    }
