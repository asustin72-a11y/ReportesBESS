"""Importa MEGA_total_20.csv (suma granja) → SQLite GRANJA_IUSA2."""

from __future__ import annotations

import csv
from pathlib import Path

from bess.config.paths import DIRECTORIO_BASE
from bess.data.ingest.granja.consolidar import totales_a_registros_bess
from bess.data.ingest.ion import db

LOTE = 500
RUTA_MEGA_TOTAL_DEFAULT = DIRECTORIO_BASE / "perfiles_granja" / "MEGA_total_20.csv"


def _leer_totales(ruta_csv: Path) -> dict[str, float]:
    totales: dict[str, float] = {}
    with ruta_csv.open(encoding="utf-8-sig", newline="") as archivo:
        reader = csv.DictReader(archivo)
        if not reader.fieldnames:
            raise ValueError("CSV vacío")

        campo_fecha = "Fecha_Hora" if "Fecha_Hora" in reader.fieldnames else "Fecha"
        campo_kw = "kW_total" if "kW_total" in reader.fieldnames else "KWH_REC"
        if campo_fecha not in reader.fieldnames:
            raise ValueError(f"Columna de fecha no encontrada en {ruta_csv.name}")
        if campo_kw not in reader.fieldnames:
            raise ValueError(f"Columna de potencia no encontrada en {ruta_csv.name}")

        for fila in reader:
            fecha = (fila.get(campo_fecha) or "").strip()
            if not fecha:
                continue
            totales[fecha] = float(fila.get(campo_kw) or 0)

    return totales


def importar_mega_total(
    ruta_csv: Path,
    ruta_bd: Path,
    medidor_id: str = db.MEDIDOR_GRANJA_IUSA2,
    solo_faltantes: bool = False,
) -> int:
    if not ruta_csv.exists():
        print(f"ERROR: no existe {ruta_csv}")
        return 1

    db.init_db(ruta_bd)
    print(f"Leyendo {ruta_csv} ...")

    totales = _leer_totales(ruta_csv)
    registros = totales_a_registros_bess(totales)
    print(f"Filas leídas en CSV: {len(registros)}")

    if solo_faltantes:
        with db.conectar_bd(ruta_bd) as conn:
            existentes = {
                row["fecha"]
                for row in conn.execute(
                    "SELECT fecha FROM perfil_carga WHERE medidor_id = ?",
                    (medidor_id,),
                )
            }
        antes = len(registros)
        registros = [r for r in registros if r["fecha"] not in existentes]
        print(
            f"Solo faltantes en BD: {len(registros)} "
            f"(omitidos ya presentes: {antes - len(registros)})"
        )
        if not registros:
            print("BD ya contiene todos los timestamps del CSV.")
            return 0

    insertados = 0
    actualizados = 0
    for i in range(0, len(registros), LOTE):
        lote = registros[i : i + LOTE]
        with db.conectar_bd(ruta_bd) as conn:
            resultado = db.upsert_registros(conn, medidor_id, lote, fuente="csv")
            insertados += resultado.insertados
            actualizados += resultado.actualizados
            conn.commit()
        print(f"  Guardados {min(i + LOTE, len(registros))}/{len(registros)}...")

    with db.conectar_bd(ruta_bd) as conn:
        if registros:
            db.actualizar_sync_state(conn, medidor_id, registros[-1]["fecha"])
        conn.commit()
        total_bd = db.contar_registros(conn, medidor_id)

    print(
        f"Medidor: {medidor_id} | Nuevos: {insertados} | "
        f"Actualizados: {actualizados} | Total BD: {total_bd}"
    )
    return 0
