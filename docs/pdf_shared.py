"""Utilidades compartidas para manuales PDF (ReportLab)."""

from __future__ import annotations

from pathlib import Path

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

PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch
CONTENT_W = PAGE_W - 2 * MARGIN

C = {
    "text": colors.HexColor("#2d3748"),
    "heading": colors.HexColor("#1a202c"),
    "muted": colors.HexColor("#718096"),
    "line": colors.HexColor("#cbd5e0"),
    "surface": colors.HexColor("#f7fafc"),
    "header_bg": colors.HexColor("#edf2f7"),
    "white": colors.white,
}


def styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Heading1"],
            fontSize=20,
            leading=24,
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
            leading=16,
            textColor=C["text"],
            leftIndent=4,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=13,
            spaceBefore=14,
            spaceAfter=6,
            textColor=C["heading"],
            fontName="Helvetica-Bold",
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=4,
            textColor=C["heading"],
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
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
            spaceAfter=10,
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
            spaceBefore=16,
        ),
    }


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), styles()[style])


def section(num: str, title: str) -> list:
    line = Table([[""]], colWidths=[CONTENT_W], rowHeights=[1])
    line.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, C["line"])]))
    return [Spacer(1, 4), p(f"{num}. {title}", "h1"), line, Spacer(1, 6)]


def table(data: list, col_widths=None) -> Table:
    header = [Paragraph(f"<b>{c}</b>", styles()["body"]) for c in data[0]]
    rows = [header] + [
        [Paragraph(str(c), styles()["body"]) for c in row] for row in data[1:]
    ]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
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
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def formula_box(text: str) -> Table:
    box = Table([[Paragraph(text, styles()["formula"])]], colWidths=[CONTENT_W])
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


def img_block(capturas_dir: Path, filename: str, caption: str, fig_num: int) -> list:
    path = capturas_dir / filename
    if not path.exists():
        return [p(f"<i>[Captura no disponible: {filename}]</i>", "caption")]
    image = Image(str(path))
    max_w = CONTENT_W - 0.1 * inch
    ratio = min(max_w / image.drawWidth, 1.0)
    image.drawWidth *= ratio
    image.drawHeight *= ratio
    frame = Table([[image]], colWidths=[CONTENT_W])
    frame.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 0.5, C["line"]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    cap = Paragraph(f"<b>Figura {fig_num}.</b> {caption}", styles()["caption"])
    return [Spacer(1, 4), frame, cap]


def cover_page(logo_path: Path, title: str, subtitle: str, version: str) -> list:
    items = [Spacer(1, 0.9 * inch)]
    if logo_path.exists():
        logo = Image(str(logo_path))
        ratio = min(1.8 * inch / logo.drawWidth, 1.0)
        logo.drawWidth *= ratio
        logo.drawHeight *= ratio
        logo.hAlign = "CENTER"
        items.append(logo)
        items.append(Spacer(1, 0.35 * inch))
    rule = Table([[""]], colWidths=[2.4 * inch], hAlign="CENTER")
    rule.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.75, C["line"])]))
    items.extend(
        [
            rule,
            Spacer(1, 0.3 * inch),
            p(title, "cover_title"),
            p(subtitle, "cover_sub"),
            Spacer(1, 0.45 * inch),
            p(f"Versión {version}", "cover_meta"),
            p("IUSASOL", "cover_meta"),
        ]
    )
    return items


def toc_box(entries: list[str]) -> list:
    rows = [[Paragraph(s, styles()["toc_item"])] for s in entries]
    box = Table(rows, colWidths=[CONTENT_W])
    box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, C["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [p("Contenido", "toc_title"), box, Spacer(1, 12)]


def build_pdf(story: list, output: Path, header_title: str):
    def _chrome(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(C["line"])
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, PAGE_H - 0.5 * inch, PAGE_W - MARGIN, PAGE_H - 0.5 * inch)
        canvas.setFillColor(C["muted"])
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN, PAGE_H - 0.4 * inch, header_title)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.4 * inch, "IUSASOL")
        canvas.drawCentredString(PAGE_W / 2, 0.42 * inch, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.65 * inch,
        bottomMargin=0.55 * inch,
    )
    doc.build(story, onFirstPage=_chrome, onLaterPages=_chrome)
