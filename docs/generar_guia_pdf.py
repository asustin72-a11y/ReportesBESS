"""
Genera GUIA_USUARIO.pdf con capturas de pantalla de la app local.
Requisitos: streamlit corriendo en http://localhost:8501
Uso: python docs/generar_guia_pdf.py
"""
from __future__ import annotations

import copy
import os
import sys
from io import BytesIO
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    Frame,
    Image,
    Paragraph,
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
VERSION = "5.3"

PAGE_W = letter[0]
MARGIN = 0.75 * inch
CONTENT_W = PAGE_W - 2 * MARGIN
PAD_TOP = 0.55 * inch
PAD_BOTTOM = 0.45 * inch
MEASURE_H = 30000  # puntos (~416 in) para medir contenido en una sola página

# Paleta sobria (grises y un acento discreto)
C = {
    "text": colors.HexColor("#2d3748"),
    "heading": colors.HexColor("#1a202c"),
    "muted": colors.HexColor("#718096"),
    "line": colors.HexColor("#cbd5e0"),
    "surface": colors.HexColor("#f7fafc"),
    "header_bg": colors.HexColor("#edf2f7"),
    "white": colors.white,
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

        browser.close()
    print(f"Capturas guardadas en {CAPTURAS}")


def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Heading1"],
            fontSize=22,
            leading=26,
            alignment=TA_CENTER,
            textColor=C["heading"],
            spaceAfter=8,
            fontName="Helvetica-Bold",
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["BodyText"],
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=C["muted"],
            spaceAfter=4,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            parent=base["BodyText"],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=C["muted"],
            spaceAfter=2,
        ),
        "toc_title": ParagraphStyle(
            "toc_title",
            parent=base["Heading1"],
            fontSize=14,
            textColor=C["heading"],
            spaceAfter=10,
            fontName="Helvetica-Bold",
        ),
        "toc_item": ParagraphStyle(
            "toc_item",
            parent=base["BodyText"],
            fontSize=10,
            leading=18,
            textColor=C["text"],
            leftIndent=4,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=13,
            spaceBefore=16,
            spaceAfter=8,
            textColor=C["heading"],
            fontName="Helvetica-Bold",
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=11,
            spaceBefore=12,
            spaceAfter=5,
            textColor=C["heading"],
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=7,
            textColor=C["text"],
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["BodyText"],
            fontSize=8.5,
            leading=11,
            textColor=C["muted"],
            alignment=TA_CENTER,
            spaceBefore=3,
            spaceAfter=12,
        ),
        "formula": ParagraphStyle(
            "formula",
            parent=base["Code"],
            fontSize=9,
            leading=13,
            textColor=C["text"],
            fontName="Courier",
            alignment=TA_LEFT,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["BodyText"],
            fontSize=8.5,
            alignment=TA_CENTER,
            textColor=C["muted"],
            spaceBefore=20,
        ),
    }


def _draw_single_page_chrome(c, page_h):
    c.saveState()
    c.setStrokeColor(C["line"])
    c.setLineWidth(0.5)
    c.line(MARGIN, page_h - 0.42 * inch, PAGE_W - MARGIN, page_h - 0.42 * inch)
    c.setFillColor(C["muted"])
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN, page_h - 0.32 * inch, f"Guía de usuario BESS · v{VERSION}")
    c.drawRightString(PAGE_W - MARGIN, page_h - 0.32 * inch, "IUSASOL")
    c.line(MARGIN, 0.42 * inch, PAGE_W - MARGIN, 0.42 * inch)
    c.restoreState()


def _make_frame(page_h):
    fh = page_h - PAD_TOP - PAD_BOTTOM
    return Frame(
        MARGIN,
        PAD_BOTTOM,
        CONTENT_W,
        fh,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        showBoundary=0,
    )


def _used_content_height(story):
    buf = BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(PAGE_W, MEASURE_H))
    frame = _make_frame(MEASURE_H)
    remaining = frame.addFromList(copy.deepcopy(story), c)
    if remaining:
        raise RuntimeError("El contenido excede el tamaño máximo de página única.")
    return frame._height - (frame._y - frame._y1)


def _render_single_page(story, path):
    used = _used_content_height(story)
    page_h = used + PAD_TOP + PAD_BOTTOM + 4
    c = pdf_canvas.Canvas(str(path), pagesize=(PAGE_W, page_h))
    _draw_single_page_chrome(c, page_h)
    frame = _make_frame(page_h)
    frame.addFromList(story, c)
    c.save()


