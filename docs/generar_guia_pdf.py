"""
Genera GUIA_USUARIO.pdf con capturas de pantalla de la app local.
Requisitos: streamlit corriendo en http://localhost:8501
Uso: python docs/generar_guia_pdf.py
"""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CAPTURAS = DOCS / "capturas"
PDF_OUT = DOCS / "GUIA_USUARIO.pdf"
APP_URL = os.environ.get("BESS_APP_URL", "http://localhost:8501")

CAPTURES = [
    ("01-login.png", None),
    ("02-operacion-bess.png", None),
    ("03-analisis-demanda.png", "Análisis"),
    ("04-analisis-energia.png", ("Análisis", "Energía y costos")),
    ("05-analisis-cfe.png", ("Análisis", "Capacidad CFE")),
    ("06-tendencia.png", "Tendencia"),
    ("07-reporte.png", "Reporte"),
    ("08-admin-sidebar.png", "admin"),
]


def _wait_app(page, ms=2500):
    page.wait_for_timeout(ms)


def capturar_pantallas():
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        _wait_app(page, 4000)

        page.screenshot(path=str(CAPTURAS / "01-login.png"), full_page=True)

        try:
            page.get_by_placeholder("Ingresa tu usuario").fill("user")
            page.get_by_placeholder("Ingresa tu contraseña").fill("user123")
            page.get_by_role("button", name="Iniciar Sesión").click()
            _wait_app(page, 5000)
        except PlaywrightTimeout as exc:
            browser.close()
            raise RuntimeError("No se pudo iniciar sesión. ¿Está corriendo la app?") from exc

        page.screenshot(path=str(CAPTURAS / "02-operacion-bess.png"), full_page=True)

        page.get_by_role("tab", name="Análisis").click()
        _wait_app(page, 2500)
        page.screenshot(path=str(CAPTURAS / "03-analisis-demanda.png"), full_page=True)

        page.get_by_role("tab", name="Energía y costos").click()
        _wait_app(page, 2500)
        page.screenshot(path=str(CAPTURAS / "04-analisis-energia.png"), full_page=True)

        page.get_by_role("tab", name="Capacidad CFE").click()
        _wait_app(page, 2500)
        page.screenshot(path=str(CAPTURAS / "05-analisis-cfe.png"), full_page=True)

        page.get_by_role("tab", name="Tendencia").click()
        _wait_app(page, 2500)
        page.screenshot(path=str(CAPTURAS / "06-tendencia.png"), full_page=True)

        page.get_by_role("tab", name="Reporte").click()
        _wait_app(page, 2500)
        page.screenshot(path=str(CAPTURAS / "07-reporte.png"), full_page=True)

        # Admin sidebar
        try:
            page.get_by_role("button", name="Cerrar sesión").click()
            _wait_app(page, 3000)
            page.get_by_placeholder("Ingresa tu usuario").fill("admin")
            page.get_by_placeholder("Ingresa tu contraseña").fill("admin123")
            page.get_by_role("button", name="Iniciar Sesión").click()
            _wait_app(page, 5000)
            header_btn = page.locator('[data-testid="stHeader"] button').first
            if header_btn.count():
                header_btn.click()
                _wait_app(page, 1500)
            page.screenshot(path=str(CAPTURAS / "08-admin-sidebar.png"), full_page=True)
        except Exception:
            page.screenshot(path=str(CAPTURAS / "08-admin-sidebar.png"), full_page=True)

        browser.close()
    print(f"Capturas guardadas en {CAPTURAS}")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Heading1"],
            fontSize=22,
            spaceAfter=14,
            textColor=colors.HexColor("#1a5276"),
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=16,
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.HexColor("#1a5276"),
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=13,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#2c3e50"),
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["BodyText"],
            fontSize=9,
            textColor=colors.HexColor("#718096"),
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "formula": ParagraphStyle(
            "formula",
            parent=base["Code"],
            fontSize=9,
            backColor=colors.HexColor("#f8fafc"),
            borderPadding=6,
            spaceAfter=8,
        ),
    }


def _img(filename, caption, max_w=6.5 * inch):
    path = CAPTURAS / filename
    if not path.exists():
        return [Paragraph(f"<i>[Captura no disponible: {filename}]</i>", _styles()["caption"])]
    img = Image(str(path))
    ratio = min(max_w / img.drawWidth, 1.0)
    img.drawWidth *= ratio
    img.drawHeight *= ratio
    return [
        Spacer(1, 6),
        img,
        Paragraph(caption, _styles()["caption"]),
    ]


