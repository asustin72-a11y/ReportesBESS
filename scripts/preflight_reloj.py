#!/usr/bin/env python3
"""Verifica zona horaria y sincronización NTP del host (preflight antes del sync)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ZONA_ESPERADA = "America/Mexico_City"
ROOT = Path(__file__).resolve().parents[1]
RUTA_DEFAULT = ROOT / "data" / "sync_preflight.json"


def _timedatectl(prop: str) -> str | None:
    try:
        proc = subprocess.run(
            ["timedatectl", "show", f"-p{prop}", "--value"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return None
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip()


def _reloj_sincronizado() -> bool | None:
    ntp = _timedatectl("NTPSynchronized")
    if ntp is not None:
        return ntp.lower() in ("yes", "1", "true")
    try:
        proc = subprocess.run(
            ["timedatectl", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    return "System clock synchronized: yes" in (proc.stdout or "")


def verificar_reloj_host() -> list[str]:
    """Lista de advertencias; vacía si el host cumple zona y NTP."""
    advertencias: list[str] = []

    zona = _timedatectl("Timezone")
    if zona is None:
        advertencias.append(
            "No se pudo verificar el reloj del host (timedatectl no disponible). "
            "Confirme zona America/Mexico_City y NTP antes de sincronizar."
        )
        return advertencias

    if zona != ZONA_ESPERADA:
        advertencias.append(
            f"Zona horaria del host: {zona} (esperada: {ZONA_ESPERADA}). "
            f"Ejecute: sudo timedatectl set-timezone {ZONA_ESPERADA}"
        )

    sync = _reloj_sincronizado()
    if sync is False:
        advertencias.append(
            "Reloj del host sin sincronizar (NTP). "
            "Revise: timedatectl status · Hyper-V sincronización de hora."
        )
    elif sync is None:
        advertencias.append(
            "No se pudo confirmar si el reloj del host está sincronizado (NTP)."
        )

    return advertencias


def escribir_estado(ruta: Path, advertencias: list[str]) -> dict:
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not advertencias,
        "advertencias": advertencias,
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    ruta = Path(args[0]) if args else RUTA_DEFAULT
    advertencias = verificar_reloj_host()
    escribir_estado(ruta, advertencias)
    if advertencias:
        for msg in advertencias:
            print(f"ADVERTENCIA: {msg}", file=sys.stderr)
        return 1
    print("OK: reloj y zona horaria del host verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
