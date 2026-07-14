#!/usr/bin/env python3
"""
Fase 7 — Limpia CSV legacy y opcionalmente regenera el pipeline completo.

Borra:
  - ArchivosFuente/, ArchivosProcesados/, ArchivosReporte/ (todos los CSV)
  - *_POR_HORA*.csv
  - data/perfiles_granja/
  - CSV de prueba en data/ (tmp_*, ION_*primeros*)

Conserva:
  - data/Tarifas/, logos, modbus_map, bess_perfiles.db, ReportesDiarios/

Uso:
  python scripts/limpiar_datos_legacy.py --dry-run
  python scripts/limpiar_datos_legacy.py --ejecutar
  python scripts/limpiar_datos_legacy.py --ejecutar --reset-validado
  python scripts/limpiar_datos_legacy.py --ejecutar --corrida-completa
  python scripts/limpiar_datos_legacy.py --ejecutar --corrida-completa --sin-sync
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bess.config.paths import DIRECTORIO_BASE
from bess.data.pipeline.cleanup_legacy import limpiar_datos_legacy, listar_archivos_legacy


def _imprimir_lista(archivos: list[Path]) -> None:
    if not archivos:
        print("No hay archivos legacy que borrar.")
        return
    print(f"Se borrarían {len(archivos)} archivo(s):\n")
    for ruta in archivos:
        try:
            rel = ruta.relative_to(DIRECTORIO_BASE)
        except ValueError:
            rel = ruta
        print(f"  {rel}")


def _corrida_completa(*, sin_sync: bool, quiet: bool) -> int:
    from bess.data.ingest.ion.export_csv import exportar_todos
    from bess.config.paths import RUTA_BD_PERFILES
    from bess_core import ejecutar_reporte_bess, filtrar_datos, verificar_datos_fuente

    if sin_sync:
        print("\n=== Export SQLite -> ArchivosFuente ===")
        codigo = exportar_todos(RUTA_BD_PERFILES, quiet=quiet)
        if codigo != 0:
            print("ERROR: exportación incompleta (revisar perfiles en BD).", file=sys.stderr)
            return codigo
    else:
        print("\n=== Sincronizar perfiles ===")
        script = ROOT / "scripts" / "sincronizar_perfiles.py"
        args_sync = [sys.executable, str(script)]
        if quiet:
            args_sync.append("--quiet")
        proc = subprocess.run(args_sync, cwd=str(ROOT))
        if proc.returncode != 0:
            return proc.returncode

    print("\n=== Verificar ===")
    ok_v, msg_v = verificar_datos_fuente()
    print(msg_v if ok_v else f"ERROR: {msg_v}")
    if not ok_v:
        return 1

    print("\n=== Filtrar ===")
    ok_f, msg_f = filtrar_datos()
    print(msg_f if ok_f else f"ERROR: {msg_f}")
    if not ok_f:
        return 1

    print("\n=== Generar reportes ===")
    ok_r, mensajes = ejecutar_reporte_bess()
    if "_error" in mensajes:
        print(f"ERROR: {mensajes['_error']}", file=sys.stderr)
        return 1
    if ok_r:
        for prefijo, msg in mensajes.items():
            if not prefijo.startswith("_") and msg:
                print(f"  OK {prefijo}: {msg}")
    else:
        for prefijo, msg in mensajes.items():
            if not prefijo.startswith("_") and msg:
                print(f"  FALLO {prefijo}: {msg}", file=sys.stderr)
        return 1

    print("\nCorrida completa Fase 7 finalizada.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Limpieza legacy Fase 7 + corrida opcional")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo listar archivos a borrar (predeterminado si no pasa --ejecutar)",
    )
    parser.add_argument("--ejecutar", action="store_true", help="Borrar archivos listados")
    parser.add_argument(
        "--reset-validado",
        action="store_true",
        help="Vaciar columna Validado en Medidores.csv tras limpiar",
    )
    parser.add_argument(
        "--corrida-completa",
        action="store_true",
        help="Tras limpiar: sync (o export) + verificar + filtrar + generar reportes",
    )
    parser.add_argument(
        "--sin-sync",
        action="store_true",
        help="Con --corrida-completa: exportar desde SQLite en lugar de sincronizar",
    )
    parser.add_argument("--quiet", action="store_true", help="Menos salida en sync")
    args = parser.parse_args(argv)

    if not args.ejecutar:
        args.dry_run = True

    if args.dry_run and not args.ejecutar:
        _imprimir_lista(listar_archivos_legacy())
        if args.corrida_completa:
            print("\n[dry-run] Corrida completa no se ejecuta sin --ejecutar.")
        return 0

    borrados, errores = limpiar_datos_legacy(
        ejecutar=True,
        reset_validado=args.reset_validado or args.corrida_completa,
    )
    if errores:
        for err in errores:
            print(f"ADVERTENCIA: {err}", file=sys.stderr)

    if args.corrida_completa:
        return _corrida_completa(sin_sync=args.sin_sync, quiet=args.quiet)

    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
