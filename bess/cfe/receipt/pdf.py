
"""Exportación PDF del recibo (sin Streamlit)."""

from __future__ import annotations

import subprocess
import sys

from bess.config.constants import slug_medidor
from bess.cfe.receipt.html import render_html_recibo_documento

_CHROMIUM_LAUNCH_ARGS = (
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
)


def nombre_archivo_recibo(fecha, prefijo, con_bess):
    escenario = "ConBESS" if con_bess else "SinBESS"
    return f"Recibo_{slug_medidor(prefijo)}_{escenario}_{fecha.strftime('%Y%m%d')}.pdf"


def _ensure_playwright_chromium():
    from pathlib import Path

    browsers = Path.home() / ".cache" / "ms-playwright"
    if browsers.exists() and any(browsers.glob("chromium-*")):
        return True
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            "No se pudo instalar Chromium para Playwright."
            + (f" {detail}" if detail else "")
        )
    return True


def html_a_pdf_bytes(html_doc: str) -> bytes:
    _ensure_playwright_chromium()
    from playwright.sync_api import sync_playwright

    margin = {"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"}
    altura_util_px = 980
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=list(_CHROMIUM_LAUNCH_ARGS),
        )
        try:
            page = browser.new_page(viewport={"width": 920, "height": 1400})
            page.set_content(html_doc, wait_until="load")
            altura_recibo = page.evaluate(
                '() => document.querySelector(".cfe-recibo").getBoundingClientRect().height'
            )
            escala = min(1.0, altura_util_px / altura_recibo)
            return page.pdf(
                format="Letter",
                print_background=True,
                margin=margin,
                scale=escala,
            )
        finally:
            browser.close()


def generar_recibo_pdf_bytes(datos) -> bytes:
    html_doc = render_html_recibo_documento(datos)
    return html_a_pdf_bytes(html_doc)