def _table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def _p(text, style="body"):
    return Paragraph(text.replace("\n", "<br/>"), _styles()[style])


def construir_pdf():
    st = _styles()
    story = []

    story.append(_p("Guía de usuario — Sistema BESS", "title"))
    story.append(_p("<b>Versión 5.0</b> · Monitoreo, análisis y reportes BESS (medidores ION y BANCO)", "body"))
    story.append(Spacer(1, 12))

    # 1 Intro
    story.append(_p("1. Introducción", "h1"))
    story.append(_p(
        "El sistema BESS permite consultar la operación de la batería, comparar escenarios "
        "<b>con BESS</b> y <b>sin BESS</b>, estimar costos de energía y capacidad CFE, y generar "
        "reportes PDF diarios. Los datos provienen de archivos CSV procesados a partir de mediciones de planta.",
        "body",
    ))

    # 2 Acceso
    story.append(_p("2. Acceso al sistema", "h1"))
    story.append(_p("2.1 Inicio de sesión", "h2"))
    story.append(_p(
        "Al abrir la aplicación ingrese usuario y contraseña asignados. La pantalla de acceso es compacta y centrada.",
        "body",
    ))
    story.extend(_img("01-login.png", "Figura 1 — Pantalla de inicio de sesión"))

    story.append(_p("2.2 Roles", "h2"))
    story.append(
        _table(
            [
                ["Rol", "Permisos"],
                ["Usuario (visualizador)", "Consulta pestañas, gráficas, tablas y descarga PDF. Sidebar colapsada por defecto."],
                ["Administrador", "Todo lo anterior + carga de archivos, procesamiento de datos y tarifas en el panel lateral."],
            ],
            [1.6 * inch, 4.9 * inch],
        )
    )
    story.append(Spacer(1, 10))

    # 3 Comunes
    story.append(_p("3. Elementos comunes", "h1"))
    story.append(_p("3.1 Selector de medidor", "h2"))
    story.append(_p("En la parte superior elija <b>ION</b> o <b>BANCO</b>. Todas las pestañas usan el medidor activo.", "body"))
    story.append(_p("3.2 Selectores de fecha", "h2"))
    story.append(
        _table(
            [
                ["Tipo", "Pestañas", "Uso"],
                ["Rango (Desde / Hasta)", "Operación BESS, Tendencia", "Uno o varios días de análisis."],
                ["Fecha única", "Análisis, Reporte", "Día de corte o del reporte PDF."],
            ],
            [1.4 * inch, 2.0 * inch, 3.1 * inch],
        )
    )
    story.append(Spacer(1, 8))
    story.append(_p("3.3 Periodos tarifarios: <b>Base</b>, <b>Intermedio</b> y <b>Punta</b>. Tarifas desde Tarifas_2026.csv según el mes.", "body"))

    # 4 Operación BESS
    story.append(PageBreak())
    story.append(_p("4. Pestaña «Operación BESS»", "h1"))
    story.extend(_img("02-operacion-bess.png", "Figura 2 — Operación BESS: resumen, perfil de carga y arbitraje"))
    story.append(_p("4.1 Resumen del periodo", "h2"))
    story.append(
        _table(
            [
                ["Indicador", "Descripción", "Cálculo"],
                ["Carga BESS", "Energía absorbida (kWh)", "Suma KWH_REC_BESS en el rango"],
                ["Descarga BESS", "Energía entregada (kWh)", "Suma KWH_ENT_BESS en el rango"],
                ["Eficiencia", "Rendimiento (%)", "(Descarga ÷ Carga) × 100"],
                ["Arbitraje", "Beneficio (MXN)", "Costo sin BESS − costo con BESS (ver §8)"],
            ],
            [1.2 * inch, 2.3 * inch, 2.5 * inch],
        )
    )
    story.append(Spacer(1, 8))
    story.append(_p("4.2 Perfil de carga", "h2"))
    story.append(_p(
        "Gráfica de potencia (kW): <b>IUSA Con BESS</b>, <b>Carga BESS</b> (positiva) y "
        "<b>Descarga BESS</b> (negativa). Un día: por hora. Varios días: máximo diario.",
        "body",
    ))
    story.append(_p("4.3 Tabla de energía", "h2"))
    story.append(_p(
        "Incluye consumo por periodo, demanda rolada (kW), carga/descarga BESS y arbitraje por periodo. "
        "En un solo día el consumo es acumulado mensual; en rango múltiple, suma del periodo.",
        "body",
    ))

    # 5 Análisis
    story.append(PageBreak())
    story.append(_p("5. Pestaña «Análisis»", "h1"))
    story.append(_p("Usa <b>fecha de corte</b> única. Acumulados del mes calendario hasta ese día.", "body"))

    story.append(_p("5.1 Demanda", "h2"))
    story.extend(_img("03-analisis-demanda.png", "Figura 3 — Demanda del día (15 min) y demanda máxima del mes"))
    story.append(_p(
        "Curva con/sin BESS en intervalos de 15 minutos. Tabla de picos mensuales por periodo (kW y hora).",
        "body",
    ))

    story.append(_p("5.2 Energía y costos", "h2"))
    story.extend(_img("04-analisis-energia.png", "Figura 4 — Costo de energía acumulado del mes"))
    story.append(_p("Fórmula por periodo:", "body"))
    story.append(_p("Costo (MXN) = kWh del periodo (entero) × Tarifa del mes ($/kWh)", "formula"))
    story.append(_p("Ahorro = Costo sin BESS − Costo con BESS.", "body"))

    story.append(_p("5.3 Capacidad CFE", "h2"))
    story.extend(_img("05-analisis-cfe.png", "Figura 5 — Criterio de capacidad CFE"))
    story.append(_p("DemandaCalculadaCFE = Energía mes (kWh) ÷ (0,74 × 24 × días transcurridos)", "formula"))
    story.append(_p("Capacidad CFE (kW) = mín(Demanda punta , DemandaCalculadaCFE)", "formula"))
    story.append(_p("Costo capacidad = Capacidad × Tarifa capacidad del mes", "formula"))

    # 6 Tendencia
    story.append(PageBreak())
    story.append(_p("6. Pestaña «Tendencia»", "h1"))
    story.extend(_img("06-tendencia.png", "Figura 6 — Tendencia histórica por rango de fechas"))
    story.append(_p(
        "<b>Consumo por periodo:</b> áreas apiladas Base/Intermedio/Punta y promedio móvil 7 días.<br/>"
        "<b>Con vs sin BESS:</b> líneas de consumo diario y barras de diferencia kWh.<br/>"
        "<b>Operación BESS:</b> carga/descarga diaria y arbitraje por día.",
        "body",
    ))

    # 7 Reporte
    story.append(_p("7. Pestaña «Reporte»", "h1"))
    story.extend(_img("07-reporte.png", "Figura 7 — Vista previa y generación del PDF diario"))
    story.append(_p(
        "Seleccione la fecha, revise KPIs, gráfica y tabla, luego use <b>Generar Reporte Diario</b> para descargar el PDF.",
        "body",
    ))

    # 8 Arbitraje
    story.append(_p("8. Arbitraje (beneficio económico)", "h1"))
    story.append(_p("Método principal (con datos sin BESS):", "body"))
    story.append(_p("Arbitraje = Costo sin BESS − Costo con BESS (por periodo y total)", "formula"))
    story.append(_p("Respaldo: (kWh descarga − kWh carga) × tarifa del periodo.", "body"))

    # 9 Admin
    story.append(PageBreak())
    story.append(_p("9. Panel administrador", "h1"))
    story.extend(_img("08-admin-sidebar.png", "Figura 8 — Panel lateral del administrador"))
    story.append(
        _table(
            [
                ["Opción", "Función"],
                ["Cargar archivos", "Sube CSV fuente (ION, BESS, Banco1)"],
                ["Verificar / Filtrar", "Valida y procesa datos crudos"],
                ["Generar reportes", "Actualiza CSV de reporte ION y BANCO"],
                ["Tarifas del mes", "Consulta tarifas vigentes"],
            ],
            [1.8 * inch, 4.7 * inch],
        )
    )

    story.append(Spacer(1, 20))
    story.append(_p("Documento generado para usuarios del sistema BESS — IUSASOL.", "caption"))

    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Guía de usuario BESS",
        author="IUSASOL",
    )
    doc.build(story)
    print(f"PDF generado: {PDF_OUT}")


def main():
    try:
        capturar_pantallas()
    except Exception as exc:
        print(f"Advertencia capturas: {exc}", file=sys.stderr)
        print("Se generará el PDF con capturas existentes (si las hay).", file=sys.stderr)
    construir_pdf()


if __name__ == "__main__":
    main()
