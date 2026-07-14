"""
Genera GUIA_ADMINISTRADOR.pdf (pipeline, sidebar, catálogo v5.8).

Uso:
  python docs/generar_guia_admin_pdf.py
  BESS_SKIP_CAPTURE=1 python docs/generar_guia_admin_pdf.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Spacer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bess import __version__ as VERSION
from docs.pdf_shared import (
    build_pdf,
    cover_page,
    img_block,
    p,
    section,
    table,
    toc_box,
)

DOCS = ROOT / "docs"
CAPTURAS = DOCS / "capturas"
PDF_OUT = DOCS / "GUIA_ADMINISTRADOR.pdf"
LOGO = ROOT / "data" / "Logo IUSASOL.png"
APP_URL = os.environ.get("BESS_APP_URL", "http://localhost:8501")


def _wait(page, ms=2500):
    page.wait_for_timeout(ms)


def capturar_sidebar_admin():
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        _wait(page, 3000)
        try:
            page.get_by_placeholder("Ingresa tu usuario").fill("admin")
            page.get_by_placeholder("Ingresa tu contraseña").fill("admin123")
            page.get_by_role("button", name="Iniciar Sesión").click()
            _wait(page, 5000)
        except PlaywrightTimeout as exc:
            browser.close()
            raise RuntimeError("No se pudo iniciar sesión como admin.") from exc
        page.screenshot(path=str(CAPTURAS / "08-admin-sidebar.png"), full_page=True)
        browser.close()
    print(f"Captura admin: {CAPTURAS / '08-admin-sidebar.png'}")


def _build_story() -> list:
    s: list = []
    s.extend(
        cover_page(
            LOGO,
            "Guía del administrador — Sistema BESS",
            "Pipeline de datos · Catálogo SQLite · Roles admin y superadmin",
            VERSION,
        )
    )
    s.append(PageBreak())
    s.extend(
        toc_box(
            [
                "1. Responsabilidades",
                "2. Roles y acceso",
                "3. Barra lateral",
                "4. Subestaciones",
                "5. Reglas de negocio",
                "6. Solución de problemas",
                "7. Rutas y scripts",
            ]
        )
    )
    s.append(PageBreak())

    s.extend(section("1", "Responsabilidades"))
    s.append(
        p(
            "El administrador mantiene el pipeline: <b>1)</b> Sincronizar perfiles "
            "(ION Modbus + API BESS/generación), <b>2)</b> Verificar CSV en fuente, "
            "<b>3)</b> Filtrar intersección temporal, <b>4)</b> Generar reportes CSV "
            "para el reporteador.",
            "body",
        )
    )

    s.extend(section("2", "Roles y acceso"))
    s.append(
        table(
            [
                ["Rol", "Sidebar", "Catálogo / BD"],
                ["user", "Oculta", "No"],
                ["admin", "Pipeline completo", "No"],
                ["superadmin", "Pipeline + Catálogo + Mant. DB", "Sí"],
            ],
            [1.2 * inch, 2.5 * inch, 2.8 * inch],
        )
    )

    s.extend(section("3", "Barra lateral"))
    s.extend(img_block(CAPTURAS, "08-admin-sidebar.png", "Panel admin: Ayuda, Procesar todo, pasos", 1))
    s.append(
        table(
            [
                ["Elemento", "Función"],
                ["Ayuda", "Flujo de trabajo en 4 pasos (solo referencia)."],
                ["⚡ Procesar todo", "Verificar + Filtrar + Generar reportes en un clic."],
                ["🔧 Paso a paso", "Sync, Verificar, Filtrar y Generar por separado."],
                ["📂 Cargar archivos", "Subida manual de CSV a ArchivosFuente."],
                ["💲 Consulta — Tarifas", "Lectura del mes actual."],
                ["🏭 Catálogo", "Superadmin: subestaciones, medidores, tarifas, usuarios."],
                ["🗄️ Mantenimiento DB", "Superadmin: SQLite import/export/purga."],
            ],
            [1.8 * inch, 4.7 * inch],
        )
    )
    s.append(Spacer(1, 6))
    s.append(
        p(
            "Tras sync o procesamiento exitoso aparecen <b>banners</b> en sidebar. "
            "Si no hay reportes CSV, el reporteador muestra estado vacío con CTA al pipeline.",
            "body",
        )
    )
    s.append(
        p(
            "<b>Procesar todo</b> requiere medidores validados. Si hay pendientes, "
            "ejecute <b>Sincronizar ahora</b> primero.",
            "body",
        )
    )

    s.extend(section("4", "Subestaciones"))
    s.append(
        table(
            [
                ["Subestación", "Facturación", "BESS", "Generación"],
                ["IUSA 1", "ION + Banco 1", "BESS_NORTE", "Generación"],
                ["IUSA 2", "ION testigo", "BESS_SUR", "Granja solar"],
                ["IUSA ARAGON", "Consumo Aragón", "BESS Aragón", "Generación Aragón"],
            ],
            [1.1 * inch, 1.5 * inch, 1.3 * inch, 2.6 * inch],
        )
    )
    s.append(Spacer(1, 6))
    s.append(p("Catálogo en SQLite (`bess_catalog.db`); CSV en data/Tarifas migra si tablas vacías.", "body"))

    s.extend(section("5", "Reglas de negocio"))
    s.append(
        p(
            "<b>Shapley:</b> atribución generación vs BESS solo en sección Participación. "
            "No propagar ahorros de generación a Capacidad CFE, sidebar ni PDF global "
            "(salvo reporte acumulado: solo parte BESS).",
            "body",
        )
    )
    s.append(
        p(
            "<b>IUSA 1 Banco:</b> intercambio REC/ENT solo en Banco_1_Filtrado.csv. "
            "<b>Consumo:</b> KWH_REC (IUSA 1), KWH_NETO (IUSA 2).",
            "body",
        )
    )
    s.append(p("Autorefresh del reporteador: cada 15 minutos (no sustituye el pipeline).", "body"))

    s.extend(section("6", "Solución de problemas"))
    s.append(
        table(
            [
                ["Síntoma", "Acción"],
                ["Medidores sin validar", "Sincronizar ahora; revisar ION/API."],
                ["Faltan filtrados", "Ejecutar Filtrar antes de reportes."],
                ["Error al escribir CSV", "Cerrar Excel en ArchivosReporte."],
                ["Timeout generación", "run_reporte_bess.py en consola."],
            ],
            [2.2 * inch, 4.3 * inch],
        )
    )

    s.extend(section("7", "Rutas y scripts"))
    s.append(
        table(
            [
                ["Ruta / script", "Uso"],
                ["data/ArchivosFuente/{Sub}/", "CSV crudos (sync o carga)."],
                ["data/ArchivosProcesados/{Sub}/", "Verificados y *_Filtrado.csv."],
                ["data/ArchivosReporte/{Sub}/", "Combinados y energía diaria."],
                ["scripts/sincronizar_perfiles.py", "Sincronización ION + API."],
                ["scripts/run_reporte_bess.py", "Generación masiva de reportes."],
            ],
            [2.6 * inch, 3.9 * inch],
        )
    )
    s.append(Spacer(1, 12))
    s.append(p("Guía para administradores del sistema BESS — IUSASOL.", "footer"))
    return s


def main():
    if not os.environ.get("BESS_SKIP_CAPTURE"):
        try:
            capturar_sidebar_admin()
        except Exception as exc:
            print(f"Advertencia captura admin: {exc}", file=sys.stderr)
    build_pdf(_build_story(), PDF_OUT, f"Guía administrador BESS · v{VERSION}")
    print(f"PDF generado: {PDF_OUT}")


if __name__ == "__main__":
    main()
