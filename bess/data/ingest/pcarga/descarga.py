"""Descarga pcarga por red y convierte a CSV listo para Importar (Fecha + kWh).

En el servidor Docker, Wine/MLE viven en el host: se ejecuta pcarga por SSH
([pcarga] ssh_host / ssh_user / ssh_password) y se trae el CSV por SFTP.
"""

from __future__ import annotations

import csv
import io
import os
import platform
import shlex
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

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


def _pcarga_secrets() -> dict[str, Any]:
    try:
        import streamlit as st

        cfg = st.secrets.get("pcarga", {})
        return dict(cfg) if cfg else {}
    except Exception:
        return {}


def _cfg(clave: str, env: str = "", default: str = "") -> str:
    if env:
        val = (os.environ.get(env) or "").strip()
        if val:
            return val
    secrets = _pcarga_secrets()
    if clave in secrets and secrets[clave] not in (None, ""):
        return str(secrets[clave]).strip()
    return default


def _ruta_pcarga_configurada() -> str:
    """Ruta configurada (puede no existir dentro del contenedor)."""
    env = (os.environ.get("PCARGA_SCRIPT") or "").strip()
    if env:
        return env
    secrets = _pcarga_secrets()
    script = secrets.get("script") or secrets.get("script_dir")
    if script:
        return str(script).strip()
    return ""


def _ruta_pcarga_local() -> Path | None:
    """Solo si el archivo es visible en este filesystem."""
    conf = _ruta_pcarga_configurada()
    if conf:
        p = Path(conf).expanduser()
        if p.is_file():
            return p
        cand = p / "pcarga.py"
        if cand.is_file():
            return cand

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
    return _cfg("mle_dir", "MLE_DIR", str(Path.home() / "mle"))


def _ssh_cfg() -> dict[str, str] | None:
    """Credenciales SSH al host (Wine/MLE). None si no aplica."""
    host = _cfg("ssh_host", "PCARGA_SSH_HOST")
    user = _cfg("ssh_user", "PCARGA_SSH_USER", "bess")
    password = _cfg("ssh_password", "PCARGA_SSH_PASSWORD")
    if not host:
        # Auto en Docker: gateway típico o IP del servidor BESS
        if Path("/.dockerenv").is_file():
            # IP LAN del host (hairpin); alternativa: 172.17.0.1 (docker0)
            host = _cfg("ssh_host", "", "172.16.208.250")
        else:
            return None
    if not password:
        return None
    script = _ruta_pcarga_configurada() or "/home/bess/mle/leeperfil/pcarga.py"
    return {
        "host": host,
        "user": user,
        "password": password,
        "port": _cfg("ssh_port", "PCARGA_SSH_PORT", "22"),
        "script": script,
        "mle_dir": _mle_dir() if _mle_dir() else "/home/bess/mle",
        "python": _cfg("ssh_python", "PCARGA_SSH_PYTHON", "python3"),
    }


def _en_docker() -> bool:
    return Path("/.dockerenv").is_file()


def _fmt_rango(valor: date | datetime, *, fin: bool = False) -> str:
    if isinstance(valor, datetime):
        # Perfil a 5 min: solo hora:minuto (segundos en 00)
        return valor.replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:00")
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


def _resultado_desde_crudo(
    *,
    ep: EndpointPCarga,
    medidor_id: str,
    ke: float,
    desde_s: str,
    hasta_s: str,
    ruta_crudo: Path,
    log: str,
    crudo_nombre: str | None = None,
) -> ResultadoDescargaPCarga:
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
            ruta_crudo=crudo_nombre or ruta_crudo.name,
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
        ruta_crudo=crudo_nombre or ruta_crudo.name,
    )


def _descargar_local(
    *,
    ep: EndpointPCarga,
    medidor_id: str,
    script: Path,
    desde_s: str,
    hasta_s: str,
    ke: float,
    timeout_s: int,
) -> ResultadoDescargaPCarga:
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

        return _resultado_desde_crudo(
            ep=ep,
            medidor_id=medidor_id,
            ke=ke,
            desde_s=desde_s,
            hasta_s=hasta_s,
            ruta_crudo=crudos[-1],
            log=log,
        )


