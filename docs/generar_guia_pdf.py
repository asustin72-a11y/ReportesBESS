"""
Genera GUIA_USUARIO.pdf con capturas de pantalla de la app local.
Requisitos: streamlit corriendo en http://localhost:8501
Uso: python docs/generar_guia_pdf.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
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
LOGO = ROOT / "data" / "Logo IUSASOL.png"
APP_URL = os.environ.get("BESS_APP_URL", "http://localhost:8501")

PAGE_W, PAGE_H = letter
MARGIN = 0.72 * inch
CONTENT_W = PAGE_W - 2 * MARGIN

BRAND = {
    "primary": colors.HexColor("#1a5276"),
    "primary_dark": colors.HexColor("#154360"),
    "secondary": colors.HexColor("#2e86c1"),
    "accent": colors.HexColor("#27ae60"),
    "accent_light": colors.HexColor("#d5f5e3"),
    "surface": colors.HexColor("#f8fafc"),
    "surface_alt": colors.HexColor("#ebf5fb"),
    "border": colors.HexColor("#d5e8f0"),
    "text": colors.HexColor("#2c3e50"),
    "muted": colors.HexColor("#718096"),
    "white": colors.white,
    "warning_bg": colors.HexColor("#fef9e7"),
    "warning_border": colors.HexColor("#f39c12"),
}


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
        _wait_app(page, 4000)
        panel_tendencia = page.get_by_role("tabpanel", name="Tendencia")
        page.screenshot(path=str(CAPTURAS / "06-tendencia.png"), full_page=True)

        tab_con_bess = panel_tendencia.get_by_role("tab", name="Consumo con BESS")
        tab_con_bess.wait_for(state="visible", timeout=30000)
        tab_con_bess.click()
        _wait_app(page, 3500)
        page.screenshot(path=str(CAPTURAS / "06b-consumo-bess.png"), full_page=True)

        panel_tendencia.get_by_role("tab", name="Operación BESS").click()
        _wait_app(page, 3500)
        page.screenshot(path=str(CAPTURAS / "06c-operacion-bess.png"), full_page=True)

        page.get_by_role("tab", name="Reporte").click()
        _wait_app(page, 2500)
        page.screenshot(path=str(CAPTURAS / "07-reporte.png"), full_page=True)

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
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Heading1"],
            fontSize=28,
            leading=32,
            alignment=TA_CENTER,
            textColor=BRAND["primary"],
            spaceAfter=6,
            fontName="Helvetica-Bold",
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["BodyText"],
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            textColor=BRAND["muted"],
            spaceAfter=4,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            parent=base["BodyText"],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=BRAND["secondary"],
            spaceAfter=2,
        ),
        "toc_title": ParagraphStyle(
            "toc_title",
            parent=base["Heading1"],
            fontSize=18,
            textColor=BRAND["primary"],
            spaceAfter=14,
            fontName="Helvetica-Bold",
        ),
        "toc_item": ParagraphStyle(
            "toc_item",
            parent=base["BodyText"],
            fontSize=10.5,
            leading=20,
            textColor=BRAND["text"],
            leftIndent=8,
        ),
        "section_num": ParagraphStyle(
            "section_num",
            parent=base["BodyText"],
            fontSize=14,
            textColor=BRAND["white"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=base["Heading1"],
            fontSize=15,
            textColor=BRAND["white"],
            fontName="Helvetica-Bold",
            leading=18,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=12,
            spaceBefore=14,
            spaceAfter=6,
            textColor=BRAND["primary"],
            fontName="Helvetica-Bold",
            borderPadding=(0, 0, 4, 0),
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=15,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
            textColor=BRAND["text"],
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["BodyText"],
            fontSize=9,
            leading=12,
            textColor=BRAND["muted"],
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=14,
        ),
        "formula": ParagraphStyle(
            "formula",
            parent=base["Code"],
            fontSize=9.5,
            leading=14,
            textColor=BRAND["primary_dark"],
            fontName="Courier-Bold",
            alignment=TA_LEFT,
        ),
        "tip": ParagraphStyle(
            "tip",
            parent=base["BodyText"],
            fontSize=9.5,
            leading=14,
            textColor=BRAND["text"],
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["BodyText"],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=BRAND["muted"],
            spaceBefore=24,
        ),
    }


def _draw_page(canvas, doc, *, cover=False):
    canvas.saveState()
    if cover:
        canvas.setFillColor(BRAND["primary"])
        canvas.rect(0, PAGE_H * 0.38, PAGE_W, PAGE_H * 0.62, fill=1, stroke=0)
        canvas.setFillColor(BRAND["secondary"])
        canvas.rect(0, PAGE_H * 0.36, PAGE_W, 0.12 * inch, fill=1, stroke=0)
        canvas.setFillColor(BRAND["accent"])
        canvas.circle(PAGE_W - 1.1 * inch, PAGE_H - 1.1 * inch, 0.55 * inch, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#1e8449"))
        canvas.circle(0.9 * inch, PAGE_H * 0.42, 0.35 * inch, fill=1, stroke=0)
    else:
        canvas.setFillColor(BRAND["primary"])
        canvas.rect(0, PAGE_H - 0.42 * inch, PAGE_W, 0.42 * inch, fill=1, stroke=0)
        canvas.setFillColor(BRAND["white"])
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN, PAGE_H - 0.28 * inch, "BESS · Sistema de Energía")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.28 * inch, "Guía de usuario v5.1")

        canvas.setStrokeColor(BRAND["border"])
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 0.52 * inch, PAGE_W - MARGIN, 0.52 * inch)
        canvas.setFillColor(BRAND["muted"])
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN, 0.32 * inch, "IUSASOL · Monitoreo y reportes BESS")
        canvas.drawRightString(PAGE_W - MARGIN, 0.32 * inch, f"Página {doc.page}")
    canvas.restoreState()


def _p(text, style="body"):
    return Paragraph(text.replace("\n", "<br/>"), _styles()[style])


def _section(num: str, title: str):
    st = _styles()
    badge = Table(
        [[Paragraph(num, st["section_num"])]],
        colWidths=[0.42 * inch],
        rowHeights=[0.42 * inch],
    )
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND["secondary"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    row = Table(
        [[badge, Paragraph(title, st["section_title"])]],
        colWidths=[0.5 * inch, CONTENT_W - 0.5 * inch],
    )
    row.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND["primary"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 10),
                ("LEFTPADDING", (1, 0), (1, 0), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return [Spacer(1, 6), row, Spacer(1, 12)]


def _table(data, col_widths=None):
    body_rows = []
    for r, row in enumerate(data):
        body_rows.append([Paragraph(str(c), _styles()["body"] if r else _styles()["body"]) for c in row])
    # Header row bold via inline HTML
    header = [Paragraph(f'<font color="white"><b>{c}</b></font>', _styles()["body"]) for c in data[0]]
    rows = [header] + body_rows[1:]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND["primary"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), BRAND["white"]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (-1, -1), BRAND["text"]),
                ("GRID", (0, 0), (-1, -1), 0.4, BRAND["border"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BRAND["white"], BRAND["surface"]]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return t


def _formula(text):
    box = Table([[Paragraph(text, _styles()["formula"])]], colWidths=[CONTENT_W])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND["surface_alt"]),
                ("BOX", (0, 0), (-1, -1), 0.8, BRAND["secondary"]),
                ("LINEBEFORE", (0, 0), (0, -1), 4, BRAND["accent"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return box


def _tip(text):
    box = Table([[Paragraph(f"<b>Tip:</b> {text}", _styles()["tip"])]], colWidths=[CONTENT_W])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND["accent_light"]),
                ("BOX", (0, 0), (-1, -1), 0.6, BRAND["accent"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return box


def _img(filename, caption, fig_num, max_w=CONTENT_W - 0.2 * inch):
    path = CAPTURAS / filename
    if not path.exists():
        return [Paragraph(f"<i>[Captura no disponible: {filename}]</i>", _styles()["caption"])]
    img = Image(str(path))
    ratio = min(max_w / img.drawWidth, 1.0)
    img.drawWidth *= ratio
    img.drawHeight *= ratio
    frame = Table([[img]], colWidths=[CONTENT_W])
    frame.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, -1), BRAND["surface"]),
                ("BOX", (0, 0), (-1, -1), 1, BRAND["border"]),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    cap = Paragraph(
        f'<font color="#2e86c1"><b>Figura {fig_num}</b></font> — {caption}',
        _styles()["caption"],
    )
    return [Spacer(1, 4), frame, cap]


def _cover_page():
    items = [Spacer(1, 0.55 * inch)]
    if LOGO.exists():
        logo = Image(str(LOGO))
        ratio = min(2.4 * inch / logo.drawWidth, 1.0)
        logo.drawWidth *= ratio
        logo.drawHeight *= ratio
        logo.hAlign = "CENTER"
        items.append(logo)
        items.append(Spacer(1, 0.35 * inch))
    items.extend(
        [
            _p("Guía de usuario", "cover_title"),
            _p("Sistema BESS", "cover_title"),
            Spacer(1, 10),
            _p("Monitoreo, análisis y reportes de almacenamiento de energía", "cover_sub"),
            _p("Medidores ION · BANCO", "cover_sub"),
            Spacer(1, 0.55 * inch),
        ]
    )
    badge = Table(
        [[Paragraph("<b>Versión 5.1</b>", _styles()["cover_meta"])]],
        colWidths=[1.6 * inch],
        hAlign="CENTER",
    )
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND["accent_light"]),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e8449")),
                ("BOX", (0, 0), (-1, -1), 1, BRAND["accent"]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    items.extend([badge, Spacer(1, 1.2 * inch)])
    items.append(_p("IUSASOL · Energía solar y almacenamiento", "cover_meta"))
    items.append(_p("Documento para usuarios del sistema", "cover_meta"))
    return items


def _toc():
    sections = [
        "1. Introducción",
        "2. Acceso al sistema",
        "3. Elementos comunes de la interfaz",
        "4. Pestaña «Operación BESS»",
        "5. Pestaña «Análisis»",
        "6. Pestaña «Tendencia»",
        "7. Pestaña «Reporte»",
        "8. Arbitraje (beneficio económico)",
        "9. Panel administrador",
    ]
    rows = [[Paragraph(s, _styles()["toc_item"])] for s in sections]
    toc_box = Table(rows, colWidths=[CONTENT_W])
    toc_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND["surface"]),
                ("BOX", (0, 0), (-1, -1), 0.8, BRAND["border"]),
                ("LINEBEFORE", (0, 0), (0, -1), 5, BRAND["primary"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return [
        _p("Contenido", "toc_title"),
        toc_box,
        Spacer(1, 16),
    ]


def construir_pdf():
    story = []
    story.extend(_cover_page())
    story.append(PageBreak())
    story.extend(_toc())

    # 1 Intro
    story.extend(_section("1", "Introducción"))
    story.append(
        _p(
            "El sistema BESS permite consultar la operación de la batería, comparar escenarios "
            "<b>con BESS</b> y <b>sin BESS</b>, estimar costos de energía y capacidad CFE, y generar "
            "reportes PDF diarios. Los datos provienen de archivos CSV procesados a partir de mediciones de planta.",
            "body",
        )
    )
    story.append(
        _tip(
            "Use el selector de medidor (ION / BANCO) en la cabecera para alternar entre instalaciones."
        )
    )

    # 2 Acceso
    story.extend(_section("2", "Acceso al sistema"))
    story.append(_p("2.1 Inicio de sesión", "h2"))
    story.append(
        _p(
            "Al abrir la aplicación ingrese usuario y contraseña. La pantalla muestra el logo IUSASOL, "
            "el título <b>BESS · Sistema de Energía</b> y un formulario centrado.",
            "body",
        )
    )
    story.extend(_img("01-login.png", "Pantalla de inicio de sesión", 1))

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
    story.extend(_section("3", "Elementos comunes"))
    story.append(_p("3.1 Cabecera y selector de medidor", "h2"))
    story.append(
        _p(
            "Tras el login: logo IUSASOL, título, rol del usuario, botón <b>Cerrar sesión</b> y selector "
            "<b>ION</b> / <b>BANCO</b>.",
            "body",
        )
    )
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
    story.append(
        _p(
            "3.3 Periodos tarifarios: <b>Base</b>, <b>Intermedio</b> y <b>Punta</b>. "
            "Tarifas desde Tarifas_2026.csv según el mes.",
            "body",
        )
    )

    # 4 Operación BESS
    story.append(PageBreak())
    story.extend(_section("4", "Pestaña «Operación BESS»"))
    story.extend(_img("02-operacion-bess.png", "Operación BESS: resumen, perfil de carga y arbitraje", 2))
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
    story.append(
        _p(
            "Gráfica de potencia (kW): <b>IUSA Con BESS</b>, <b>Carga BESS</b> (positiva) y "
            "<b>Descarga BESS</b> (negativa). Un día: por hora. Varios días: máximo diario.",
            "body",
        )
    )
    story.append(_p("4.3 Tabla de energía", "h2"))
    story.append(
        _p(
            "Incluye consumo por periodo, demanda rolada (kW), carga/descarga BESS y arbitraje por periodo. "
            "En un solo día el consumo es acumulado mensual; en rango múltiple, suma del periodo.",
            "body",
        )
    )

    # 5 Análisis
    story.append(PageBreak())
    story.extend(_section("5", "Pestaña «Análisis»"))
    story.append(_p("Usa <b>fecha de corte</b> única. Acumulados del mes calendario hasta ese día.", "body"))

    story.append(_p("5.1 Demanda", "h2"))
    story.extend(_img("03-analisis-demanda.png", "Demanda del día (15 min) y demanda máxima del mes", 3))
    story.append(
        _p(
            "Curva con/sin BESS en intervalos de 15 minutos. Tabla de picos mensuales por periodo (kW y hora).",
            "body",
        )
    )

    story.append(_p("5.2 Energía y costos", "h2"))
    story.extend(_img("04-analisis-energia.png", "Costo de energía acumulado del mes", 4))
    story.append(_p("Fórmula por periodo:", "body"))
    story.append(_formula("Costo (MXN) = kWh del periodo (entero) × Tarifa del mes ($/kWh)"))
    story.append(Spacer(1, 6))
    story.append(
        _p(
            "Ahorro = Costo sin BESS − Costo con BESS. Gráfica: barras verdes (Con BESS) y rojas (Sin BESS).",
            "body",
        )
    )

    story.append(_p("5.3 Capacidad CFE", "h2"))
    story.extend(_img("05-analisis-cfe.png", "Criterio de capacidad CFE", 5))
    story.append(_formula("DemandaCalculadaCFE = Energía mes (kWh) ÷ (0,74 × 24 × días transcurridos)"))
    story.append(Spacer(1, 4))
    story.append(_formula("Capacidad CFE (kW) = mín(Demanda punta , DemandaCalculadaCFE)"))
    story.append(Spacer(1, 4))
    story.append(_formula("Costo capacidad = Capacidad × Tarifa capacidad del mes"))

    # 6 Tendencia
    story.append(PageBreak())
    story.extend(_section("6", "Pestaña «Tendencia»"))
    story.extend(_img("06-tendencia.png", "Consumo diario por periodo tarifario", 6))
    story.append(
        _p(
            "<b>Resumen del periodo:</b> días, consumo, ahorro y arbitraje acumulado (formato compacto).",
            "body",
        )
    )
    story.append(_p("6.1 Consumo por periodo", "h2"))
    story.append(
        _p(
            "Áreas apiladas Base / Intermedio / Punta. Eje Y: 0–300 000 kWh. Sin promedio móvil.",
            "body",
        )
    )
    story.append(_p("6.2 Consumo con BESS", "h2"))
    story.extend(_img("06b-consumo-bess.png", "Comparativa diaria con y sin BESS", 7))
    story.append(
        _p(
            "Línea verde (con BESS), línea roja (sin BESS), barras de ahorro diario. "
            "Tarjetas: costo con/sin BESS y ahorro acumulado (MXN). Eje Y: 0–300 000 kWh.",
            "body",
        )
    )
    story.append(_p("6.3 Operación BESS (Tendencia)", "h2"))
    story.extend(_img("06c-operacion-bess.png", "Carga, descarga y arbitraje diario", 8))
    story.append(
        _p(
            "Barras de carga/descarga (eje Y: 0–30 000 kWh), arbitraje diario y tarjetas de "
            "carga, descarga y eficiencia (Óptima si ≥ 80 %).",
            "body",
        )
    )

    # 7 Reporte
    story.extend(_section("7", "Pestaña «Reporte»"))
    story.extend(_img("07-reporte.png", "Vista previa y generación del PDF diario", 9))
    story.append(
        _p(
            "Seleccione la fecha, revise KPIs, gráfica y tabla, luego use <b>Generar Reporte Diario</b> "
            "para descargar el PDF.",
            "body",
        )
    )

    # 8 Arbitraje
    story.extend(_section("8", "Arbitraje (beneficio económico)"))
    story.append(_p("Método principal (con datos sin BESS):", "body"))
    story.append(_formula("Arbitraje = Costo sin BESS − Costo con BESS (por periodo y total)"))
    story.append(Spacer(1, 6))
    story.append(_p("Respaldo: (kWh descarga − kWh carga) × tarifa del periodo.", "body"))

    # 9 Admin
    story.append(PageBreak())
    story.extend(_section("9", "Panel administrador"))
    story.extend(_img("08-admin-sidebar.png", "Panel lateral del administrador", 10))
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

    story.append(Spacer(1, 24))
    closing = Table(
        [[Paragraph("Documento para usuarios del sistema BESS", _styles()["footer"])]],
        colWidths=[CONTENT_W],
    )
    closing.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, 0), 1, BRAND["border"]),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(closing)
    story.append(_p("<b>IUSASOL</b> · Energía solar y almacenamiento", "footer"))

    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=letter,
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=0.78 * inch,
        bottomMargin=0.72 * inch,
        title="Guía de usuario BESS",
        author="IUSASOL",
    )

    def first_page(canvas, doc_obj):
        _draw_page(canvas, doc_obj, cover=True)

    def later_pages(canvas, doc_obj):
        _draw_page(canvas, doc_obj, cover=False)

    doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
    print(f"PDF generado: {PDF_OUT}")


def main():
    if os.environ.get("BESS_SKIP_CAPTURE"):
        construir_pdf()
        return
    try:
        capturar_pantallas()
    except Exception as exc:
        print(f"Advertencia capturas: {exc}", file=sys.stderr)
        print("Se generará el PDF con capturas existentes (si las hay).", file=sys.stderr)
    construir_pdf()


if __name__ == "__main__":
    main()
