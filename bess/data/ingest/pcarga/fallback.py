"""Fallback pcarga IUSA 1/2 cuando la API ISOL está caída.

Orquesta: descarga Ethernet → import CSV (fuente=csv) → Rebuild CSV.
No incluye Aragón ni granja. Solo lectura pcarga (sin mset).
"""

from __future__ import annotations

import contextlib
import io
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bess.config.paths import RUTA_BD_PERFILES
from bess.config.pcarga_endpoints import lista_medidores_fallback_iusa12
from bess.data.ingest.ion import db
from bess.data.ingest.ion.modbus import ZONA_HORARIA_DEFAULT


@dataclass
class ResultadoFallbackMedidor:
    medidor_id: str
    ok: bool
    registros: int = 0
    log: str = ""
    desde: str = ""
    hasta: str = ""
    etapa: str = ""  # descarga | import | rebuild | —


@dataclass
class ResultadoFallbackLote:
    ok: bool
    medidores: list[ResultadoFallbackMedidor] = field(default_factory=list)
    log: str = ""

    @property
    def exitosos(self) -> int:
        return sum(1 for m in self.medidores if m.ok)

    @property
    def fallidos(self) -> int:
        return sum(1 for m in self.medidores if not m.ok)


def _alinear_5min(dt: datetime) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    return dt.replace(minute=(dt.minute // 5) * 5)


def ahora_fin_pcarga() -> datetime:
    return _alinear_5min(datetime.now())


def desde_cursor_medidor(medidor_id: str, *, hasta: datetime | None = None) -> datetime:
    """Inicio por defecto: última fecha en BD (+5 min) o 24 h atrás."""
    fin = hasta or ahora_fin_pcarga()
    zona = ZoneInfo(ZONA_HORARIA_DEFAULT)
    if not RUTA_BD_PERFILES.is_file():
        return fin - timedelta(hours=24)
    with db.conectar_bd(RUTA_BD_PERFILES) as conn:
        ultima = db.get_ultima_fecha(conn, medidor_id, zona)
    if ultima is None:
        return fin - timedelta(hours=24)
    inicio = ultima + timedelta(minutes=5)
    if inicio >= fin:
        # Solape corto para revalidar el último intervalo
        return _alinear_5min(fin - timedelta(hours=3))
    return _alinear_5min(inicio)


def _importar_bytes(csv_bytes: bytes, medidor_id: str, nombre: str) -> tuple[int, str]:
    from bess.data.ingest.ion.import_csv import importar_csv

    suffix = Path(nombre).suffix or ".csv"
    with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as tmp:
        tmp.write(csv_bytes)
        ruta_tmp = Path(tmp.name)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            codigo = importar_csv(
                ruta_tmp,
                RUTA_BD_PERFILES,
                medidor_id,
                solo_faltantes=False,
            )
        return codigo, buf.getvalue()
    finally:
        ruta_tmp.unlink(missing_ok=True)


def ejecutar_fallback_medidor(
    medidor_id: str,
    *,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    rebuild: bool = True,
    procesar: bool = False,
) -> ResultadoFallbackMedidor:
    """Descarga + import (+ rebuild) de un medidor del lote IUSA 1/2."""
    from bess.data.ingest.pcarga.descarga import descargar_pcarga_medidor

    fin = hasta or ahora_fin_pcarga()
    ini = desde or desde_cursor_medidor(medidor_id, hasta=fin)
    logs: list[str] = []

    if ini > fin:
        return ResultadoFallbackMedidor(
            medidor_id=medidor_id,
            ok=False,
            desde=ini.strftime("%Y-%m-%d %H:%M"),
            hasta=fin.strftime("%Y-%m-%d %H:%M"),
            log="Desde no puede ser posterior a Hasta.",
            etapa="—",
        )

    res = descargar_pcarga_medidor(medidor_id, ini, fin)
    logs.append(res.log or "")
    if not res.ok:
        return ResultadoFallbackMedidor(
            medidor_id=medidor_id,
            ok=False,
            registros=0,
            log="\n".join(x for x in logs if x).strip() or "Descarga pcarga falló.",
            desde=ini.strftime("%Y-%m-%d %H:%M"),
            hasta=fin.strftime("%Y-%m-%d %H:%M"),
            etapa="descarga",
        )

    codigo, log_imp = _importar_bytes(res.csv_bytes, medidor_id, res.nombre_archivo)
    if log_imp.strip():
        logs.append(log_imp.strip())
    if codigo != 0:
        return ResultadoFallbackMedidor(
            medidor_id=medidor_id,
            ok=False,
            registros=res.registros,
            log="\n".join(x for x in logs if x).strip() or f"Import falló (código {codigo}).",
            desde=ini.strftime("%Y-%m-%d %H:%M"),
            hasta=fin.strftime("%Y-%m-%d %H:%M"),
            etapa="import",
        )

    if rebuild:
        from bess.data.csv_rebuild import ejecutar_rebuild_csv

        rb = ejecutar_rebuild_csv(medidor_id, ini.date(), procesar=procesar)
        logs.append(rb.get("log") or rb.get("mensaje") or str(rb))
        if not rb.get("ok", False):
            return ResultadoFallbackMedidor(
                medidor_id=medidor_id,
                ok=False,
                registros=res.registros,
                log="\n".join(x for x in logs if x).strip() or "Rebuild CSV falló.",
                desde=ini.strftime("%Y-%m-%d %H:%M"),
                hasta=fin.strftime("%Y-%m-%d %H:%M"),
                etapa="rebuild",
            )

    return ResultadoFallbackMedidor(
        medidor_id=medidor_id,
        ok=True,
        registros=res.registros,
        log="\n".join(x for x in logs if x).strip(),
        desde=ini.strftime("%Y-%m-%d %H:%M"),
        hasta=fin.strftime("%Y-%m-%d %H:%M"),
        etapa="rebuild" if rebuild else "import",
    )


def ejecutar_fallback_pcarga_iusa12(
    *,
    desde: datetime | date | None = None,
    hasta: datetime | date | None = None,
    medidores: list[str] | None = None,
    rebuild: bool = True,
    procesar: bool = False,
) -> ResultadoFallbackLote:
    """Ejecuta el lote IUSA 1/2. Fallos parciales no abortan el resto."""
    ids = medidores or lista_medidores_fallback_iusa12()
    fin: datetime | None
    ini_fijo: datetime | None
    if hasta is None:
        fin = None
    elif isinstance(hasta, datetime):
        fin = _alinear_5min(hasta)
    else:
        fin = datetime.combine(hasta, datetime.min.time()).replace(
            hour=23, minute=55, second=0, microsecond=0
        )

    if desde is None:
        ini_fijo = None
    elif isinstance(desde, datetime):
        ini_fijo = _alinear_5min(desde)
    else:
        ini_fijo = datetime.combine(desde, datetime.min.time()).replace(
            hour=0, minute=5, second=0, microsecond=0
        )

    resultados: list[ResultadoFallbackMedidor] = []
    for mid in ids:
        resultados.append(
            ejecutar_fallback_medidor(
                mid,
                desde=ini_fijo,
                hasta=fin,
                rebuild=rebuild,
                procesar=procesar,
            )
        )

    ok = all(r.ok for r in resultados) if resultados else False
    lineas = [
        f"{'OK' if r.ok else 'FAIL'} {r.medidor_id}: "
        f"{r.registros} reg · {r.desde} → {r.hasta}"
        + (f" ({r.etapa})" if not r.ok else "")
        for r in resultados
    ]
    return ResultadoFallbackLote(
        ok=ok,
        medidores=resultados,
        log="\n".join(lineas),
    )
