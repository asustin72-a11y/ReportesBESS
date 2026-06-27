"""
Lectura Modbus TCP de medidor Schneider ION 8650.

Incluye:
  - Prueba del mapa Default (mediciones instantaneas)
  - Lectura de Data Recorder (perfil de carga historico)

Nota de direccionamiento:
  Schneider documenta registros como 40xxx / 43xxx.
  pymodbus usa offset = registro_schneider - 40001.
  Ejemplo: 43001 -> direccion 3000, 40011 -> direccion 10.
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pymodbus.client import ModbusTcpClient

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
MEDIDOR_IP_DEFAULT = "172.16.111.209"
PUERTO_DEFAULT = 502
MEDIDOR_IP = MEDIDOR_IP_DEFAULT  # alias para compatibilidad
PUERTO = PUERTO_DEFAULT

from bess.config.paths import DIRECTORIO_BASE

RUTA_MAPA_MODBUS = DIRECTORIO_BASE / "modbus_map_default.csv"

# Numero de modulo Data Recorder en ION Setup (ajustar segun medidor)
DATA_RECORDER_MODULE = 1

# Registros Schneider -> se convierten con reg_a_direccion()
REG_DR_MODULE = 43001
REG_DR_START_RECORD = 43002
REG_DR_OLDEST_RECORD = 43008
REG_DR_NEWEST_RECORD = 43010
REG_DR_BLOCK_START = 43012
REG_DR_UTC_SECONDS = 43014
REG_DR_UTC_MICROSECONDS = 43016
REG_DR_SOURCE1_DATA = 43018

REGISTROS_HEADER_REGISTRO = 6  # RecordNum + UTC seconds + UTC microseconds
REGISTROS_POR_SOURCE = 2

ZONA_HORARIA_DEFAULT = "America/Mexico_City"

# Orden de sources del Data Recorder modulo 1 (6 canales de energia; sin Source_7).
# El canal 1 del DR trae la energia activa recibida; BESS la espera en KWH_REC.
NOMBRES_SOURCES = ["KWH_REC", "KWH_ENT", "KVARH_Q1", "KVARH_Q2", "KVARH_Q3", "KVARH_Q4"]
NUM_SOURCES_DEFAULT = 6


def mapear_sources_bess(valores: list[float]) -> dict[str, float]:
    """
    Asigna cada source del Data Recorder a la columna BESS correspondiente.
    Usado en descarga CSV y sync SQLite para evitar invertir KWH_REC/KWH_ENT.
    """
    resultado = {nombre: 0.0 for nombre in NOMBRES_SOURCES}
    for i, valor in enumerate(valores):
        if i < len(NOMBRES_SOURCES):
            resultado[NOMBRES_SOURCES[i]] = float(valor)
    return resultado

# Parametros clave del mapa Default (bloque 40150+ / 402xx)
PARAMETROS_INSTANTANEOS = [
    "Vln avg scaled",
    "I avg scaled",
    "Freq",
    "kW tot scaled",
    "kWh del",
    "kWh rec",
    "kVARh del",
    "kVARh rec",
]

VALORES_INVALIDOS = {65535, 65530, -1}


@dataclass(frozen=True)
class ParametroModbus:
    nombre: str
    address: int
    regs: int
    formato: str
    scaling: float


@dataclass
class RegistroPerfil:
    record_num: int
    fecha: datetime
    valores: list[float]


# ---------------------------------------------------------------------------
# Mapa Modbus (CSV Schneider)
# ---------------------------------------------------------------------------
def cargar_mapa_modbus(ruta: Path) -> dict[str, ParametroModbus]:
    """Carga el CSV Default Modbus Map. Ante nombres duplicados prefiere address >= 40150."""
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontro mapa Modbus: {ruta}")

    mapa: dict[str, ParametroModbus] = {}
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # titulo
        next(reader, None)  # linea vacia
        next(reader, None)  # encabezado

        for fila in reader:
            if len(fila) < 6 or not fila[0].strip():
                continue
            param = ParametroModbus(
                nombre=fila[0].strip(),
                address=int(fila[1]),
                regs=int(fila[2]),
                formato=fila[3].strip(),
                scaling=float(fila[4]),
            )
            previo = mapa.get(param.nombre)
            if previo is None or param.address >= previo.address:
                mapa[param.nombre] = param
    return mapa


def buscar_parametro(mapa: dict[str, ParametroModbus], nombre: str) -> ParametroModbus | None:
    clave = nombre.strip().lower()
    for param in mapa.values():
        if param.nombre.lower() == clave:
            return param
    return None


# ---------------------------------------------------------------------------
# Utilidades Modbus
# ---------------------------------------------------------------------------
def reg_a_direccion(registro_schneider: int) -> int:
    """Convierte numero de registro Schneider (40xxx) a direccion pymodbus."""
    return registro_schneider - 40001


def int32_desde_registros(high: int, low: int) -> int:
    valor = (high << 16) | low
    if valor >= 0x80000000:
        valor -= 0x100000000
    return valor


def uint32_desde_registros(high: int, low: int) -> int:
    return (high << 16) | low


def int16_desde_registro(reg: int) -> int:
    return reg - 0x10000 if reg >= 0x8000 else reg


def float32_desde_registros(high: int, low: int) -> float:
    return struct.unpack(">f", struct.pack(">HH", high, low))[0]


def int32_a_registros(valor: int) -> list[int]:
    if valor < 0:
        valor += 0x100000000
    return [(valor >> 16) & 0xFFFF, valor & 0xFFFF]


def conectar(ip: str = MEDIDOR_IP_DEFAULT, puerto: int = PUERTO_DEFAULT) -> ModbusTcpClient:
    client = ModbusTcpClient(ip, port=puerto)
    client.connect()
    return client


def leer_holding(client: ModbusTcpClient, registro: int, count: int = 1) -> list[int] | None:
    resultado = client.read_holding_registers(
        address=reg_a_direccion(registro), count=count
    )
    if resultado.isError():
        return None
    return list(resultado.registers)


def escribir_uint16(client: ModbusTcpClient, registro: int, valor: int) -> bool:
    resultado = client.write_register(address=reg_a_direccion(registro), value=valor)
    return not resultado.isError()


def escribir_int32(client: ModbusTcpClient, registro: int, valor: int) -> bool:
    regs = int32_a_registros(valor)
    resultado = client.write_registers(address=reg_a_direccion(registro), values=regs)
    return not resultado.isError()


def leer_int32(client: ModbusTcpClient, registro: int) -> int | None:
    regs = leer_holding(client, registro, 2)
    if regs is None or len(regs) < 2:
        return None
    return int32_desde_registros(regs[0], regs[1])


def leer_parametro_raw(client: ModbusTcpClient, param: ParametroModbus) -> int | None:
    regs = leer_holding(client, param.address, param.regs)
    if regs is None or len(regs) < param.regs:
        return None

    fmt = param.formato.upper()
    if param.regs == 1:
        if fmt.startswith("INT16"):
            return int16_desde_registro(regs[0])
        return regs[0]
    if fmt.startswith("UINT32"):
        return uint32_desde_registros(regs[0], regs[1])
    return int32_desde_registros(regs[0], regs[1])


def escalar_valor(raw: int, param: ParametroModbus) -> float:
    if param.scaling == 0:
        return float(raw)
    return raw / param.scaling


def leer_parametro(client: ModbusTcpClient, param: ParametroModbus) -> tuple[int | None, float | None]:
    raw = leer_parametro_raw(client, param)
    if raw is None:
        return None, None
    return raw, escalar_valor(raw, param)


def decodificar_source(high: int, low: int, como_float: bool) -> float:
    if como_float:
        return float32_desde_registros(high, low)
    return float(int32_desde_registros(high, low))


def timestamp_desde_registros(
    utc_seconds: int,
    utc_microseconds: int,
    zona: ZoneInfo,
) -> datetime:
    """Convierte UTC Seconds + MicroSeconds del bloque Data Recorder a datetime local."""
    dt_utc = datetime.fromtimestamp(utc_seconds, tz=timezone.utc)
    if utc_microseconds:
        dt_utc = dt_utc.replace(microsecond=min(utc_microseconds, 999_999))
    return dt_utc.astimezone(zona)


def formatear_fecha(fecha: datetime) -> str:
    return fecha.strftime("%Y-%m-%d %H:%M:%S")


def parse_fecha_arg(texto: str, zona: ZoneInfo, es_hasta: bool = False) -> datetime:
    """Parsea YYYY-MM-DD o YYYY-MM-DD HH:MM:SS en datetime con zona horaria."""
    texto = texto.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(texto, fmt)
            if fmt == "%Y-%m-%d":
                if es_hasta:
                    dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=zona)
        except ValueError:
            continue
    raise ValueError(
        f"Fecha invalida: {texto!r}. Usa YYYY-MM-DD o YYYY-MM-DD HH:MM:SS"
    )


# ---------------------------------------------------------------------------
# Mapa Default (mediciones instantaneas)
# ---------------------------------------------------------------------------
def listar_parametros(mapa: dict[str, ParametroModbus], filtro: str | None = None) -> None:
    print("-" * 80)
    print("PARAMETROS DEL MAPA MODBUS")
    print("-" * 80)
    filtro_lower = filtro.lower() if filtro else None
    for nombre in sorted(mapa):
        if filtro_lower and filtro_lower not in nombre.lower():
            continue
        p = mapa[nombre]
        print(f"  {p.address:>5}  {p.regs} reg  {p.formato:<12}  scale={p.scaling:<6g}  {p.nombre}")


def leer_instantaneas(client: ModbusTcpClient, mapa: dict[str, ParametroModbus]) -> None:
    print("-" * 80)
    print("MEDICIONES INSTANTANEAS (mapa Default MW-1411A150-01)")
    print("-" * 80)

    mapa_vacio = True
    for nombre in PARAMETROS_INSTANTANEOS:
        param = mapa.get(nombre)
        if param is None:
            print(f"  {nombre:<24} NO EN MAPA")
            continue

        raw, valor = leer_parametro(client, param)
        if raw is None:
            print(f"  {param.address:>5} {nombre:<24} ERROR lectura")
            continue

        if raw not in VALORES_INVALIDOS:
            mapa_vacio = False
        unidad = _unidad_parametro(nombre)
        print(
            f"  {param.address:>5} {nombre:<24} raw={raw!s:>14} -> "
            f"{valor:>12.3f} {unidad}"
        )

    print("-" * 80)
    if mapa_vacio:
        print("Mapa sin vincular (65535 / -1). Configura Source en ION Setup.")
    else:
        print("Lecturas validas recibidas.")


def leer_parametro_por_nombre(
    client: ModbusTcpClient,
    mapa: dict[str, ParametroModbus],
    nombre: str,
) -> None:
    param = buscar_parametro(mapa, nombre)
    if param is None:
        print(f"Parametro no encontrado en mapa: {nombre}")
        return

    raw, valor = leer_parametro(client, param)
    if raw is None:
        print(f"ERROR lectura: {param.nombre} @ {param.address}")
        return

    print(f"{param.nombre}")
    print(f"  Address : {param.address}")
    print(f"  Formato : {param.formato} ({param.regs} reg)")
    print(f"  Scaling : {param.scaling}")
    print(f"  Raw     : {raw}")
    print(f"  Valor   : {valor:.6f} {_unidad_parametro(param.nombre)}")


def _unidad_parametro(nombre: str) -> str:
    n = nombre.lower()
    if "kwh" in n:
        return "kWh"
    if "kvarh" in n:
        return "kVArh"
    if "kvah" in n:
        return "kVAh"
    if "kw" in n:
        return "kW"
    if "kvar" in n:
        return "kVAr"
    if "kva" in n:
        return "kVA"
    if "vln" in n or "vll" in n:
        return "V"
    if n.startswith("i ") or " i " in n or n.endswith(" scaled") and "i " in n:
        return "A"
    if "freq" in n:
        return "Hz"
    if "pf" in n:
        return ""
    if "thd" in n:
        return "%"
    return ""


def probar_mapa_default(client: ModbusTcpClient, mapa: dict[str, ParametroModbus]) -> None:
    """Alias del modo instantaneas para compatibilidad."""
    leer_instantaneas(client, mapa)


# ---------------------------------------------------------------------------
# Data Recorder (perfil de carga)
# ---------------------------------------------------------------------------
def seleccionar_data_recorder(client: ModbusTcpClient, module_num: int) -> bool:
    ok = escribir_uint16(client, REG_DR_MODULE, module_num)
    if not ok:
        print(f"ERROR: no se pudo seleccionar Data Recorder modulo {module_num}")
    return ok


def leer_rango_registros(client: ModbusTcpClient) -> tuple[int, int] | None:
    oldest = leer_int32(client, REG_DR_OLDEST_RECORD)
    newest = leer_int32(client, REG_DR_NEWEST_RECORD)
    if oldest is None or newest is None:
        return None
    if oldest < 0 or newest < 0:
        return None
    return oldest, newest


def solicitar_registro(client: ModbusTcpClient, record_num: int) -> bool:
    return escribir_int32(client, REG_DR_START_RECORD, record_num)


def leer_registro_perfil(
    client: ModbusTcpClient,
    num_sources: int,
    zona: ZoneInfo,
    como_float: bool = True,
) -> RegistroPerfil | None:
    """Lee bloque 43012+ con RecordNum, timestamp UTC y sources (Appendix B Schneider)."""
    total_regs = REGISTROS_HEADER_REGISTRO + num_sources * REGISTROS_POR_SOURCE
    regs = leer_holding(client, REG_DR_BLOCK_START, total_regs)
    if regs is None or len(regs) < total_regs:
        return None

    record_num = uint32_desde_registros(regs[0], regs[1])
    utc_seconds = uint32_desde_registros(regs[2], regs[3])
    utc_microseconds = uint32_desde_registros(regs[4], regs[5])

    if utc_seconds == 0 and record_num in VALORES_INVALIDOS:
        return None

    fecha = timestamp_desde_registros(utc_seconds, utc_microseconds, zona)

    valores = []
    for i in range(num_sources):
        base = REGISTROS_HEADER_REGISTRO + i * REGISTROS_POR_SOURCE
        valores.append(decodificar_source(regs[base], regs[base + 1], como_float))

    return RegistroPerfil(record_num=record_num, fecha=fecha, valores=valores)


def leer_registro_por_numero(
    client: ModbusTcpClient,
    record_num: int,
    num_sources: int,
    zona: ZoneInfo,
    como_float: bool,
) -> RegistroPerfil | None:
    if not solicitar_registro(client, record_num):
        return None
    return leer_registro_perfil(client, num_sources, zona, como_float)


def _buscar_registro_por_fecha(
    client: ModbusTcpClient,
    oldest: int,
    newest: int,
    num_sources: int,
    zona: ZoneInfo,
    como_float: bool,
    limite: datetime,
    buscar_desde: bool,
) -> int | None:
    """
    buscar_desde=True  -> primer registro con fecha >= limite
    buscar_desde=False -> ultimo registro con fecha <= limite
    """
    lo, hi = oldest, newest
    encontrado: int | None = None

    while lo <= hi:
        mid = (lo + hi) // 2
        registro = leer_registro_por_numero(
            client, mid, num_sources, zona, como_float
        )
        if registro is None:
            lo = mid + 1
            continue

        if buscar_desde:
            if registro.fecha < limite:
                lo = mid + 1
            else:
                encontrado = mid
                hi = mid - 1
        else:
            if registro.fecha > limite:
                hi = mid - 1
            else:
                encontrado = mid
                lo = mid + 1

    return encontrado


def resolver_rango_por_fechas(
    client: ModbusTcpClient,
    oldest: int,
    newest: int,
    num_sources: int,
    zona: ZoneInfo,
    como_float: bool,
    desde: datetime | None,
    hasta: datetime | None,
) -> tuple[int, int] | None:
    inicio = oldest
    fin = newest

    if desde is not None:
        reg_desde = _buscar_registro_por_fecha(
            client, oldest, newest, num_sources, zona, como_float, desde, True
        )
        if reg_desde is None:
            print(f"No hay registros desde {formatear_fecha(desde)}")
            return None
        inicio = reg_desde

    if hasta is not None:
        reg_hasta = _buscar_registro_por_fecha(
            client, oldest, newest, num_sources, zona, como_float, hasta, False
        )
        if reg_hasta is None:
            print(f"No hay registros hasta {formatear_fecha(hasta)}")
            return None
        fin = reg_hasta

    if inicio > fin:
        print("Rango de fechas sin registros en el medidor.")
        return None

    return inicio, fin


def escanear_data_recorders(client: ModbusTcpClient, max_modulo: int = 10) -> None:
    print("-" * 70)
    print(f"ESCANEANDO DATA RECORDERS 1..{max_modulo}")
    print("-" * 70)

    encontrados = 0
    for module_num in range(1, max_modulo + 1):
        if not seleccionar_data_recorder(client, module_num):
            print(f"  Modulo {module_num:>2}: error al seleccionar")
            continue

        rango = leer_rango_registros(client)
        if rango is None:
            print(f"  Modulo {module_num:>2}: sin datos o modulo invalido")
            continue

        oldest, newest = rango
        total = newest - oldest + 1
        print(f"  Modulo {module_num:>2}: registros {oldest}..{newest} ({total} total)")
        encontrados += 1

    print("-" * 70)
    if encontrados == 0:
        print("Ningun Data Recorder respondio. Verifica en ION Setup el modulo y el perfil.")


def probar_data_recorder(
    client: ModbusTcpClient,
    module_num: int,
    num_sources: int,
    zona: ZoneInfo,
    como_float: bool,
) -> None:
    print("-" * 70)
    print(f"DATA RECORDER modulo {module_num}")
    print("-" * 70)

    if not seleccionar_data_recorder(client, module_num):
        return

    print(f"  Sources a leer       : {num_sources}")

    rango = leer_rango_registros(client)
    if rango is None:
        print("ERROR: no se pudo leer rango de registros (43008-43011)")
        return

    oldest, newest = rango
    print(f"  Registro mas antiguo : {oldest}")
    print(f"  Registro mas reciente: {newest}")
    print(f"  Registros disponibles: {newest - oldest + 1}")

    if not solicitar_registro(client, newest):
        print(f"ERROR: no se pudo solicitar registro {newest}")
        return

    registro = leer_registro_perfil(client, num_sources, zona, como_float)
    if registro is None:
        print("ERROR: no se pudo leer bloque del registro")
        return

    tipo = "float32" if como_float else "int32"
    print(f"  Ultimo registro ({registro.record_num}) @ {formatear_fecha(registro.fecha)}:")
    for i, val in enumerate(registro.valores):
        nombre = NOMBRES_SOURCES[i] if i < len(NOMBRES_SOURCES) else f"Source_{i + 1}"
        print(f"    {nombre:<12} = {val:.6f} ({tipo})")


def resolver_rango_descarga(
    client: ModbusTcpClient,
    module_num: int,
    num_sources: int,
    desde: datetime | None,
    hasta: datetime | None,
    cantidad: int | None,
    zona: ZoneInfo,
    como_float: bool,
) -> tuple[int, int, int] | None:
    """Resuelve inicio/fin de registros Modbus. Devuelve (inicio, fin, total)."""
    if not seleccionar_data_recorder(client, module_num):
        return None

    rango = leer_rango_registros(client)
    if rango is None:
        return None

    oldest, newest = rango

    if desde is not None or hasta is not None:
        rango_fechas = resolver_rango_por_fechas(
            client, oldest, newest, num_sources, zona, como_float, desde, hasta
        )
        if rango_fechas is None:
            return None
        inicio, fin = rango_fechas
    elif cantidad is not None:
        inicio = max(oldest, newest - cantidad + 1)
        fin = newest
    else:
        inicio, fin = oldest, newest

    return inicio, fin, fin - inicio + 1


def descargar_perfil(
    client: ModbusTcpClient,
    module_num: int,
    num_sources: int,
    cantidad: int | None,
    desde: datetime | None,
    hasta: datetime | None,
    salida: Path | None,
    zona: ZoneInfo,
    como_float: bool,
) -> Path | None:
    rango_regs = resolver_rango_descarga(
        client, module_num, num_sources, desde, hasta, cantidad, zona, como_float
    )
    if rango_regs is None:
        print("ERROR: no se pudo resolver rango de registros")
        return None

    print(f"Sources a descargar: {num_sources}")

    inicio, fin, total_a_leer = rango_regs

    if desde is not None or hasta is not None:
        if cantidad is not None:
            print("Nota: --cantidad ignorado cuando se usa --desde/--hasta")
        if desde:
            print(f"  Desde: {formatear_fecha(desde)} (registro {inicio})")
        if hasta:
            print(f"  Hasta: {formatear_fecha(hasta)} (registro {fin})")

    print(f"Registros a descargar: {total_a_leer} (#{inicio} .. #{fin})")

    if salida is None:
        if desde and hasta:
            stamp = f"{desde.strftime('%Y%m%d')}_{hasta.strftime('%Y%m%d')}"
        else:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        salida = Path(__file__).resolve().parent / f"perfil_ion_{stamp}.csv"

    columnas = ["Fecha"] + [
        NOMBRES_SOURCES[i] if i < len(NOMBRES_SOURCES) else f"Source_{i + 1}"
        for i in range(num_sources)
    ]

    filas = []
    for idx, record_num in enumerate(range(inicio, fin + 1), start=1):
        registro = leer_registro_por_numero(
            client, record_num, num_sources, zona, como_float
        )
        if registro is None:
            print(f"  ADVERTENCIA: fallo lectura registro {record_num}")
            continue

        if desde and registro.fecha < desde:
            continue
        if hasta and registro.fecha > hasta:
            continue

        mapeado = mapear_sources_bess(registro.valores)
        fila = [formatear_fecha(registro.fecha)] + [
            mapeado[NOMBRES_SOURCES[i]] for i in range(num_sources)
        ]
        filas.append(fila)

        if idx % 100 == 0 or idx == total_a_leer:
            print(f"  Progreso: {idx}/{total_a_leer} registros...")

    if not filas:
        print("No se descargaron registros.")
        return None

    with salida.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columnas)
        writer.writerows(filas)

    print(f"Descargados {len(filas)} registros -> {salida}")
    if filas:
        print(f"  Rango temporal: {filas[0][0]}  a  {filas[-1][0]}")
    return salida


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Lectura Modbus ION 8650")
    parser.add_argument(
        "--modo",
        choices=["default", "instantaneas", "listar", "param", "recorder", "escanear", "descargar"],
        default="instantaneas",
        help="instantaneas=mapa Default; listar=ver CSV; param=leer uno; recorder/descargar=perfil",
    )
    parser.add_argument("--mapa", type=Path, default=RUTA_MAPA_MODBUS, help="Ruta al CSV del mapa Modbus")
    parser.add_argument("--nombre", help="Nombre del parametro (modo param)")
    parser.add_argument("--filtro", help="Filtro de texto (modo listar)")
    parser.add_argument("--modulo-dr", type=int, default=DATA_RECORDER_MODULE)
    parser.add_argument(
        "--sources",
        type=int,
        default=NUM_SOURCES_DEFAULT,
        help=f"Sources a leer del DR (default: {NUM_SOURCES_DEFAULT}, sin canal extra)",
    )
    parser.add_argument("--cantidad", type=int, default=10, help="Ultimos N registros (sin --desde/--hasta)")
    parser.add_argument(
        "--desde",
        help="Fecha inicio del perfil (YYYY-MM-DD o YYYY-MM-DD HH:MM:SS)",
    )
    parser.add_argument(
        "--hasta",
        help="Fecha fin inclusive (YYYY-MM-DD o YYYY-MM-DD HH:MM:SS)",
    )
    parser.add_argument("--salida", type=Path, help="Ruta CSV de salida")
    parser.add_argument(
        "--tz",
        default=ZONA_HORARIA_DEFAULT,
        help=f"Zona horaria para Fecha (default: {ZONA_HORARIA_DEFAULT})",
    )
    parser.add_argument(
        "--int32",
        action="store_true",
        help="Decodificar sources como int32 (por defecto: float32)",
    )
    parser.add_argument(
        "--ip",
        default=MEDIDOR_IP_DEFAULT,
        help=f"IP del medidor ION (default: {MEDIDOR_IP_DEFAULT})",
    )
    parser.add_argument(
        "--puerto",
        type=int,
        default=PUERTO_DEFAULT,
        help=f"Puerto Modbus TCP (default: {PUERTO_DEFAULT})",
    )
    args = parser.parse_args()

    mapa: dict[str, ParametroModbus] | None = None
    if args.modo in {"default", "instantaneas", "listar", "param"}:
        try:
            mapa = cargar_mapa_modbus(args.mapa)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}")
            return 1

    if args.modo == "listar":
        listar_parametros(mapa, args.filtro)
        return 0

    print(f"Conectando a {args.ip}:{args.puerto} ...")
    client = conectar(args.ip, args.puerto)

    if not client.is_socket_open():
        print(f"ERROR: no se pudo conectar a {args.ip}:{args.puerto}")
        return 1

    print(f"Conectado a {args.ip}:{args.puerto}")

    try:
        zona = ZoneInfo(args.tz)
    except Exception:
        print(f"ERROR: zona horaria invalida: {args.tz}")
        return 1

    try:
        if args.modo in {"default", "instantaneas"}:
            leer_instantaneas(client, mapa)
        elif args.modo == "param":
            if not args.nombre:
                print("ERROR: usa --nombre \"kWh rec\" (modo param)")
                return 1
            leer_parametro_por_nombre(client, mapa, args.nombre)
        elif args.modo == "escanear":
            escanear_data_recorders(client, max_modulo=args.modulo_dr)
        elif args.modo == "recorder":
            probar_data_recorder(
                client, args.modulo_dr, args.sources, zona, como_float=not args.int32
            )
        else:
            try:
                desde = parse_fecha_arg(args.desde, zona) if args.desde else None
                hasta = parse_fecha_arg(args.hasta, zona, es_hasta=True) if args.hasta else None
            except ValueError as exc:
                print(f"ERROR: {exc}")
                return 1

            if desde and hasta and desde > hasta:
                print("ERROR: --desde debe ser anterior o igual a --hasta")
                return 1

            descargar_perfil(
                client,
                module_num=args.modulo_dr,
                num_sources=args.sources,
                cantidad=args.cantidad,
                desde=desde,
                hasta=hasta,
                salida=args.salida,
                zona=zona,
                como_float=not args.int32,
            )
    finally:
        client.close()
        print("Conexion cerrada.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
