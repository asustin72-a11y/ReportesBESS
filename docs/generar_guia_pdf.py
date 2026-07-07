"""
Genera GUIA_USUARIO.pdf (manual del reporteador, v5.8).

Requisitos opcionales para capturas: app en http://localhost:8501
Uso:
  python docs/generar_guia_pdf.py
  BESS_SKIP_CAPTURE=1 python docs/generar_guia_pdf.py
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
    CONTENT_W,
    build_pdf,
    cover_page,
    formula_box,
    img_block,
    p,
    section,
    table,
    toc_box,
)

DOCS = ROOT / "docs"
CAPTURAS = DOCS / "capturas"
PDF_OUT = DOCS / "GUIA_USUARIO.pdf"
LOGO = ROOT / "data" / "Logo IUSASOL.png"
APP_URL = os.environ.get("BESS_APP_URL", "http://localhost:8501")


def _wait(page, ms=2500):
    page.wait_for_timeout(ms)


def _click_nav(page, key: str):
    page.locator(f".st-key-nav_btn_{key} button").first.click()
    _wait(page, 2800)


def capturar_pantallas():
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        _wait(page, 4000)
        page.screenshot(path=str(CAPTURAS / "01-login.png"), full_page=True)

        try:
            page.get_by_placeholder("Ingresa tu usuario").fill("user")
            page.get_by_placeholder("Ingresa tu contraseña").fill("user123")
            page.get_by_role("button", name="Iniciar Sesión").click()
            _wait(page, 5500)
        except PlaywrightTimeout as exc:
            browser.close()
            raise RuntimeError("No se pudo iniciar sesión. ¿Está corriendo la app?") from exc

        page.screenshot(path=str(CAPTURAS / "02-operacion-bess.png"), full_page=True)

        _click_nav(page, "analisis")
        page.screenshot(path=str(CAPTURAS / "03-analisis-demanda.png"), full_page=True)

        page.get_by_role("tab", name="Energía y costos").click()
        _wait(page, 2500)
        page.screenshot(path=str(CAPTURAS / "04-analisis-energia.png"), full_page=True)

        page.get_by_role("tab", name="Capacidad CFE").click()
        _wait(page, 2500)
        page.screenshot(path=str(CAPTURAS / "05-analisis-cfe.png"), full_page=True)

        _click_nav(page, "tendencia")
        _wait(page, 3500)
        panel = page.locator('[data-testid="stMainBlockContainer"]').last
        page.screenshot(path=str(CAPTURAS / "06-tendencia.png"), full_page=True)

        page.get_by_role("tab", name="Consumo con BESS").click()
        _wait(page, 3000)
        page.screenshot(path=str(CAPTURAS / "06b-consumo-bess.png"), full_page=True)

        page.get_by_role("tab", name="Operación BESS").click()
        _wait(page, 3000)
        page.screenshot(path=str(CAPTURAS / "06c-operacion-bess.png"), full_page=True)

        _click_nav(page, "reportes")
        _wait(page, 3000)
        page.screenshot(path=str(CAPTURAS / "07-reporte.png"), full_page=True)

        browser.close()
    print(f"Capturas guardadas en {CAPTURAS}")


def _build_story() -> list:
    s: list = []
    s.extend(
        cover_page(
            LOGO,
            "Guía de usuario — Sistema BESS",
            "Reporteador · Subestaciones IUSA 1, IUSA 2 e IUSA ARAGON",
            VERSION,
        )
    )
    s.append(PageBreak())
    s.extend(
        toc_box(
            [
                "1. Introducción",
                "2. Acceso y roles",
                "3. Interfaz común",
                "4. Operación BESS",
                "5. Análisis",
                "6. Participación y Generación",
                "7. Tendencia",
                "8. Reportes y Recibo",
                "9. Arbitraje",
                "10. Redondeo y datos",
                "11. Preguntas frecuentes",
            ]
        )
    )
    s.append(PageBreak())

    s.extend(section("1", "Introducción"))
    s.append(
        p(
            "El sistema BESS consulta operación de batería, compara escenarios con y sin BESS, "
            "estima costos CFE y genera reportes PDF. Los datos provienen de CSV procesados "
            "por el administrador (sincronización, verificación, filtrado y reportes).",
            "body",
        )
    )

    s.extend(section("2", "Acceso y roles"))
    s.extend(img_block(CAPTURAS, "01-login.png", "Pantalla de inicio de sesión", 1))
    s.append(
        table(
            [
                ["Rol", "Experiencia"],
                ["Visualizador (user)", "Solo reporteador; barra lateral oculta."],
                ["Operador (admin)", "Reporteador + pipeline en sidebar."],
                ["Superadmin", "Operador + catálogo SQLite y mantenimiento BD."],
            ],
            [1.6 * inch, 4.9 * inch],
        )
    )
    s.append(Spacer(1, 8))
    s.append(p("Use <b>Cerrar sesión</b> al terminar. Credenciales: administrador del sistema.", "body"))

    s.extend(section("3", "Interfaz común"))
    s.append(p("3.1 Cabecera: logo, usuario, cerrar sesión.", "h2"))
    s.append(p("3.2 Selectores <b>Subestación</b> y <b>Medidor de facturación</b>.", "h2"))
    s.append(
        p(
            "3.3 Navegación: botones Ir a la sección (Operación, Análisis, Participación, "
            "Tendencia, Generación, Reportes, Recibo). Participación y Generación solo "
            "si aplican a la subestación. Ayuda flotante al mantener el cursor ~2 s.",
            "body",
        )
    )
    s.append(
        table(
            [
                ["Selector", "Secciones", "Uso"],
                ["Rango Desde/Hasta", "Operación, Tendencia", "Uno o varios días."],
                ["Fecha única", "Análisis, Reportes, Recibo", "Día de corte o PDF."],
            ],
            [1.5 * inch, 2.2 * inch, 2.8 * inch],
        )
    )
    s.append(Spacer(1, 6))
    s.append(p("La app recarga automáticamente cada <b>15 minutos</b>.", "body"))

    s.extend(section("4", "Operación BESS"))
    s.extend(img_block(CAPTURAS, "02-operacion-bess.png", "Resumen, perfil y arbitraje", 2))
    s.append(
        table(
            [
                ["Indicador", "Descripción"],
                ["Carga / Descarga BESS", "kWh en el rango (KWH_REC_BESS / KWH_ENT_BESS)."],
                ["Eficiencia", "(Descarga ÷ Carga) × 100 — Óptima si ≥ 80 %."],
                ["Arbitraje", "Beneficio MXN (ver §9)."],
            ],
            [1.8 * inch, 4.7 * inch],
        )
    )
    s.append(Spacer(1, 6))
    s.append(
        p(
            "Perfil de carga: demanda con BESS, carga y descarga. Incluye curva de generación "
            "si la subestación tiene recurso. Tabla: consumo, demanda rolada, generación "
            "acumulada (kWh), carga/descarga y arbitraje por periodo.",
            "body",
        )
    )

    s.extend(section("5", "Análisis"))
    s.append(p("Fecha de corte única; acumulados del mes hasta ese día.", "body"))
    s.append(p("5.1 Demanda", "h2"))
    s.extend(img_block(CAPTURAS, "03-analisis-demanda.png", "Demanda 15 min y picos del mes", 3))
    s.append(
        p(
            "Curva con/sin BESS. Demanda rodante reiniciada cada mes (00:05 y 00:10 en cero).",
            "body",
        )
    )
    s.append(p("5.2 Energía y costos", "h2"))
    s.extend(img_block(CAPTURAS, "04-analisis-energia.png", "Costo de energía del mes", 4))
    s.append(formula_box("Costo (MXN) = kWh periodo (entero) × Tarifa del mes ($/kWh)"))
    s.append(Spacer(1, 4))
    s.append(p("Ahorro = Costo sin BESS − Costo con BESS.", "body"))
    s.append(p("5.3 Capacidad CFE", "h2"))
    s.extend(img_block(CAPTURAS, "05-analisis-cfe.png", "Criterio capacidad CFE", 5))
    s.append(formula_box("Capacidad CFE = mín(Demanda punta , Energía mes ÷ (0,74×24×días))"))
    s.append(Spacer(1, 4))
    s.append(
        p(
            "Comparación con/sin BESS. No incluye atribución Shapley de generación.",
            "body",
        )
    )

    s.extend(section("6", "Participación y Generación"))
    s.append(
        p(
            "<b>Participación Capacidad:</b> atribución Shapley generación vs BESS (solo "
            "subestaciones compatibles). Referencia en esta sección; no altera Capacidad CFE.",
            "body",
        )
    )
    s.append(
        p(
            "<b>Generación:</b> energía del recurso de generación de la subestación. "
            "Fila Generación Acumulada en tablas es referencia kWh.",
            "body",
        )
    )

    s.extend(section("7", "Tendencia"))
    s.extend(img_block(CAPTURAS, "06-tendencia.png", "Consumo por periodo tarifario", 6))
    s.extend(img_block(CAPTURAS, "06b-consumo-bess.png", "Comparativa con/sin BESS", 7))
    s.extend(img_block(CAPTURAS, "06c-operacion-bess.png", "Carga, descarga y arbitraje diario", 8))

    s.extend(section("8", "Reportes y Recibo"))
    s.extend(img_block(CAPTURAS, "07-reporte.png", "Reporte diario y PDF", 9))
    s.append(
        p(
            "<b>Reporte diario:</b> fecha, vista previa, opción incluir generación en PDF, descarga. "
            "<b>Reporte acumulado:</b> ahorros BESS en periodo (Shapley solo parte BESS). "
            "<b>Recibo CFE:</b> estimación mensual con/sin BESS y PDF.",
            "body",
        )
    )

    s.extend(section("9", "Arbitraje"))
    s.append(formula_box("Arbitraje = Costo sin BESS − Costo con BESS (por periodo y total)"))
    s.append(Spacer(1, 4))
    s.append(p("Respaldo: (kWh descarga − kWh carga) × tarifa del periodo.", "body"))

    s.extend(section("10", "Redondeo y datos"))
    s.append(
        table(
            [
                ["Magnitud", "Regla"],
                ["kWh", "Entero más cercano."],
                ["Costos energía", "2 decimales."],
                ["Demanda / capacidad kW", "Redondeo hacia arriba."],
            ],
            [2.2 * inch, 4.3 * inch],
        )
    )
    s.append(Spacer(1, 8))
    s.append(
        table(
            [
                ["Archivo", "Contenido"],
                ["COMBINADO_POR_MINUTO_*.csv", "Series minuto a minuto."],
                ["ENERGIA_*_POR_DIA.csv", "Energía diaria por periodo."],
                ["ACUMULADOS_*.csv", "Acumulados mensuales."],
            ],
            [2.5 * inch, 3.9 * inch],
        )
    )

    s.extend(section("11", "Preguntas frecuentes"))
    s.append(
        p(
            "<b>¿Sin gráficas?</b> El administrador debe ejecutar Procesar todo en el pipeline.",
            "body",
        )
    )
    s.append(
        p(
            "<b>¿Sin Participación/Generación?</b> Se ocultan si no aplican a la subestación.",
            "body",
        )
    )
    s.append(
        p(
            "<b>¿Consumo mensual en un solo día?</b> Es acumulado del mes natural hasta esa fecha.",
            "body",
        )
    )
    s.append(Spacer(1, 12))
    s.append(p("Documento para usuarios del sistema BESS — IUSASOL.", "footer"))
    return s


def main():
    if not os.environ.get("BESS_SKIP_CAPTURE"):
        try:
            capturar_pantallas()
        except Exception as exc:
            print(f"Advertencia capturas: {exc}", file=sys.stderr)
            print("Se generará el PDF con capturas existentes.", file=sys.stderr)
    build_pdf(_build_story(), PDF_OUT, f"Guía de usuario BESS · v{VERSION}")
    print(f"PDF generado: {PDF_OUT}")


if __name__ == "__main__":
    main()