def _p(text, style="body"):
    return Paragraph(text.replace("\n", "<br/>"), _styles()[style])


def _section(num: str, title: str):
    line = Table([[""]], colWidths=[CONTENT_W], rowHeights=[1])
    line.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, C["line"])]))
    return [
        Spacer(1, 4),
        _p(f"{num}. {title}", "h1"),
        line,
        Spacer(1, 8),
    ]


def _table(data, col_widths=None):
    header = [Paragraph(f"<b>{c}</b>", _styles()["body"]) for c in data[0]]
    rows = [header] + [
        [Paragraph(str(c), _styles()["body"]) for c in row] for row in data[1:]
    ]
    t = Table(rows, colWidths=col_widths, repeatRows=1, splitByRow=0)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C["header_bg"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), C["heading"]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.35, C["line"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["surface"]]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def _formula(text):
    box = Table([[Paragraph(text, _styles()["formula"])]], colWidths=[CONTENT_W])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), C["surface"]),
                ("BOX", (0, 0), (-1, -1), 0.5, C["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return box


def _img(filename, caption, fig_num, max_w=CONTENT_W - 0.15 * inch):
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
                ("BOX", (0, 0), (-1, -1), 0.5, C["line"]),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    cap = Paragraph(f"<b>Figura {fig_num}.</b> {caption}", _styles()["caption"])
    return [Spacer(1, 4), frame, cap]


def _cover_page():
    items = [Spacer(1, 1.1 * inch)]
    if LOGO.exists():
        logo = Image(str(LOGO))
        ratio = min(2.0 * inch / logo.drawWidth, 1.0)
        logo.drawWidth *= ratio
        logo.drawHeight *= ratio
        logo.hAlign = "CENTER"
        items.append(logo)
        items.append(Spacer(1, 0.4 * inch))

    rule = Table([[""]], colWidths=[2.5 * inch], hAlign="CENTER")
    rule.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.75, C["line"])]))
    items.extend(
        [
            rule,
            Spacer(1, 0.35 * inch),
            _p("Guía de usuario — Sistema BESS", "cover_title"),
            _p("Monitoreo, análisis y reportes · Medidores ION y BANCO", "cover_sub"),
            Spacer(1, 0.5 * inch),
            _p(f"Versión {VERSION}", "cover_meta"),
            _p("IUSASOL", "cover_meta"),
            Spacer(1, 1.5 * inch),
        ]
    )
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
        "9. Reglas de redondeo",
        "10. Fuentes de datos",
        "11. Preguntas frecuentes",
    ]
    rows = [[Paragraph(s, _styles()["toc_item"])] for s in sections]
    toc_box = Table(rows, colWidths=[CONTENT_W])
    toc_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, C["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [_p("Contenido", "toc_title"), toc_box, Spacer(1, 14)]


def _build_story():
    story = []
    story.extend(_cover_page())
    story.append(Spacer(1, 0.4 * inch))
    story.extend(_toc())

    story.extend(_section("1", "Introducción"))
    story.append(
        _p(
            "El sistema BESS permite consultar la operación de la batería, comparar escenarios "
            "con BESS y sin BESS, estimar costos de energía y capacidad CFE, y generar reportes PDF diarios. "
            "Los datos provienen de archivos CSV procesados a partir de mediciones de planta.",
            "body",
        )
    )
    story.append(
        _p(
            "Use el selector de medidor (ION / BANCO) en la cabecera para alternar entre instalaciones.",
            "body",
        )
    )

    story.extend(_section("2", "Acceso al sistema"))
    story.append(_p("2.1 Inicio de sesión", "h2"))
    story.append(
        _p(
            "Al abrir la aplicación ingrese usuario y contraseña. La pantalla muestra el logo IUSASOL, "
            "el título BESS · Sistema de Energía y un formulario centrado.",
            "body",
        )
    )
    story.extend(_img("01-login.png", "Pantalla de inicio de sesión", 1))

    story.append(_p("2.2 Uso de la aplicación", "h2"))
    story.append(
        _p(
            "Tras autenticarse podrá consultar pestañas, gráficas, tablas y descargar reportes PDF. "
            "Use Cerrar sesión al terminar. Las credenciales las proporciona el administrador del sistema.",
            "body",
        )
    )

    story.extend(_section("3", "Elementos comunes"))
    story.append(_p("3.1 Cabecera y selector de medidor", "h2"))
    story.append(
        _p(
            "Tras el login: logo IUSASOL, título, nombre de usuario, botón Cerrar sesión y selector ION / BANCO.",
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
            "3.3 Periodos tarifarios: Base, Intermedio y Punta. "
            "Tarifas desde Tarifas_2026.csv según el mes.",
            "body",
        )
    )

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
            "Gráfica de potencia (kW): IUSA Con BESS, Carga BESS (positiva) y Descarga BESS (negativa). "
            "Un día: por hora. Varios días: máximo diario.",
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

    story.extend(_section("5", "Pestaña «Análisis»"))
    story.append(_p("Usa fecha de corte única. Acumulados del mes calendario hasta ese día.", "body"))

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

    story.extend(_section("6", "Pestaña «Tendencia»"))
    story.extend(_img("06-tendencia.png", "Consumo diario por periodo tarifario", 6))
    story.append(
        _p("Resumen del periodo: días, consumo, ahorro y arbitraje acumulado (formato compacto).", "body")
    )
    story.append(_p("6.1 Consumo por periodo", "h2"))
    story.append(
        _p("Áreas apiladas Base / Intermedio / Punta. Eje Y: 0–300 000 kWh. Sin promedio móvil.", "body")
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

    story.extend(_section("7", "Pestaña «Reporte»"))
    story.extend(_img("07-reporte.png", "Vista previa y generación del PDF diario", 9))
    story.append(
        _p(
            "Seleccione la fecha, revise KPIs, gráfica y tabla, luego use Generar Reporte Diario "
            "para descargar el PDF.",
            "body",
        )
    )

    story.extend(_section("8", "Arbitraje (beneficio económico)"))
    story.append(_p("Método principal (con datos sin BESS):", "body"))
    story.append(_formula("Arbitraje = Costo sin BESS − Costo con BESS (por periodo y total)"))
    story.append(Spacer(1, 6))
    story.append(_p("Respaldo: (kWh descarga − kWh carga) × tarifa del periodo.", "body"))

    story.extend(_section("9", "Reglas de redondeo"))
    story.append(
        _table(
            [
                ["Magnitud", "Regla"],
                ["kWh", "Entero más cercano (≥ 0,5 sube)."],
                ["Costos de energía (MXN)", "2 decimales, redondeo matemático."],
                ["Demanda / capacidad (kW)", "Redondeo hacia arriba al entero."],
                ["Costo de capacidad (MXN)", "Redondeo hacia arriba a 2 decimales."],
            ],
            [2.2 * inch, 4.3 * inch],
        )
    )

    story.extend(_section("10", "Fuentes de datos"))
    story.append(
        _table(
            [
                ["Archivo", "Contenido"],
                ["COMBINADO_POR_MINUTO_{ION|BANCO}.csv", "Series minuto a minuto: demanda, carga/descarga BESS."],
                ["ENERGIA_{ION|BANCO}_POR_DIA.csv", "Energía diaria por periodo, con y sin BESS."],
                ["ENERGIA_BESS_POR_DIA.csv", "Carga y descarga BESS por periodo y día."],
                ["ACUMULADOS_{ION|BANCO}.csv", "Acumulados mensuales: energía, demandas máximas."],
                ["Tarifas/Tarifas_2026.csv", "Tarifas mensuales Base, Intermedio, Punta y Capacidad."],
            ],
            [2.4 * inch, 4.1 * inch],
        )
    )

    story.extend(_section("11", "Preguntas frecuentes"))
    story.append(
        _p(
            "<b>¿Por qué el consumo «mensual» en un reporte de un solo día?</b> "
            "En vista de un día, la fila de consumo refleja lo acumulado del mes natural hasta esa fecha.",
            "body",
        )
    )
    story.append(
        _p(
            "<b>¿Por qué no veo comparación sin BESS?</b> "
            "Los CSV deben incluir columnas *_SIN_BESS. Contacte al administrador del sistema.",
            "body",
        )
    )
    story.append(
        _p(
            "<b>¿El arbitraje del dashboard y el del reporte diario son iguales?</b> "
            "Para un solo día en Operación BESS coinciden con el reporte de esa fecha; "
            "en rangos de varios días, el dashboard integra el periodo completo.",
            "body",
        )
    )

    story.append(Spacer(1, 20))
    story.append(_p("Documento para usuarios del sistema BESS — IUSASOL.", "footer"))
    return story


def construir_pdf():
    story = _build_story()
    _render_single_page(story, PDF_OUT)
    print(f"PDF generado: {PDF_OUT} (página única continua)")


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
