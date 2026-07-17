"""Descarga pcarga por red y convierte a CSV listo para Importar (Fecha + kWh)."""

from __future__ import annotations

import csv
import io
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bess.config.pcarga_endpoints import EndpointPCarga, endpoint_pcarga


@dataclass(frozen=True)
class ResultadoDescargaPCarga:
    ok: bool
    medidor_id: str
    registros: int
    omitidos_invalidos: int
    ke_aplicado: float
    ya_escalado: bool
    csv_bytes: bytes
    nombre_archivo: str
    log: str
    serie_leida: str = ""
    ruta_crudo: str = ""


def _ruta_pcarga_py() -> Path | None:
    env = (os.environ.get("PCARGA_SCRIPT") or "").strip()
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None

    try:
        import streamlit as st

        cfg = st.secrets.get("pcarga", {})
        script = cfg.get("script") or cfg.get("script_dir")
        if script:
            p = Path(str(script)).expanduser()
            if p.is_file():
                return p
            cand = p / "pcarga.py"
            if cand.is_file():
                return cand
    except Exception:
        pass

    candidatos = [
        Path.home() / "mle" / "leeperfil" / "pcarga.py",
        Path.home() / "Lee_Medidor_IUSA" / "pcarga.py",
        Path(r"C:\Proyectos_Python\Lee_Medidor_IUSA\pcarga.py"),
    ]
    for c in candidatos:
        if c.is_file():
            return c
    return None


def _mle_dir() -> str:
    env = (os.environ.get("MLE_DIR") or "").strip()
    if env:
        return str(Path(env).expanduser())
    try:
        import streamlit as st

        cfg = st.secrets.get("pcarga", {})
        if cfg.get("mle_dir"):
            return str(Path(str(cfg["mle_dir"])).expanduser())
    except Exception:
        pass
    return str(Path.home() / "mle")


def _fmt_rango(valor: date | datetime, *, fin: bool = False) -> str:
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    return f"{valor.isoformat()} {'23:55:00' if fin else '00:00:00'}"


def wh_a_kwh(raw: float, ke: float) -> float:
    """pcarga en Wh (o Wh ya escalados) → kWh de importación BESS."""
    return (float(raw) * float(ke)) / 1000.0


def convertir_pcarga_a_import(
    ruta_o_texto: Path | str | io.StringIO,
    *,
    ke: float,
    solo_validos: bool = True,
) -> tuple[str, int, int]:
    """
    Convierte CSV crudo pcarga → CSV Importar (Fecha, KWH_*, KVARH_*).

    Returns:
        (csv_text, n_filas, n_omitidos_invalidos)
    """
    if isinstance(ruta_o_texto, Path):
        texto = ruta_o_texto.read_text(encoding="utf-8", errors="replace")
    elif isinstance(ruta_o_texto, io.StringIO):
        texto = ruta_o_texto.getvalue()
    else:
        texto = str(ruta_o_texto)

    reader = csv.DictReader(io.StringIO(texto))
    if not reader.fieldnames:
        raise ValueError("CSV pcarga sin encabezados")

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["Fecha", "KWH_REC", "KWH_ENT", "KVARH_Q1", "KVARH_Q2", "KVARH_Q3", "KVARH_Q4"]
    )
    n = 0
    omitidos = 0
    for fila in reader:
        keys = {k.lower().strip(): (v or "").strip() for k, v in fila.items() if k}
        if solo_validos and keys.get("valido", "1") not in ("1", "true", "True"):
            omitidos += 1
            continue
        fecha = keys.get("fecha", "")
        hora = keys.get("hora", "")
        if not fecha:
            omitidos += 1
            continue
        stamp = fecha if not hora else f"{fecha} {hora}"
        if len(stamp) == 16:
            stamp = f"{stamp}:00"
        writer.writerow(
            [
                stamp,
                f"{wh_a_kwh(_leer_num(keys, 'kwh_rec'), ke):.6f}",
                f"{wh_a_kwh(_leer_num(keys, 'kwh_ent'), ke):.6f}",
                f"{wh_a_kwh(_leer_num(keys, 'kvarh_q1'), ke):.6f}",
                f"{wh_a_kwh(_leer_num(keys, 'kvarh_q2'), ke):.6f}",
                f"{wh_a_kwh(_leer_num(keys, 'kvarh_q3'), ke):.6f}",
                f"{wh_a_kwh(_leer_num(keys, 'kvarh_q4'), ke):.6f}",
            ]
        )
        n += 1
    return out.getvalue(), n, omitidos


def _leer_num(keys: dict[str, str], nombre: str) -> float:
    raw = keys.get(nombre, "0") or "0"
    try:
        return float(raw)
    except ValueError:
        return 0.0


