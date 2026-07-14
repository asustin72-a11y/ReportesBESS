import csv, sqlite3
from pathlib import Path
ROOT=Path(r'C:\Proyectos_IUSASOL\BESS')
BD=ROOT/'data'/'bess_perfiles.db'
OUT=ROOT/'data'/'tmp_compare_result.txt'
DESDE='2026-06-01 00:05:00'; HASTA='2026-06-30 15:25:00'
COLS=['kwh_rec','kwh_ent','kvarh_q1','kvarh_q2','kvarh_q3','kvarh_q4']; TOL=1e-4
lines=[]

def load_csv(p):
    d={}
    with open(p, newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            fecha=(row.get('Fecha') or row.get('fecha') or '').strip()
            if not fecha or fecha<DESDE or fecha>HASTA: continue
            d[fecha]={c: float(row.get(c.upper(), row.get(c,0)) or 0) for c in COLS}
    return d

def load_bd():
    d={}
    with sqlite3.connect(BD) as conn:
        for row in conn.execute('select fecha,kwh_rec,kwh_ent,kvarh_q1,kvarh_q2,kvarh_q3,kvarh_q4,fuente from perfil_carga where medidor_id=? and fecha>=? and fecha<=?',('ION_IUSA2',DESDE,HASTA)):
            d[row[0]]={COLS[i]:row[i+1] for i in range(6)}; d[row[0]]['fuente']=row[7]
    return d

def report(a,b,na,nb):
    ka,kb=set(a),set(b)
    mism=[]
    for k in sorted(ka&kb):
        for c in COLS:
            if abs(a[k][c]-b[k][c])>TOL:
                mism.append((k,c,a[k][c],b[k][c])); break
    lines.append(f'=== {na} vs {nb} ===')
    lines.append(f'  {na}: {len(a)} | {nb}: {len(b)} | solo {na}: {len(ka-kb)} | solo {nb}: {len(kb-ka)} | dif valores: {len(mism)}')
    for x in mism[:8]: lines.append(f'    {x}')

bd=load_bd(); fu=load_csv(ROOT/'data'/'ArchivosFuente'/'ION_IUSA2.csv'); pr=load_csv(ROOT/'data'/'ArchivosProcesados'/'ION_IUSA2.csv')
lines.append(f'Rango {DESDE} -> {HASTA}')
report(bd,fu,'BD','ArchivosFuente')
report(bd,pr,'BD','ArchivosProcesados')
with sqlite3.connect(BD) as conn:
    tot=conn.execute("select count(*), min(fecha), max(fecha) from perfil_carga where medidor_id='ION_IUSA2'").fetchone()
    fc=conn.execute("select fuente, count(*) from perfil_carga where medidor_id='ION_IUSA2' group by fuente").fetchall()
lines.append(f'Total BD ION_IUSA2: {tot}')
lines.append(f'Fuentes BD: {dict(fc)}')
OUT.write_text('\n'.join(lines), encoding='utf-8')
