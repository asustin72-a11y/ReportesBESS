import csv
import sqlite3
from pathlib import Path

from bess.config.paths import RUTA_BD_PERFILES

csv_path = Path(r"C:\Proyectos_IUSASOL\Descarga_ION\172_16_205_203_20260629_131014.csv")
casos = []
with csv_path.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        rec = float(row["KWH_REC"] or 0)
        ent = float(row["KWH_ENT"] or 0)
        if rec == 0 and ent > 0:
            casos.append((row["Fecha"], rec, ent))
            if len(casos) >= 5:
                break

with sqlite3.connect(RUTA_BD_PERFILES) as conn:
    print("Verificacion REC=0 ENT>0 (respaldo vs BD):")
    ok_all = True
    for fecha, rec, ent in casos:
        bd = conn.execute(
            "SELECT kwh_rec, kwh_ent FROM perfil_carga WHERE medidor_id=? AND fecha=?",
            ("ION_IUSA2", fecha),
        ).fetchone()
        ok = bd and abs(bd[0] - rec) < 1e-6 and abs(bd[1] - ent) < 1e-6
        ok_all = ok_all and ok
        print(f"  {fecha}  CSV({rec},{ent})  BD({bd[0]},{bd[1]})  {'OK' if ok else 'MAL'}")

    tot = conn.execute(
        "SELECT COUNT(*), MIN(fecha), MAX(fecha) FROM perfil_carga WHERE medidor_id=?",
        ("ION_IUSA2",),
    ).fetchone()
    swap = conn.execute(
        "SELECT COUNT(*) FROM perfil_carga WHERE medidor_id=? AND kwh_rec=0 AND kwh_ent>0",
        ("ION_IUSA2",),
    ).fetchone()[0]
    print(f"Total BD: {tot[0]}  rango {tot[1]} -> {tot[2]}")
    print(f"Registros con REC=0 y ENT>0 en BD: {swap}")