def descargar_pcarga_medidor(
    medidor_id: str,
    desde: date | datetime,
    hasta: date | datetime,
    *,
    timeout_s: int = 600,
) -> ResultadoDescargaPCarga:
    """Ejecuta pcarga.py --red y devuelve CSV listo para Importar (sin escribir BD)."""
    ep = endpoint_pcarga(medidor_id)
    if ep is None:
        return ResultadoDescargaPCarga(
            ok=False,
            medidor_id=medidor_id,
            registros=0,
            omitidos_invalidos=0,
            ke_aplicado=1.0,
            ya_escalado=False,
            csv_bytes=b"",
            nombre_archivo="",
            log=f"Medidor {medidor_id!r} no tiene endpoint pcarga configurado.",
        )

    script = _ruta_pcarga_py()
    if script is None:
        return ResultadoDescargaPCarga(
            ok=False,
            medidor_id=medidor_id,
            registros=0,
            omitidos_invalidos=0,
            ke_aplicado=ep.ke_efectivo,
            ya_escalado=ep.ya_escalado,
            csv_bytes=b"",
            nombre_archivo="",
            log=(
                "No se encontró pcarga.py. Configure secrets [pcarga] script "
                "o variable PCARGA_SCRIPT."
            ),
        )

    desde_s = _fmt_rango(desde, fin=False)
    hasta_s = _fmt_rango(hasta, fin=True)
    ke = ep.ke_efectivo

    with tempfile.TemporaryDirectory(prefix="bess_pcarga_") as tmp:
        outdir = Path(tmp)
        cmd = [
            sys.executable,
            str(script),
            "--red",
            "--ip",
            ep.ip,
            "--puerto",
            str(ep.puerto),
            "-desde",
            desde_s,
            "-hasta",
            hasta_s,
            "-d",
            str(outdir),
        ]
        if platform.system() == "Linux":
            cmd.extend(["--wine", "--mle-dir", _mle_dir()])

        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(script.parent),
                env=env,
            )
        except subprocess.TimeoutExpired:
            return ResultadoDescargaPCarga(
                ok=False,
                medidor_id=medidor_id,
                registros=0,
                omitidos_invalidos=0,
                ke_aplicado=ke,
                ya_escalado=ep.ya_escalado,
                csv_bytes=b"",
                nombre_archivo="",
                log=f"Timeout ({timeout_s}s) ejecutando pcarga.",
            )

        log = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        crudos = sorted(outdir.glob("*_pcarga_*.csv"))
        if proc.returncode != 0 or not crudos:
            return ResultadoDescargaPCarga(
                ok=False,
                medidor_id=medidor_id,
                registros=0,
                omitidos_invalidos=0,
                ke_aplicado=ke,
                ya_escalado=ep.ya_escalado,
                csv_bytes=b"",
                nombre_archivo="",
                log=log.strip() or f"pcarga falló (código {proc.returncode}).",
            )

        ruta_crudo = crudos[-1]
        try:
            csv_txt, n, omitidos = convertir_pcarga_a_import(ruta_crudo, ke=ke)
        except Exception as exc:
            return ResultadoDescargaPCarga(
                ok=False,
                medidor_id=medidor_id,
                registros=0,
                omitidos_invalidos=0,
                ke_aplicado=ke,
                ya_escalado=ep.ya_escalado,
                csv_bytes=b"",
                nombre_archivo="",
                log=f"{log}\nError convirtiendo CSV: {exc}",
                ruta_crudo=str(ruta_crudo),
            )

        serie = _serie_desde_nombre(ruta_crudo.name) or ep.serie
        if ep.serie and serie and ep.serie not in serie:
            log += (
                f"\nAviso: serie leída {serie!r} no coincide con "
                f"configurada {ep.serie!r}."
            )

        d0 = desde_s[:10].replace("-", "")
        d1 = hasta_s[:10].replace("-", "")
        nombre = f"{medidor_id}_pcarga_{d0}_{d1}.csv"
        return ResultadoDescargaPCarga(
            ok=True,
            medidor_id=medidor_id,
            registros=n,
            omitidos_invalidos=omitidos,
            ke_aplicado=ke,
            ya_escalado=ep.ya_escalado,
            csv_bytes=csv_txt.encode("utf-8"),
            nombre_archivo=nombre,
            log=log.strip(),
            serie_leida=serie,
            ruta_crudo=ruta_crudo.name,
        )


def _serie_desde_nombre(nombre: str) -> str:
    # 00000000CS3190VL2E19NB_pcarga_local.csv o similar
    base = Path(nombre).name
    if "_pcarga_" in base:
        return base.split("_pcarga_", 1)[0]
    return ""


def etiqueta_endpoint(ep: EndpointPCarga) -> str:
    ke_txt = "ya escalado" if ep.ya_escalado else f"Ke×{ep.ke:g}"
    return (
        f"{ep.etiqueta or ep.medidor_id} · {ep.serie} · "
        f"{ep.ip}:{ep.puerto} · {ke_txt}"
    )
