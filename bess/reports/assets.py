"""Recursos estáticos para reportes PDF."""

from __future__ import annotations

import base64
import os

from bess.config.paths import (
    DIRECTORIO_BASE,
    DIRECTORIO_REPORTES_DIARIOS,
    DIRECTORIO_TARIFAS,
)
from bess.core.console import log

print = log


def buscar_logo() -> str | None:
    """Busca el logo en diferentes directorios."""
    posibles_rutas = [
        os.path.join(DIRECTORIO_BASE, "Logo IUSASOL.png"),
        os.path.join(DIRECTORIO_BASE, "LogoIUSASOL.jpeg"),
        os.path.join(DIRECTORIO_BASE, "LogoIUSASOL.jpg"),
        os.path.join(DIRECTORIO_BASE, "logo.jpeg"),
        os.path.join(DIRECTORIO_BASE, "logo.jpg"),
        os.path.join(DIRECTORIO_TARIFAS, "LogoIUSASOL.jpeg"),
        os.path.join(DIRECTORIO_TARIFAS, "LogoIUSASOL.jpg"),
        os.path.join(DIRECTORIO_REPORTES_DIARIOS, "LogoIUSASOL.jpeg"),
        os.path.join(DIRECTORIO_REPORTES_DIARIOS, "LogoIUSASOL.jpg"),
        "LogoIUSASOL.jpeg",
        "LogoIUSASOL.jpg",
        "logo.jpeg",
        "logo.jpg",
    ]
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            print(f"Logo encontrado: {ruta}")
            return ruta
    print("Logo no encontrado en ninguna ruta")
    return None


def formatear_fecha_espanol(fecha_dt) -> str:
    """Formatea una fecha en español."""
    meses = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    }
    return f"{fecha_dt.day} de {meses.get(fecha_dt.month, '')} de {fecha_dt.year}"


def logo_cfe_html(width=200):
    """Logo CFE embebido en base64 para el recibo simulado."""
    candidatos = [
        os.path.join(DIRECTORIO_BASE, 'Comisión_Federal_de_Electricidad_(logo).jpg'),
        os.path.join(DIRECTORIO_BASE, 'Comision_Federal_de_Electricidad_(logo).jpg'),
    ]
    for logo_path in candidatos:
        if not os.path.exists(logo_path):
            continue
        with open(logo_path, 'rb') as logo_file:
            logo_b64 = base64.b64encode(logo_file.read()).decode()
        ext = os.path.splitext(logo_path)[1].lower()
        mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/png'
        return (
            f'<img class="cfe-logo-img" src="data:{mime};base64,{logo_b64}" '
            f'width="{width}" alt="Comisión Federal de Electricidad" />'
        )
    return ''
