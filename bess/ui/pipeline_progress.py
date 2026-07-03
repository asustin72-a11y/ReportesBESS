"""Barra de progreso Streamlit para subprocess del pipeline."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable, Sequence

import streamlit as st

from bess.core.ui_progress import parse_ui_progress


class BarraProgreso:
    """Barra + leyenda actualizable (solo desde el hilo principal de Streamlit)."""

    def __init__(self, titulo: str):
        self._titulo = titulo
        try:
            self._bar = st.progress(0.0, text=titulo)
        except TypeError:
            self._bar = st.progress(0.0)
        self._caption = st.empty()

    def actualizar(self, fraccion: float, mensaje: str = "") -> None:
        pct = max(0.0, min(float(fraccion), 1.0))
        texto = mensaje or self._titulo
        try:
            self._bar.progress(pct, text=texto)
        except TypeError:
            self._bar.progress(pct)
            self._caption.caption(texto)
            return
        if mensaje:
            self._caption.caption(mensaje)

    def paso(self, step: int, total: int, mensaje: str) -> None:
        total = max(total, 1)
        fraccion = min(step / total, 1.0)
        self.actualizar(fraccion, mensaje)

    def completar(self, mensaje: str = "Completado") -> None:
        try:
            self._bar.progress(1.0, text=mensaje)
        except TypeError:
            self._bar.progress(1.0)
        self._caption.empty()


def _leer_stream(stream, destino: list[str]) -> None:
    if stream is None:
        return
    for line in stream:
        destino.append(line)


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

    def _on_stderr_line(line: str) -> None:
        parsed = parse_ui_progress(line)
        if parsed:
            step, total, label = parsed
            barra.paso(step, total, label)
            if on_progress:
                on_progress(step, total, label)

    run_env = {**os.environ, **(env or {}), "PYTHONUNBUFFERED": "1"}

    proc = subprocess.Popen(
        list(cmd),
        cwd=cwd,
        env=run_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    t_out = threading.Thread(
        target=_leer_stream,
        args=(proc.stdout, stdout_lines),
        daemon=True,
    )
    t_out.start()

    deadline = time.monotonic() + timeout
    try:
        while proc.poll() is None:
            if time.monotonic() > deadline:
                proc.kill()
                proc.wait()
                barra.actualizar(1.0, "Tiempo agotado")
                raise subprocess.TimeoutExpired(list(cmd), timeout)

            line = proc.stderr.readline() if proc.stderr else ""
            if line:
                stderr_lines.append(line)
                _on_stderr_line(line)
            else:
                time.sleep(0.05)

        if proc.stderr:
            for line in proc.stderr:
                stderr_lines.append(line)
                _on_stderr_line(line)

        rc = proc.returncode if proc.returncode is not None else 1
    finally:
        t_out.join(timeout=5)

    if rc == 0:
        barra.completar()
    else:
        barra.actualizar(1.0, "Finalizado con errores")

    return rc, "".join(stdout_lines), "".join(stderr_lines)
