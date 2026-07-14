"""Descarga perfil ION desde una fecha hasta el ultimo registro del medidor."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bess.data.ingest.ion.modbus import (
    DATA_RECORDER_MODULE,
    NOMBRES_SOURCES,
    NUM_SOURCES_DEFAULT,
    PUERTO_DEFAULT,
    ZONA_HORARIA_DEFAULT,
    _buscar_registro_por_fecha,
    conectar,
    formatear_fecha,
    leer_rango_registros,
    leer_registro_por_numero,
    mapear_sources_bess,
    parse_fecha_arg,
    seleccionar_data_recorder,
)


def resolver_rango_desde_ultimo(
    client,
    module_num: int,
    num_sources: int,
    zona: ZoneInfo,
    como_float: bool,
    desde_solicitado: datetime,
) -> tuple[int, int, datetime, datetime, bool]:
    """
    Resuelve indices [inicio, fin] desde la fecha solicitada hasta el ultimo registro.

    Si desde_solicitado es anterior al primer registro, inicio = registro mas antiguo
    y el quinto valor de retorno es True (aviso al usuario).
    """
    if not seleccionar_data_recorder(client, module_num):
        raise RuntimeError(f"No se pudo seleccionar Data Recorder modulo {module_num}")

    rango = leer_rango_registros(client)
    if rango is None:
        raise RuntimeError("El medidor no tiene registros de perfil disponibles")

    oldest, newest = rango
    primero = leer_registro_por_numero(client, oldest, num_sources, zona, como_float)
    ultimo = leer_registro_por_numero(client, newest, num_sources, zona, como_float)
    if primero is None or ultimo is None:
        raise RuntimeError("No se pudo leer el rango temporal del medidor")

    fecha_antigua = desde_solicitado < primero.fecha
    if fecha_antigua:
        inicio = oldest
        fecha_inicio = primero.fecha
    else:
        if desde_solicitado > ultimo.fecha:
            raise RuntimeError(
                f"No hay registros desde {formatear_fecha(desde_solicitado)}. "
                f"Ultimo registro: {formatear_fecha(ultimo.fecha)}"
            )
        reg = _buscar_registro_por_fecha(
            client,
            oldest,
            newest,
            num_sources,
            zona,
            como_float,
            desde_solicitado,
            True,
        )
        inicio = reg if reg is not None else oldest
        registro_inicio = leer_registro_por_numero(
            client, inicio, num_sources, zona, como_float
        )
        fecha_inicio = registro_inicio.fecha if registro_inicio else primero.fecha

    return inicio, newest, fecha_inicio, ultimo.fecha, fecha_antigua


def _ruta_salida_default(ip: str, zona: ZoneInfo) -> Path:
    ip_seguro = ip.replace(".", "_")
    ahora = datetime.now(zona)
    stamp = ahora.strftime("%Y%m%d_%H%M%S")
    return Path.cwd() / f"{ip_seguro}_{stamp}.csv"


def descargar_perfil_ion(
    ip: str,
    desde_texto: str,
    salida: Path | None = None,
    puerto: int = PUERTO_DEFAULT,
    module_num: int = DATA_RECORDER_MODULE,
    num_sources: int = NUM_SOURCES_DEFAULT,
    zona: ZoneInfo | None = None,
    como_float: bool = True,
) -> Path:
    """Descarga perfil CSV desde fecha inicio hasta el ultimo registro del medidor."""
    zona = zona or ZoneInfo(ZONA_HORARIA_DEFAULT)
    desde_solicitado = parse_fecha_arg(desde_texto, zona)

    print(f"Medidor: {ip}:{puerto}  (Data Recorder modulo {module_num})")
    print(f"Fecha solicitada: {formatear_fecha(desde_solicitado)}")

    client = conectar(ip, puerto)
    if not client.is_socket_open():
        raise RuntimeError(f"No se pudo conectar a {ip}:{puerto}")

    try:
        inicio, fin, fecha_inicio, fecha_fin, fecha_antigua = resolver_rango_desde_ultimo(
            client, module_num, num_sources, zona, como_float, desde_solicitado
        )

        if fecha_antigua:
            print()
            print("AVISO: La fecha solicitada es anterior al primer registro disponible.")
            print(f"  Solicitada:  {formatear_fecha(desde_solicitado)}")
            print(f"  Disponible desde: {formatear_fecha(fecha_inicio)}")
            print("  Se descargaran todos los datos disponibles en el medidor.")
            print()

        total = fin - inicio + 1
        print(f"Rango efectivo: {formatear_fecha(fecha_inicio)} -> {formatear_fecha(fecha_fin)}")
        print(f"Registros a descargar: {total} (#{inicio} .. #{fin})")

        destino = salida or _ruta_salida_default(ip, zona)
        destino.parent.mkdir(parents=True, exist_ok=True)

        columnas = ["Fecha"] + [
            NOMBRES_SOURCES[i] if i < len(NOMBRES_SOURCES) else f"Source_{i + 1}"
            for i in range(num_sources)
        ]

        filas: list[list] = []
        for idx, record_num in enumerate(range(inicio, fin + 1), start=1):
            registro = leer_registro_por_numero(
                client, record_num, num_sources, zona, como_float
            )
            if registro is None:
                print(f"  ADVERTENCIA: fallo lectura registro {record_num}")
                continue

            mapeado = mapear_sources_bess(registro.valores)
            fila = [formatear_fecha(registro.fecha)] + [
                mapeado[NOMBRES_SOURCES[i]] for i in range(num_sources)
            ]
            filas.append(fila)

            if idx % 100 == 0 or idx == total:
                print(f"  Progreso: {idx}/{total} registros...")

        if not filas:
            raise RuntimeError("No se descargaron registros")

        with destino.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, lineterminator="\r\n")
            writer.writerow(columnas)
            writer.writerows(filas)

        print(f"Descargados {len(filas)} registros -> {destino}")
        print(f"  Rango temporal: {filas[0][0]}  a  {filas[-1][0]}")
        return destino
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga perfil de carga ION desde una fecha hasta el ultimo registro "
            "disponible en el medidor."
        ),
        epilog=(
            "Ejemplo (Python):\n"
            "  python scripts\\descargar_ion.py 172.16.111.209 2026-05-01\n"
            "  python scripts\\descargar_ion.py 172.16.111.209 2026-05-01 salida.csv\n\n"
            "Ejemplo (ejecutable):\n"
            "  .\\descargar_ion.exe 172.16.111.209 2026-05-01"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("ip", help="Direccion IP del medidor ION")
    parser.add_argument(
        "desde",
        help="Fecha de inicio (YYYY-MM-DD o YYYY-MM-DD HH:MM:SS)",
    )
    parser.add_argument(
        "salida",
        nargs="?",
        default=None,
        help="Ruta del CSV de salida (opcional; default: ./<ip>_<YYYYMMDD_HHMMSS>.csv en la carpeta actual)",
    )
    parser.add_argument("--puerto", type=int, default=PUERTO_DEFAULT)
    parser.add_argument("--modulo-dr", type=int, default=DATA_RECORDER_MODULE)
    parser.add_argument("--sources", type=int, default=NUM_SOURCES_DEFAULT)
    parser.add_argument(
        "--int32",
        action="store_true",
        help="Decodificar sources como int32 en lugar de float32",
    )

    args = parser.parse_args(argv)
    salida = Path(args.salida) if args.salida else None

    try:
        descargar_perfil_ion(
            ip=args.ip,
            desde_texto=args.desde,
            salida=salida,
            puerto=args.puerto,
            module_num=args.modulo_dr,
            num_sources=args.sources,
            como_float=not args.int32,
        )
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