def _descargar_via_ssh(
    *,
    ep: EndpointPCarga,
    medidor_id: str,
    ssh: dict[str, str],
    desde_s: str,
    hasta_s: str,
    ke: float,
    timeout_s: int,
) -> ResultadoDescargaPCarga:
    try:
        import paramiko
    except ImportError:
        return ResultadoDescargaPCarga(
            ok=False,
            medidor_id=medidor_id,
            registros=0,
            omitidos_invalidos=0,
            ke_aplicado=ke,
            ya_escalado=ep.ya_escalado,
            csv_bytes=b"",
            nombre_archivo="",
            log=(
                "PCarga en Docker requiere paramiko para SSH al host. "
                "Instale paramiko o ejecute Streamlit en el host."
            ),
        )

    remote_out = f"/tmp/bess_pcarga_{uuid.uuid4().hex[:10]}"
    script = ssh["script"]
    mle = ssh["mle_dir"]
    py = ssh["python"]
    # shell-safe
    cmd = (
        f"mkdir -p {shlex.quote(remote_out)} && "
        f"{shlex.quote(py)} {shlex.quote(script)} --red --wine "
        f"--mle-dir {shlex.quote(mle)} "
        f"--ip {shlex.quote(ep.ip)} --puerto {int(ep.puerto)} "
        f"-desde {shlex.quote(desde_s)} -hasta {shlex.quote(hasta_s)} "
        f"-d {shlex.quote(remote_out)}; echo PCARGA_EC=$?; "
        f"ls -1 {shlex.quote(remote_out)}/*_pcarga_*.csv 2>/dev/null | tail -1"
    )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            ssh["host"],
            port=int(ssh["port"] or 22),
            username=ssh["user"],
            password=ssh["password"],
            timeout=30,
            allow_agent=False,
            look_for_keys=False,
        )
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
            log=f"SSH al host pcarga ({ssh['user']}@{ssh['host']}) falló: {exc}",
        )

    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout_s)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        log = out + (("\n" + err) if err.strip() else "")
        # última línea no vacía que parezca ruta csv
        remote_csv = ""
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.endswith(".csv") and "_pcarga_" in line:
                remote_csv = line
                break
        if not remote_csv:
            client.exec_command(f"rm -rf {shlex.quote(remote_out)}")
            return ResultadoDescargaPCarga(
                ok=False,
                medidor_id=medidor_id,
                registros=0,
                omitidos_invalidos=0,
                ke_aplicado=ke,
                ya_escalado=ep.ya_escalado,
                csv_bytes=b"",
                nombre_archivo="",
                log=log.strip() or "pcarga vía SSH no produjo CSV.",
            )

        with tempfile.TemporaryDirectory(prefix="bess_pcarga_ssh_") as tmp:
            local_csv = Path(tmp) / Path(remote_csv).name
            sftp = client.open_sftp()
            try:
                sftp.get(remote_csv, str(local_csv))
            finally:
                sftp.close()
            client.exec_command(f"rm -rf {shlex.quote(remote_out)}")
            return _resultado_desde_crudo(
                ep=ep,
                medidor_id=medidor_id,
                ke=ke,
                desde_s=desde_s,
                hasta_s=hasta_s,
                ruta_crudo=local_csv,
                log=f"[ssh {ssh['user']}@{ssh['host']}]\n{log}",
                crudo_nombre=Path(remote_csv).name,
            )
    except Exception as exc:
        try:
            client.exec_command(f"rm -rf {shlex.quote(remote_out)}")
        except Exception:
            pass
        return ResultadoDescargaPCarga(
            ok=False,
            medidor_id=medidor_id,
            registros=0,
            omitidos_invalidos=0,
            ke_aplicado=ke,
            ya_escalado=ep.ya_escalado,
            csv_bytes=b"",
            nombre_archivo="",
            log=f"Error ejecutando pcarga por SSH: {exc}",
        )
    finally:
        client.close()


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

    desde_s = _fmt_rango(desde, fin=False)
    hasta_s = _fmt_rango(hasta, fin=True)
    ke = ep.ke_efectivo

    script_local = _ruta_pcarga_local()
    ssh = _ssh_cfg()
    # En Docker preferir SSH al host (Wine); local Windows/Linux usa script local.
    if script_local is not None and not (_en_docker() and ssh is not None):
        return _descargar_local(
            ep=ep,
            medidor_id=medidor_id,
            script=script_local,
            desde_s=desde_s,
            hasta_s=hasta_s,
            ke=ke,
            timeout_s=timeout_s,
        )

    if ssh is not None:
        return _descargar_via_ssh(
            ep=ep,
            medidor_id=medidor_id,
            ssh=ssh,
            desde_s=desde_s,
            hasta_s=hasta_s,
            ke=ke,
            timeout_s=timeout_s,
        )

    conf = _ruta_pcarga_configurada()
    hint = ""
    if conf:
        hint = f" Ruta configurada no visible aquí: {conf}."
    if _en_docker():
        hint += (
            " En Docker configure [pcarga] ssh_host / ssh_user / ssh_password "
            "para ejecutar Wine/MLE en el host."
        )
    return ResultadoDescargaPCarga(
        ok=False,
        medidor_id=medidor_id,
        registros=0,
        omitidos_invalidos=0,
        ke_aplicado=ke,
        ya_escalado=ep.ya_escalado,
        csv_bytes=b"",
        nombre_archivo="",
        log=(
            "No se encontró pcarga.py."
            + hint
            + " Configure secrets [pcarga] script o variable PCARGA_SCRIPT."
        ),
    )


def _serie_desde_nombre(nombre: str) -> str:
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
