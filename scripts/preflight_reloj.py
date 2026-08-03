#!/usr/bin/env python3
"""Verifica zona horaria y sincronización NTP del host (preflight antes del sync).

Si detecta zona incorrecta o NTP desincronizado, intenta auto-reparar con
``sudo -n`` (sin pedir contraseña). Requiere reglas NOPASSWD (ver
``deploy/sudoers-bess-ntp.example``). Hyper-V / reloj del host Windows no
se puede corregir desde el guest: en ese caso sigue bloqueando.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ZONA_ESPERADA = "America/Mexico_City"
ROOT = Path(__file__).resolve().parents[1]
RUTA_DEFAULT = ROOT / "data" / "sync_preflight.json"
_ESPERA_NTP_SEG = 20
_POLL_NTP_SEG = 2


def _run(cmd: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _timedatectl(prop: str) -> str | None:
    try:
        proc = _run(["timedatectl", "show", f"-p{prop}", "--value"], timeout=10)
    except (FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip()


def _reloj_sincronizado() -> bool | None:
    ntp = _timedatectl("NTPSynchronized")
    if ntp is not None:
        return ntp.lower() in ("yes", "1", "true")
    try:
        proc = _run(["timedatectl", "status"], timeout=10)
    except (FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    return "System clock synchronized: yes" in (proc.stdout or "")


def _sudo_n(cmd: list[str], *, timeout: int = 60) -> tuple[bool, str]:
    """Ejecuta ``sudo -n …``; False si no hay NOPASSWD o falla el comando."""
    try:
        proc = _run(["sudo", "-n", *cmd], timeout=timeout)
    except (FileNotFoundError, OSError) as exc:
        return False, f"sudo no disponible: {exc}"
    except subprocess.TimeoutExpired:
        return False, f"timeout: sudo {' '.join(cmd)}"
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        detalle = out or f"codigo {proc.returncode}"
        if "password is required" in detalle.lower() or proc.returncode == 1:
            return False, (
                "sudo -n denegado (falta NOPASSWD). "
                "Instale deploy/sudoers-bess-ntp.example"
            )
        return False, detalle
    return True, out or "ok"


def _servicio_ntp_activo() -> str | None:
    for unidad in ("systemd-timesyncd", "chronyd", "chrony"):
        try:
            proc = _run(["systemctl", "is-active", unidad], timeout=10)
        except (FileNotFoundError, OSError):
            return None
        if (proc.stdout or "").strip() == "active":
            return unidad
    return None


def intentar_reparar_reloj() -> list[str]:
    """
    Intenta corregir zona y NTP. Devuelve lista de acciones/resultados
    (para log y JSON). No levanta excepciones.
    """
    acciones: list[str] = []

    zona = _timedatectl("Timezone")
    if zona is not None and zona != ZONA_ESPERADA:
        ok, detalle = _sudo_n(["timedatectl", "set-timezone", ZONA_ESPERADA])
        if ok:
            acciones.append(f"zona → {ZONA_ESPERADA}")
        else:
            acciones.append(f"fallo set-timezone: {detalle}")

    ntp_on = _timedatectl("NTP")
    if ntp_on is not None and ntp_on.lower() not in ("yes", "1", "true"):
        ok, detalle = _sudo_n(["timedatectl", "set-ntp", "true"])
        if ok:
            acciones.append("NTP activado (timedatectl set-ntp true)")
        else:
            acciones.append(f"fallo set-ntp: {detalle}")

    sync = _reloj_sincronizado()
    if sync is False:
        unidad = _servicio_ntp_activo()
        candidatos = []
        if unidad:
            candidatos.append(unidad)
        for u in ("systemd-timesyncd", "chronyd", "chrony"):
            if u not in candidatos:
                candidatos.append(u)
        reiniciado = False
        for u in candidatos:
            ok, detalle = _sudo_n(["systemctl", "restart", u])
            if ok:
                acciones.append(f"reiniciado {u}")
                reiniciado = True
                break
            # Unidad inexistente: seguir con la siguiente
            if "not found" in detalle.lower() or "Unit" in detalle:
                continue
            acciones.append(f"fallo restart {u}: {detalle}")
            break
        if not reiniciado and not any("reiniciado" in a for a in acciones):
            # Último intento: asegurar set-ntp
            ok, detalle = _sudo_n(["timedatectl", "set-ntp", "true"])
            if ok:
                acciones.append("NTP reafirmado tras desync")
            elif not any("set-ntp" in a for a in acciones):
                acciones.append(f"fallo set-ntp (desync): {detalle}")

        deadline = time.monotonic() + _ESPERA_NTP_SEG
        while time.monotonic() < deadline:
            if _reloj_sincronizado() is True:
                acciones.append("NTP sincronizado tras reparación")
                break
            time.sleep(_POLL_NTP_SEG)
        else:
            if _reloj_sincronizado() is not True:
                acciones.append(
                    f"NTP aún no sincronizado tras {_ESPERA_NTP_SEG}s "
                    "(posible Hyper-V Time sync del host)"
                )

    return acciones


def verificar_reloj_host() -> tuple[list[str], list[str]]:
    """
    Devuelve (bloqueantes, advertencias).

    Bloquea el cron solo con zona incorrecta o NTP explícitamente desincronizado.
    Si no se puede confirmar NTP (común en VMs Hyper-V), avisa pero no bloquea.
    """
    bloqueantes: list[str] = []
    advertencias: list[str] = []

    zona = _timedatectl("Timezone")
    if zona is None:
        advertencias.append(
            "No se pudo verificar el reloj del host (timedatectl no disponible). "
            "Confirme zona America/Mexico_City y NTP."
        )
        return bloqueantes, advertencias

    if zona != ZONA_ESPERADA:
        bloqueantes.append(
            f"Zona horaria del host: {zona} (esperada: {ZONA_ESPERADA}). "
            f"Ejecute: sudo timedatectl set-timezone {ZONA_ESPERADA}"
        )

    sync = _reloj_sincronizado()
    if sync is False:
        bloqueantes.append(
            "Reloj del host sin sincronizar (NTP). "
            "Revise: timedatectl status · Hyper-V sincronización de hora."
        )
    elif sync is None:
        advertencias.append(
            "No se pudo confirmar NTP del host (el sync automático sigue habilitado). "
            "Revise: timedatectl status"
        )

    return bloqueantes, advertencias


def escribir_estado(
    ruta: Path,
    bloqueantes: list[str],
    advertencias: list[str],
    *,
    reparaciones: list[str] | None = None,
) -> dict:
    bloquea_sync = bool(bloqueantes)
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not bloquea_sync,
        "bloquea_sync": bloquea_sync,
        "bloqueantes": bloqueantes,
        "advertencias": advertencias,
        "reparaciones": list(reparaciones or []),
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    auto_reparar = True
    if "--no-repair" in args:
        auto_reparar = False
        args.remove("--no-repair")
    ruta = Path(args[0]) if args else RUTA_DEFAULT

    bloqueantes, advertencias = verificar_reloj_host()
    reparaciones: list[str] = []

    if auto_reparar and bloqueantes:
        print("Intentando auto-reparar reloj/zona…", file=sys.stderr)
        reparaciones = intentar_reparar_reloj()
        for paso in reparaciones:
            print(f"REPARACION: {paso}", file=sys.stderr)
        bloqueantes, advertencias = verificar_reloj_host()

    escribir_estado(
        ruta, bloqueantes, advertencias, reparaciones=reparaciones
    )

    for msg in advertencias:
        print(f"ADVERTENCIA: {msg}", file=sys.stderr)
    for msg in bloqueantes:
        print(f"BLOQUEO: {msg}", file=sys.stderr)

    if bloqueantes:
        if reparaciones and any("NOPASSWD" in r or "sudo -n denegado" in r for r in reparaciones):
            print(
                "TIP: instale las reglas sudoers de deploy/sudoers-bess-ntp.example",
                file=sys.stderr,
            )
        return 1
    if advertencias:
        print("OK con advertencias: sync automatico permitido.")
    elif reparaciones:
        print("OK: reloj reparado y verificado.")
    else:
        print("OK: reloj y zona horaria del host verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
