"""Barra de progreso Streamlit para subprocess del pipeline."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable, Sequence

import streamlit as st

from bess.core.ui_progress import parse_ui_progress


class BarraProgreso:
    """Barra + leyenda actualizable."""

    def __init__(self, titulo: str):
        self._titulo = titulo
        self._bar = st.progress(0.0, text=titulo)
        self._caption = st.empty()

    def actualizar(self, fraccion: float, mensaje: str = "") -> None:
        pct = max(0.0, min(float(fraccion), 1.0))
        texto = mensaje or self._titulo
        self._bar.progress(pct, text=texto)
        if mensaje:
            self._caption.caption(mensaje)

    def paso(self, step: int, total: int, mensaje: str) -> None:
        total = max(total, 1)
        fraccion = min(step / total, 1.0)
        self.actualizar(fraccion, mensaje)

    def completar(self, mensaje: str = "Completado") -> None:
        self._bar.progress(1.0, text=mensaje)
        self._caption.empty()


def _leer_stream(
    stream,
    destino: list[str],
    on_line: Callable[[str], None] | None,
) -> None:
    if stream is None:
        return
    for line in stream:
        destino.append(line)
        if on_line:
            on_line(line)


def parse_reporte_subprocess(stdout: str, stderr: str, returncode: int) -> tuple[bool, dict]:
    """Interpreta la salida de scripts/run_reporte_bess.py."""
    import json

    marker = "__BESS_REPORTE_JSON__"
    if marker not in stdout:
        err = (stderr or "").strip() or stdout.strip()
        if not err:
            err = f"El proceso terminó con código {returncode}"
        return False, {"_error": err}

    payload = json.loads(stdout.split(marker, 1)[1].strip())
    mensajes = dict(payload.get("mensajes") or {})
    if payload.get("traceback"):
        mensajes["_traceback"] = payload["traceback"]
    if not payload.get("ok") and "_error" not in mensajes:
        mensajes["_error"] = "Error al generar reportes"
    return bool(payload.get("ok")), mensajes


def ejecutar_subprocess_con_progreso(
    cmd: Sequence[str],
    *,
    cwd: str,
    timeout: int,
    titulo: str,
    env: dict[str, str] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> tuple[int, str, str]:
    """
    Ejecuta un comando capturando stdout/stderr.
    Las líneas BESS_UI_PROGRESS en stderr actualizan la barra.
    """
    barra = BarraProgreso(titulo)
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _on_stderr(line: str) -> None:
        parsed = parse_ui_progress(line)
        if parsed:
            step, total, label = parsed
            barra.paso(step, total, label)
            if on_progress:
                on_progress(step, total, label)

    proc = subprocess.Popen(
        list(cmd),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    t_out = threading.Thread(
        target=_leer_stream,
        args=(proc.stdout, stdout_lines, None),
        daemon=True,
    )
    t_err = threading.Thread(
        target=_leer_stream,
        args=(proc.stderr, stderr_lines, _on_stderr),
        daemon=True,
    )
    t_out.start()
    t_err.start()
    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        barra.actualizar(1.0, "Tiempo agotado")
        raise
    finally:
        t_out.join(timeout=2)
        t_err.join(timeout=2)

    if rc == 0:
        barra.completar()
    else:
        barra.actualizar(1.0, "Finalizado con errores")

    return rc, "".join(stdout_lines), "".join(stderr_lines)
