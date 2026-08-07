"""
Detección de formato de perfiles energéticos de distintas fuentes.

Detecta, sin asumir una sola fuente (API, Excel, medidor, etc.):
  - codificación del archivo
  - delimitador CSV
  - nombres de columnas (fecha/hora y energía)
  - formato de fecha (o fecha + hora en columnas separadas)
  - fila de tipos (FMT_DT_DATE, FMT_UINT32, …) — se ignora
  - frecuencia del perfil (minutos entre registros)
  - contadores acumulados (OBJ_CNT_TL_AP/AN) → energía de intervalo en kWh

No rellena huecos: solo inspección y normalización al formato canónico
usado por el resto del pipeline:

  FECHA (YYYY-MM-DD HH:MM:SS), KWH_REC, KWH_ENT, …  ·  UTF-8 con BOM  ·  coma
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CODIFICACIONES = ("utf-8-sig", "utf-8", "latin-1", "cp1252")

FMT_CANONICO = "%Y-%m-%d %H:%M:%S"

# Orden: más específicos primero. El primer match gana.
ALIAS_FECHA_HORA = (
    "FECHA_HORA",
    "FECHAHORA",
    "FECHA_Y_HORA",
    "TIMESTAMP",
    "DATETIME",
    "DATE_TIME",
    "DATAHORA",
    "FECHA",  # suele traer fecha+hora juntas (API / Excel)
)

ALIAS_FECHA_DIA = (
    "FECHA_DIA",
    "DATE",
    "DIA",
    "FECHA",  # si el valor es solo fecha, se combina con HORA
)

ALIAS_HORA = (
    "HORA_MIN",
    "HORARIO",
    "TIME",
    "HORA",
)

ALIAS_KWH_REC = (
    "KWH_REC",
    "KWHREC",
    "KWH_RECIBIDA",
    "ENERGIA_REC",
    "ENERGIA_RECIBIDA",
    "CONSUMO_KWH",
    "CONSUMO",
    "ACTIVE_ENERGY_IMPORT",
    "ACTIVEIMPORT",
    "EA_IMP",
    "WH_REC",
    # Contadores de medidor (p. ej. ION / objetos CNT): Active Positive
    "OBJ_CNT_TL_AP",
    "CNT_TL_AP",
    "TL_AP",
    "EA_POS",
    "KWH_IMP",
)

ALIAS_KWH_ENT = (
    "KWH_ENT",
    "KWHENT",
    "KWH_ENTREGADA",
    "ENERGIA_ENT",
    "ENERGIA_ENTREGADA",
    "GENERACION_KWH",
    "GENERACION",
    "ACTIVE_ENERGY_EXPORT",
    "ACTIVEEXPORT",
    "EA_EXP",
    "WH_ENT",
    # Contadores: Active Negative
    "OBJ_CNT_TL_AN",
    "CNT_TL_AN",
    "TL_AN",
    "EA_NEG",
    "KWH_EXP",
)

ALIAS_KWH_GEN = (
    "KWH_GEN",
    "KWHGEN",
    "ENERGIA_GEN",
    "ENERGIA_GENERADA",
)

ALIAS_KVARH = {
    "KVARH_Q1": ("KVARH_Q1", "KVARHQ1", "Q1"),
    "KVARH_Q2": ("KVARH_Q2", "KVARHQ2", "Q2"),
    "KVARH_Q3": ("KVARH_Q3", "KVARHQ3", "Q3"),
    "KVARH_Q4": ("KVARH_Q4", "KVARHQ4", "Q4"),
}

COLS_ENERGIA_CANON = (
    "KWH_REC",
    "KWH_ENT",
    "KWH_GEN",
    "KVARH_Q1",
    "KVARH_Q2",
    "KVARH_Q3",
    "KVARH_Q4",
)

FRECUENCIAS_CONOCIDAS = (1, 5, 10, 15, 30, 60)

_FORMATOS_RESPALDO = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
)

_FORMATOS_HORA = ("%H:%M:%S", "%H:%M")


# ---------------------------------------------------------------------------
# Estructuras
# ---------------------------------------------------------------------------

@dataclass
class MapaColumnas:
    """Nombres originales del CSV mapeados a roles canónicos."""

    fecha_hora: str | None = None  # datetime en una sola columna
    fecha_dia: str | None = None  # solo fecha
    hora: str | None = None  # solo hora
    energia: dict[str, str] = field(default_factory=dict)  # canon -> original

    def tiene_marca_tiempo(self) -> bool:
        return bool(self.fecha_hora) or (bool(self.fecha_dia) and bool(self.hora))


@dataclass
class PerfilMeta:
    encoding: str
    delimitador: str
    encabezados: list[str]
    columnas: MapaColumnas
    formato_fecha: str | None = None  # datetime combinado o fecha_dia
    formato_hora: str | None = None  # solo si hay columna hora aparte
    frecuencia_min: int | None = None
    muestra_fecha: str = ""
    filas_muestra: int = 0
    # Contadores acumulados (OBJ_CNT_…) → se convierten a energía de intervalo
    acumulado: bool = False
    factor_energia: float = 1.0  # p. ej. 0.001 si el contador está en Wh

    def resumen(self) -> str:
        cols = self.columnas
        energia = ", ".join(f"{k}={v}" for k, v in cols.energia.items()) or "(ninguna)"
        if cols.fecha_hora:
            marca = f"{cols.fecha_hora} ({self.formato_fecha})"
        else:
            marca = (
                f"{cols.fecha_dia} ({self.formato_fecha}) + "
                f"{cols.hora} ({self.formato_hora})"
            )
        freq = f"{self.frecuencia_min} min" if self.frecuencia_min else "desconocida"
        acum = (
            f"acumulado=si (factor={self.factor_energia:g} → kWh intervalo)"
            if self.acumulado
            else "acumulado=no"
        )
        return (
            f"codificacion={self.encoding}  delim={self.delimitador!r}\n"
            f"  marca de tiempo: {marca}\n"
            f"  energia: {energia}\n"
            f"  frecuencia: {freq}  (muestra={self.filas_muestra} filas)\n"
            f"  {acum}"
        )


# ---------------------------------------------------------------------------
# Codificación y delimitador
# ---------------------------------------------------------------------------

def detectar_codificacion(ruta: Path, max_bytes: int = 256_000) -> str:
    """Prueba utf-8-sig → utf-8 → latin-1 → cp1252; usa la primera que lea."""
    raw = ruta.read_bytes()[:max_bytes]
    if not raw:
        return "utf-8-sig"
    ultimo_error: Exception | None = None
    for enc in CODIFICACIONES:
        try:
            raw.decode(enc)
            # Validación ligera: que el texto tenga saltos o comas/punto y coma
            texto = raw.decode(enc)
            if "\n" in texto or "," in texto or ";" in texto:
                return enc
            return enc
        except UnicodeDecodeError as exc:
            ultimo_error = exc
    if ultimo_error:
        # latin-1 / cp1252 casi nunca fallan; por si acaso
        return "latin-1"
    return "utf-8-sig"


def detectar_delimitador(muestra: str) -> str:
    """Sniffer de csv; respaldo contando , vs ; en la primera línea."""
    muestra = muestra.lstrip("\ufeff")
    try:
        dialecto = csv.Sniffer().sniff(muestra[:8192], delimiters=",;")
        if dialecto.delimiter in (",", ";"):
            return dialecto.delimiter
    except csv.Error:
        pass
    primera = muestra.splitlines()[0] if muestra.strip() else ""
    return ";" if primera.count(";") > primera.count(",") else ","


# ---------------------------------------------------------------------------
# Formato de fecha (explícito, sin adivinar fila a fila)
# ---------------------------------------------------------------------------

def _parte_fecha(texto: str) -> str:
    t = (texto or "").strip().replace("T", " ", 1)
    if " " in t:
        return t.split(" ", 1)[0]
    return t


def _tiene_segundos(texto: str) -> bool:
    t = (texto or "").strip().replace("T", " ", 1)
    if " " not in t:
        return False
    hora = t.split(" ", 1)[1]
    return hora.count(":") >= 2


def detectar_formatos_fecha_candidatos(muestra: str) -> list[str]:
    """
    Inspecciona el primer valor no vacío y propone formatos candidatos.

    Si el primer componente tiene 4 dígitos → año primero.
    Si no → día primero (convención regional ES/MX).
    """
    t = (muestra or "").strip()
    if not t:
        return list(_FORMATOS_RESPALDO)

    # Solo hora (HH:MM[:SS]) — no es fecha
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", t):
        return list(_FORMATOS_HORA)

    parte = _parte_fecha(t)
    sep = "-" if "-" in parte else ("/" if "/" in parte else None)
    if sep is None:
        return list(_FORMATOS_RESPALDO)

    comps = parte.split(sep)
    if not comps:
        return list(_FORMATOS_RESPALDO)

    anio_primero = len(comps[0]) == 4 and comps[0].isdigit()
    con_hora = " " in t.replace("T", " ", 1) or "T" in (muestra or "")
    segs = _tiene_segundos(t)

    if anio_primero:
        if not con_hora:
            return [f"%Y{sep}%m{sep}%d", *(_FORMATOS_RESPALDO)]
        if segs:
            return [
                f"%Y{sep}%m{sep}%d %H:%M:%S",
                f"%Y{sep}%m{sep}%d %H:%M",
                *_FORMATOS_RESPALDO,
            ]
        return [
            f"%Y{sep}%m{sep}%d %H:%M",
            f"%Y{sep}%m{sep}%d %H:%M:%S",
            *_FORMATOS_RESPALDO,
        ]

    # Día primero
    if not con_hora:
        return [f"%d{sep}%m{sep}%Y", *(_FORMATOS_RESPALDO)]
    if segs:
        return [
            f"%d{sep}%m{sep}%Y %H:%M:%S",
            f"%d{sep}%m{sep}%Y %H:%M",
            *_FORMATOS_RESPALDO,
        ]
    return [
        f"%d{sep}%m{sep}%Y %H:%M",
        f"%d{sep}%m{sep}%Y %H:%M:%S",
        *_FORMATOS_RESPALDO,
    ]


def _probar_formatos(texto: str, formatos: list[str]) -> str | None:
    t = (texto or "").strip().replace("T", " ", 1)
    for fmt in formatos:
        try:
            datetime.strptime(t[:26], fmt)
            return fmt
        except ValueError:
            continue
    return None


def detectar_formato_fecha(muestra: str) -> str:
    """Elige un único formato explícito a partir de una muestra."""
    candidatos = detectar_formatos_fecha_candidatos(muestra)
    elegido = _probar_formatos(muestra, candidatos)
    if elegido:
        return elegido
    # Último recurso: formatos de respaldo completos
    elegido = _probar_formatos(muestra, list(_FORMATOS_RESPALDO))
    if elegido:
        return elegido
    raise ValueError(f"No se pudo detectar formato de fecha para: {muestra!r}")


def detectar_formato_hora(muestra: str) -> str:
    t = (muestra or "").strip()
    for fmt in _FORMATOS_HORA:
        try:
            datetime.strptime(t, fmt)
            return fmt
        except ValueError:
            continue
    raise ValueError(f"No se pudo detectar formato de hora para: {muestra!r}")


def parsear_fecha(texto: str, formato: str) -> datetime:
    t = (texto or "").strip().replace("T", " ", 1)
    return datetime.strptime(t[:26], formato)


def parsear_fecha_hora_separadas(
    fecha_txt: str, hora_txt: str, fmt_fecha: str, fmt_hora: str
) -> datetime:
    d = datetime.strptime((fecha_txt or "").strip()[:10], fmt_fecha).date()
    t = datetime.strptime((hora_txt or "").strip(), fmt_hora).time()
    return datetime.combine(d, t)


# ---------------------------------------------------------------------------
# Columnas
# ---------------------------------------------------------------------------

def _norm_nombre(nombre: str) -> str:
    s = (nombre or "").strip().upper()
    s = s.replace(" ", "_").replace("-", "_")
    # Quitar acentos básicos
    for a, b in (
        ("Á", "A"),
        ("É", "E"),
        ("Í", "I"),
        ("Ó", "O"),
        ("Ú", "U"),
        ("Ñ", "N"),
    ):
        s = s.replace(a, b)
    return s


def _indice_campos(fieldnames: list[str]) -> dict[str, str]:
    """{NOMBRE_NORMALIZADO: nombre_original}."""
    out: dict[str, str] = {}
    for c in fieldnames:
        key = _norm_nombre(c)
        if key and key not in out:
            out[key] = c
    return out


def _buscar_alias(indice: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    for a in aliases:
        if a in indice:
            return indice[a]
    return None


def _parece_datetime(valor: str) -> bool:
    t = (valor or "").strip()
    if not t:
        return False
    if "T" in t or " " in t:
        return True
    # Solo fecha YYYY-MM-DD / DD/MM/YYYY
    return bool(re.fullmatch(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", t))


def _parece_solo_fecha(valor: str) -> bool:
    t = (valor or "").strip()
    return bool(re.fullmatch(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", t))


def _parece_solo_hora(valor: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", (valor or "").strip()))


def _es_fila_metadatos(fila: dict[str, str]) -> bool:
    """Fila de tipos (FMT_DT_DATE, FMT_UINT32, …) u otra fila no dato."""
    vals = [(v or "").strip().upper() for v in fila.values() if v is not None]
    if not vals:
        return True
    n_fmt = sum(1 for v in vals if v.startswith("FMT_"))
    return n_fmt >= max(2, (len(vals) + 1) // 2)


def _nombre_sugiere_acumulado(nombre: str) -> bool:
    n = _norm_nombre(nombre)
    return (
        n.startswith("OBJ_CNT")
        or "_CNT_" in n
        or n.startswith("CNT_")
        or "CONTADOR" in n
    )


def detectar_acumulado_y_factor(
    series: dict[str, list[float]],
    nombres_orig: list[str],
) -> tuple[bool, float]:
    """
    Detecta contadores acumulados y factor a kWh.

    Contadores típicos (OBJ_CNT_TL_AP) vienen en Wh → factor 0.001.
    Perfiles de intervalo (API / kWh por periodo) no se tratan como acumulados
    aunque una muestra corta sea monótona.
    """
    if not series:
        return False, 1.0

    por_nombre = any(_nombre_sugiere_acumulado(n) for n in nombres_orig)

    no_dec = 0
    pares = 0
    todos_vals: list[float] = []
    deltas_pos: list[float] = []
    for vals in series.values():
        # Solo series de energía activa para el patrón (evitar KVARH en 0)
        todos_vals.extend(vals)
        for a, b in zip(vals, vals[1:]):
            pares += 1
            if b + 1e-9 >= a:
                no_dec += 1
            d = b - a
            if d >= 0:
                deltas_pos.append(d)

    monotona = pares > 0 and (no_dec / pares) >= 0.9
    med_abs = (
        sorted(abs(v) for v in todos_vals)[len(todos_vals) // 2] if todos_vals else 0.0
    )
    n_obs = max((len(v) for v in series.values()), default=0)

    # Por nombre (OBJ_CNT_…) o por patrón fuerte de registro de medidor
    if por_nombre:
        acumulado = True
    elif monotona and n_obs >= 10 and med_abs >= 1_000:
        acumulado = True
    else:
        acumulado = False

    if not acumulado:
        return False, 1.0

    factor = 1.0
    if todos_vals and deltas_pos:
        med_d = sorted(deltas_pos)[len(deltas_pos) // 2]
        if med_abs >= 1_000 and med_d >= 1:
            factor = 0.001
    return True, factor


def mapear_columnas(
    fieldnames: list[str],
    muestra_filas: list[dict[str, str]] | None = None,
) -> MapaColumnas:
    """
    Asocia encabezados del archivo a roles canónicos.

    Si FECHA trae datetime completa se usa como fecha_hora.
    Si FECHA es solo día y existe HORA, se usan columnas separadas.
    """
    indice = _indice_campos(fieldnames)
    mapa = MapaColumnas()

    col_fh = _buscar_alias(indice, ALIAS_FECHA_HORA)
    col_hora = _buscar_alias(indice, ALIAS_HORA)
    # No reutilizar la misma columna física como "hora" si ya es fecha_hora
    if col_hora and col_fh and _norm_nombre(col_hora) == _norm_nombre(col_fh):
        col_hora = None

    filas_util = [
        f for f in (muestra_filas or []) if not _es_fila_metadatos(f)
    ]

    muestra_val = ""
    if col_fh and filas_util:
        for fila in filas_util:
            v = (fila.get(col_fh) or "").strip()
            if v and not v.upper().startswith("FMT_"):
                muestra_val = v
                break

    # Si hay columnas Fecha + Hora, preferir separadas cuando FECHA es solo día
    if col_fh and col_hora and (
        not muestra_val or _parece_solo_fecha(muestra_val)
    ):
        mapa.fecha_dia = col_fh
        mapa.hora = col_hora
    elif col_fh and muestra_val and _parece_solo_fecha(muestra_val) and col_hora:
        mapa.fecha_dia = col_fh
        mapa.hora = col_hora
    elif col_fh and muestra_val and _parece_datetime(muestra_val):
        mapa.fecha_hora = col_fh
    elif col_fh and col_hora:
        mapa.fecha_dia = col_fh
        mapa.hora = col_hora
    elif col_fh:
        mapa.fecha_hora = col_fh
    else:
        col_dia = _buscar_alias(indice, ALIAS_FECHA_DIA)
        if col_dia and col_hora:
            mapa.fecha_dia = col_dia
            mapa.hora = col_hora
        elif col_dia:
            mapa.fecha_hora = col_dia

    usados = {
        _norm_nombre(x)
        for x in (mapa.fecha_hora, mapa.fecha_dia, mapa.hora)
        if x
    }

    def _map_energia(canon: str, aliases: tuple[str, ...]) -> None:
        col = _buscar_alias(indice, aliases)
        if col and _norm_nombre(col) not in usados and canon not in mapa.energia:
            if any(_norm_nombre(col) == _norm_nombre(v) for v in mapa.energia.values()):
                return
            mapa.energia[canon] = col

    _map_energia("KWH_REC", ALIAS_KWH_REC)
    _map_energia("KWH_ENT", ALIAS_KWH_ENT)
    _map_energia("KWH_GEN", ALIAS_KWH_GEN)
    for canon, aliases in ALIAS_KVARH.items():
        _map_energia(canon, aliases)

    return mapa


# ---------------------------------------------------------------------------
# Frecuencia
# ---------------------------------------------------------------------------

def detectar_frecuencia_min(timestamps: list[datetime]) -> int | None:
    """Moda de deltas entre timestamps consecutivos, redondeada a frecuencias conocidas."""
    if len(timestamps) < 2:
        return None
    ordenados = sorted(timestamps)
    deltas_min: list[int] = []
    for a, b in zip(ordenados, ordenados[1:]):
        seg = (b - a).total_seconds()
        if seg <= 0:
            continue
        minutos = int(round(seg / 60.0))
        if minutos > 0:
            deltas_min.append(minutos)
    if not deltas_min:
        return None
    moda = Counter(deltas_min).most_common(1)[0][0]
    # Ajustar a frecuencia conocida más cercana si está cerca (±20 %)
    for f in FRECUENCIAS_CONOCIDAS:
        if abs(moda - f) <= max(1, int(f * 0.2)):
            return f
    return moda


# ---------------------------------------------------------------------------
# Inspección completa
# ---------------------------------------------------------------------------

def _abrir_texto(ruta: Path, encoding: str):
    return ruta.open("r", newline="", encoding=encoding)


def _leer_muestra_filas(
    ruta: Path,
    encoding: str,
    delimitador: str,
    max_filas: int = 300,
) -> tuple[list[str], list[dict[str, str]]]:
    with _abrir_texto(ruta, encoding) as f:
        reader = csv.DictReader(f, delimiter=delimitador)
        if not reader.fieldnames:
            raise ValueError(f"CSV sin encabezado: {ruta.name}")
        encabezados = [c for c in reader.fieldnames if c is not None]
        filas: list[dict[str, str]] = []
        for row in reader:
            fila = {k: (v if v is not None else "") for k, v in row.items() if k}
            if _es_fila_metadatos(fila):
                continue
            filas.append(fila)
            if len(filas) >= max_filas:
                break
        return encabezados, filas


def inspeccionar_perfil(ruta: Path, max_filas: int = 300) -> PerfilMeta:
    """Detecta encoding, delimitador, columnas, formato de fecha y frecuencia."""
    encoding = detectar_codificacion(ruta)
    raw_txt = ruta.read_bytes()[:64_000].decode(encoding, errors="replace")
    delimitador = detectar_delimitador(raw_txt)
    encabezados, filas = _leer_muestra_filas(
        ruta, encoding, delimitador, max_filas=max_filas
    )
    columnas = mapear_columnas(encabezados, filas)

    if not columnas.tiene_marca_tiempo():
        raise ValueError(
            f"No se encontró columna de fecha/hora en {ruta.name}. "
            f"Encabezados: {encabezados}"
        )
    if not columnas.energia:
        raise ValueError(
            f"No se encontró columna de energía (KWH_REC/KWH_ENT/…) en {ruta.name}. "
            f"Encabezados: {encabezados}"
        )

    formato_fecha: str | None = None
    formato_hora: str | None = None
    muestra_fecha = ""
    stamps: list[datetime] = []
    series: dict[str, list[float]] = {c: [] for c in columnas.energia}

    def _tomar_energia(fila: dict[str, str]) -> None:
        for canon, orig in columnas.energia.items():
            try:
                series[canon].append(_float_celda(fila.get(orig, "")))
            except ValueError:
                series[canon].append(0.0)

    if columnas.fecha_hora:
        for fila in filas:
            v = (fila.get(columnas.fecha_hora) or "").strip()
            if v:
                muestra_fecha = v
                break
        if not muestra_fecha:
            raise ValueError(f"Columna {columnas.fecha_hora!r} vacía en {ruta.name}")
        formato_fecha = detectar_formato_fecha(muestra_fecha)
        for fila in filas:
            v = (fila.get(columnas.fecha_hora) or "").strip()
            if not v:
                continue
            try:
                stamps.append(parsear_fecha(v, formato_fecha))
                _tomar_energia(fila)
            except ValueError:
                continue
    else:
        assert columnas.fecha_dia and columnas.hora
        m_f = m_h = ""
        for fila in filas:
            if not m_f:
                m_f = (fila.get(columnas.fecha_dia) or "").strip()
            if not m_h:
                m_h = (fila.get(columnas.hora) or "").strip()
            if m_f and m_h:
                break
        if not m_f or not m_h:
            raise ValueError(
                f"No hay muestras de fecha/hora separadas en {ruta.name}"
            )
        muestra_fecha = f"{m_f} {m_h}"
        formato_fecha = detectar_formato_fecha(m_f)
        if " " in formato_fecha or "%H" in formato_fecha:
            formato_fecha = detectar_formato_fecha(
                m_f if _parece_solo_fecha(m_f) else m_f[:10]
            )
            if "%H" in formato_fecha:
                parte = _parte_fecha(m_f)
                sep = "-" if "-" in parte else "/"
                formato_fecha = (
                    f"%Y{sep}%m{sep}%d"
                    if len(parte.split(sep)[0]) == 4
                    else f"%d{sep}%m{sep}%Y"
                )
        formato_hora = detectar_formato_hora(m_h)
        for fila in filas:
            fd = (fila.get(columnas.fecha_dia) or "").strip()
            fh = (fila.get(columnas.hora) or "").strip()
            if not fd or not fh:
                continue
            try:
                stamps.append(
                    parsear_fecha_hora_separadas(fd, fh, formato_fecha, formato_hora)
                )
                _tomar_energia(fila)
            except ValueError:
                continue

    freq = detectar_frecuencia_min(stamps)
    acumulado, factor = detectar_acumulado_y_factor(
        series, list(columnas.energia.values())
    )

    return PerfilMeta(
        encoding=encoding,
        delimitador=delimitador,
        encabezados=encabezados,
        columnas=columnas,
        formato_fecha=formato_fecha,
        formato_hora=formato_hora,
        frecuencia_min=freq,
        muestra_fecha=muestra_fecha,
        filas_muestra=len(filas),
        acumulado=acumulado,
        factor_energia=factor,
    )


def datetime_de_fila(fila: dict[str, str], meta: PerfilMeta) -> datetime:
    cols = meta.columnas
    if cols.fecha_hora:
        assert meta.formato_fecha
        return parsear_fecha(fila.get(cols.fecha_hora, ""), meta.formato_fecha)
    assert cols.fecha_dia and cols.hora and meta.formato_fecha and meta.formato_hora
    return parsear_fecha_hora_separadas(
        fila.get(cols.fecha_dia, ""),
        fila.get(cols.hora, ""),
        meta.formato_fecha,
        meta.formato_hora,
    )


def _float_celda(valor: str) -> float:
    t = (valor or "").strip()
    if not t:
        return 0.0
    # Decimal europeo: 1.234,56 → 1234.56
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t and "." not in t:
        t = t.replace(",", ".")
    return float(t)


def iter_filas_perfil(
    ruta: Path, meta: PerfilMeta | None = None
) -> Iterator[tuple[datetime, dict[str, float]]]:
    """Yield (datetime, {KWH_REC: float, ...}) usando la meta detectada."""
    meta = meta or inspeccionar_perfil(ruta)
    prev_vals: dict[str, float] | None = None

    with _abrir_texto(ruta, meta.encoding) as f:
        reader = csv.DictReader(f, delimiter=meta.delimitador)
        for row in reader:
            fila = {k: (v if v is not None else "") for k, v in row.items() if k}
            if _es_fila_metadatos(fila):
                continue
            try:
                dt = datetime_de_fila(fila, meta)
            except ValueError:
                continue
            vals: dict[str, float] = {}
            for canon, orig in meta.columnas.energia.items():
                try:
                    vals[canon] = _float_celda(fila.get(orig, ""))
                except ValueError:
                    vals[canon] = 0.0

            if meta.acumulado:
                if prev_vals is None:
                    prev_vals = vals
                    continue
                out: dict[str, float] = {}
                for k, v in vals.items():
                    delta = v - prev_vals.get(k, v)
                    if delta < 0:
                        # Reinicio / overflow del contador: no inventar energía
                        delta = 0.0
                    out[k] = delta * meta.factor_energia
                prev_vals = vals
                yield dt, out
            else:
                if meta.factor_energia != 1.0:
                    vals = {k: v * meta.factor_energia for k, v in vals.items()}
                yield dt, vals


def es_canonico(meta: PerfilMeta) -> bool:
    """True si ya está en el formato que el pipeline espera."""
    if meta.acumulado:
        return False
    cols = meta.columnas
    if meta.delimitador != ",":
        return False
    if meta.encoding not in ("utf-8-sig", "utf-8"):
        return False
    if not cols.fecha_hora:
        return False
    if meta.formato_fecha not in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        return False
    for canon, orig in cols.energia.items():
        if _norm_nombre(orig) != canon:
            return False
    if _norm_nombre(cols.fecha_hora) != "FECHA":
        return False
    return True


def normalizar_perfil(ruta: Path, forzar: bool = False) -> Path:
    """
    Reescribe el perfil en formato canónico (UTF-8-SIG, coma, FECHA estándar).

    Si ya es canónico y forzar=False, devuelve la misma ruta.
    Sustituye el archivo vía temporal en la misma carpeta.
    Contadores acumulados se convierten a energía de intervalo (kWh).
    """
    meta = inspeccionar_perfil(ruta)
    print(f"\n[deteccion] {ruta.name}")
    print(f"  {meta.resumen()}")

    if es_canonico(meta) and not forzar:
        if meta.formato_fecha == "%Y-%m-%d %H:%M:%S":
            return ruta

    fieldnames = ["FECHA"]
    for c in COLS_ENERGIA_CANON:
        if c in meta.columnas.energia:
            fieldnames.append(c)

    tmp = ruta.with_name(ruta.stem + ".__canon__.tmp")
    n = 0
    n_bad = 0
    ejemplos_mal: list[str] = []
    with tmp.open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        for dt, vals in iter_filas_perfil(ruta, meta):
            out_row = {"FECHA": dt.strftime(FMT_CANONICO)}
            for c in fieldnames[1:]:
                out_row[c] = f"{float(vals.get(c, 0.0)):.10g}"
            writer.writerow(out_row)
            n += 1

    tmp.replace(ruta)
    print(f"  normalizado -> {ruta.name}  ({n:,} filas)")
    if n_bad:
        print(f"  filas descartadas por fecha invalida: {n_bad}")
        for ej in ejemplos_mal:
            print(f"    ej: {ej!r}")
    return ruta


def normalizar_perfiles(rutas: list[Path]) -> list[Path]:
    return [normalizar_perfil(p) for p in rutas]
