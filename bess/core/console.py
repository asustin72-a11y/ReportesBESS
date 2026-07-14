"""Salida a consola segura (Windows / Streamlit)."""

from __future__ import annotations

import builtins
import sys


def _configurar_salida_consola() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError, TypeError):
            pass


_configurar_salida_consola()


def log(*args, **kwargs) -> None:
    try:
        builtins.print(*args, **kwargs)
    except (OSError, UnicodeEncodeError):
        try:
            kwargs = dict(kwargs)
            if kwargs.get("end") not in (None, "\n"):
                kwargs.pop("end", None)
            texto = " ".join(str(a) for a in args)
            builtins.print(texto.encode("ascii", "replace").decode(), **kwargs)
        except (OSError, UnicodeEncodeError):
            pass


def imprimir_progreso(texto: str) -> None:
    if getattr(sys.stdout, "isatty", lambda: False)():
        log(texto, end="\r", flush=True)


def crear_barra(progreso: float, longitud: int) -> str:
    barra_llena = int(longitud * (progreso / 100))
    return "[" + "#" * barra_llena + " " * (longitud - barra_llena) + "]"
