"""
Genera docs/DESCARGAR_ION.pdf — manual de uso de descargar_ion.exe

Uso: python docs/generar_descargar_ion_pdf.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PDF_OUT = DOCS / "DESCARGAR_ION.pdf"
LOGO = ROOT / "data" / "Logo IUSASOL.png"

MARGIN = 0.75 * inch
CONTENT_W = letter[0] - 2 * MARGIN

C = {
    "text": colors.HexColor("#2d3748"),
    "heading": colors.HexColor("#1a202c"),
    "muted": colors.HexColor("#718096"),
    "line": colors.HexColor("#cbd5e0"),
    "surface": colors.HexColor("#f7fafc"),
    "header_bg": colors.HexColor("#edf2f7"),
    "white": colors.white,
    "code_bg": colors.HexColor("#edf2f7"),
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Heading1"],
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=C["heading"],
            spaceAfter=10,
            fontName="Helvetica-Bold",
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["BodyText"],
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=C["muted"],
            spaceAfter=6,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            parent=base["BodyText"],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=C["muted"],
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=13,
            spaceBefore=14,
            spaceAfter=8,
            textColor=C["heading"],
            fontName="Helvetica-Bold",
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=11,
            spaceBefore=10,
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
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontSize=8.5,
            leading=12,
            fontName="Courier",
            textColor=C["text"],
            leftIndent=0,
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


def _p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), _styles()[style])


def _section(title: str) -> list:
    line = Table([[""]], colWidths=[CONTENT_W], rowHeights=[1])
    line.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, C["line"])]))
    return [Spacer(1, 6), _p(title, "h1"), line, Spacer(1, 8)]


def _table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    header = [Paragraph(f"<b>{c}</b>", _styles()["body"]) for c in data[0]]
    rows = [header] + [
        [Paragraph(str(c), _styles()["body"]) for c in row] for row in data[1:]
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
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def _code_block(text: str) -> Table:
    box = Table([[Paragraph(text.replace("\n", "<br/>"), _styles()["code"])]], colWidths=[CONTENT_W])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), C["code_bg"]),
                ("BOX", (0, 0), (-1, -1), 0.5, C["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return box


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(C["line"])
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, letter[1] - 0.42 * inch, letter[0] - MARGIN, letter[1] - 0.42 * inch)
    canvas.setFillColor(C["muted"])
    canvas.setFont("Helvetica", 8)
    canvas.drawString(MARGIN, letter[1] - 0.32 * inch, "Manual descargar_ion.exe")
    canvas.drawRightString(letter[0] - MARGIN, letter[1] - 0.32 * inch, "IUSASOL")
    canvas.line(MARGIN, 0.42 * inch, letter[0] - MARGIN, 0.42 * inch)
    canvas.drawCentredString(letter[0] / 2, 0.28 * inch, f"Página {doc.page}")
    canvas.restoreState()


def _cover(story: list) -> None:
    story.append(Spacer(1, 1.2 * inch))
    if LOGO.exists():
        from reportlab.platypus import Image

        logo = Image(str(LOGO))
        ratio = min(1.8 * inch / logo.drawWidth, 1.0)
        logo.drawWidth *= ratio
        logo.drawHeight *= ratio
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 0.35 * inch))

    rule = Table([[""]], colWidths=[2.5 * inch], hAlign="CENTER")
    rule.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.75, C["line"])]))
    story.extend(
        [
            rule,
            Spacer(1, 0.3 * inch),
            _p("Manual de uso — descargar_ion.exe", "cover_title"),
            _p("Descarga de perfil de carga · Medidor Schneider ION 8650", "cover_sub"),
            Spacer(1, 0.45 * inch),
            _p(f"Generado: {datetime.now().strftime('%d/%m/%Y')}", "cover_meta"),
            _p("IUSASOL · Sistema BESS", "cover_meta"),
            PageBreak(),
        ]
    )


def _build_story() -> list:
    story: list = []
    _cover(story)

    story.append(
        _p(
            "Herramienta de línea de comandos para descargar el <b>perfil de carga</b> de un "
            "medidor Schneider <b>ION 8650</b> por <b>Modbus TCP</b>, desde una fecha de inicio "
            "hasta el <b>último registro</b> almacenado en el medidor.",
            "body",
        )
    )
    story.append(
        _p(
            "No requiere Python instalado: solo el ejecutable <b>descargar_ion.exe</b> y acceso "
            "de red al medidor (puerto <b>502</b>).",
            "body",
        )
    )

    story.extend(_section("1. Requisitos"))
    story.append(
        _table(
            [
                ["Requisito", "Detalle"],
                ["Sistema", "Windows 10/11 (64 bits)"],
                ["Red", "PC en la misma red que el medidor; firewall permite salida TCP al puerto 502"],
                ["Medidor", "ION 8650 con Data Recorder (módulo 1, 6 canales por defecto)"],
                ["Permisos", "Escritura en la carpeta desde la que se ejecuta el programa"],
            ],
            [1.4 * inch, 5.1 * inch],
        )
    )

    story.extend(_section("2. Parámetros"))
    story.append(
        _table(
            [
                ["#", "Parámetro", "Obligatorio", "Descripción"],
                ["1", "IP", "Sí", "Dirección IP del medidor (ej. 172.16.111.209)"],
                ["2", "Fecha inicio", "Sí", "YYYY-MM-DD o YYYY-MM-DD HH:MM:SS (hora México)"],
                ["3", "Archivo salida", "No", "Ruta del CSV; si se omite, nombre automático en carpeta actual"],
            ],
            [0.35 * inch, 1.1 * inch, 0.9 * inch, 4.15 * inch],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        _p(
            "<b>Comportamiento fijo:</b> la descarga siempre llega hasta el <b>último registro</b> "
            "disponible en el medidor. No hay parámetro de fecha fin.",
            "body",
        )
    )

    story.append(_p("2.1 Opciones avanzadas (opcional)", "h2"))
    story.append(
        _table(
            [
                ["Opción", "Default", "Descripción"],
                ["--puerto", "502", "Puerto Modbus TCP"],
                ["--modulo-dr", "1", "Número de módulo Data Recorder en ION Setup"],
                ["--sources", "6", "Cantidad de canales de energía"],
                ["--int32", "—", "Decodificar valores como int32 (default: float32)"],
            ],
            [1.3 * inch, 0.9 * inch, 4.3 * inch],
        )
    )

    story.extend(_section("3. Uso con el ejecutable"))
    story.append(_p("3.1 Pasos", "h2"))
    story.append(
        _p(
            "1. Copie <b>descargar_ion.exe</b> a la carpeta donde quiera guardar el CSV "
            "(o abra esa carpeta en PowerShell).<br/>"
            "2. Ejecute el comando con la IP del medidor y la fecha de inicio.",
            "body",
        )
    )
    story.append(Spacer(1, 6))
    story.append(_p("Ejemplo básico:", "body"))
    story.append(_code_block("cd C:\\MisDescargas\n.\\descargar_ion.exe 172.16.111.209 2026-05-01"))
    story.append(Spacer(1, 8))
    story.append(_p("Con nombre de archivo explícito:", "body"))
    story.append(
        _code_block(".\\descargar_ion.exe 172.16.111.209 2026-05-01 perfil_mayo.csv")
    )

    story.append(_p("3.2 Nombre del archivo generado (automático)", "h2"))
    story.append(
        _p(
            "Si no indica ruta de salida, el CSV se guarda en <b>la carpeta desde la que ejecutó "
            "el programa</b>, con este formato:",
            "body",
        )
    )
    story.append(_code_block("<IP_con_guiones>_<YYYYMMDD>_<HHMMSS>.csv"))
    story.append(Spacer(1, 6))
    story.append(
        _p(
            "Ejemplo: IP <b>172.16.111.209</b>, ejecutado el 25/06/2026 a las 14:30:52 → "
            "<font face='Courier'>172_16_111_209_20260625_143052.csv</font>",
            "body",
        )
    )

    story.extend(_section("4. Aviso cuando la fecha es muy antigua"))
    story.append(
        _p(
            "Si la fecha solicitada es <b>anterior al primer registro</b> del medidor, el programa "
            "muestra un aviso y <b>continúa</b> descargando <b>todos</b> los datos disponibles:",
            "body",
        )
    )
    story.append(
        _code_block(
            "AVISO: La fecha solicitada es anterior al primer registro disponible.\n"
            "  Solicitada:  2026-05-01 00:00:00\n"
            "  Disponible desde: 2026-06-25 22:20:00\n"
            "  Se descargaran todos los datos disponibles en el medidor."
        )
    )

    story.extend(_section("5. Formato del CSV"))
    story.append(
        _p(
            "Codificación <b>UTF-8 con BOM</b>, separador coma, fin de línea <b>CRLF</b> "
            "(compatible con Excel en Windows). Intervalo típico: <b>5 minutos</b>.",
            "body",
        )
    )
    story.append(
        _table(
            [
                ["Columna", "Descripción"],
                ["Fecha", "Timestamp YYYY-MM-DD HH:MM:SS (America/Mexico_City)"],
                ["KWH_REC", "Energía activa recibida"],
                ["KWH_ENT", "Energía activa entregada"],
                ["KVARH_Q1 … KVARH_Q4", "Energía reactiva por cuadrante"],
            ],
            [1.6 * inch, 4.9 * inch],
        )
    )

    story.extend(_section("6. Salida en consola (ejemplo)"))
    story.append(
        _code_block(
            "Medidor: 172.16.111.209:502  (Data Recorder modulo 1)\n"
            "Fecha solicitada: 2026-05-01 00:00:00\n"
            "Rango efectivo: 2026-05-01 00:05:00 -> 2026-06-26 14:55:00\n"
            "Registros a descargar: 1234 (#1 .. #1234)\n"
            "  Progreso: 100/1234 registros...\n"
            "Descargados 1234 registros -> C:\\MisDescargas\\172_16_111_209_20260625_143052.csv\n"
            "  Rango temporal: 2026-05-01 00:05:00  a  2026-06-26 14:55:00"
        )
    )
    story.append(
        _p("Código de salida: <b>0</b> = éxito, <b>1</b> = error (conexión, sin datos, etc.).", "body")
    )

    story.extend(_section("7. Errores frecuentes"))
    story.append(
        _table(
            [
                ["Mensaje", "Causa probable", "Acción"],
                [
                    "No se pudo conectar a ...:502",
                    "IP incorrecta, medidor apagado o red/firewall",
                    "Verificar IP, ping y puerto 502",
                ],
                [
                    "No hay registros desde ...",
                    "Fecha inicio posterior al último registro",
                    "Usar una fecha anterior",
                ],
                [
                    "No se descargaron registros",
                    "Rango vacío o fallos Modbus",
                    "Revisar módulo DR y número de sources",
                ],
            ],
            [1.8 * inch, 2.0 * inch, 2.7 * inch],
        )
    )

    story.extend(_section("8. Uso alternativo (con Python)"))
    story.append(_p("Desde el proyecto BESS, sin el ejecutable:", "body"))
    story.append(_code_block("cd C:\\BESS\npython scripts\\descargar_ion.py 172.16.111.209 2026-05-01"))
    story.append(Spacer(1, 6))
    story.append(_p("Wrapper PowerShell:", "body"))
    story.append(
        _code_block(".\\scripts\\descargar_ion.ps1 -Ip 172.16.111.209 -Desde 2026-05-01")
    )

    story.extend(_section("9. Generar / actualizar el ejecutable"))
    story.append(_p("Desde la raíz del proyecto BESS, con Python 3.10+ instalado:", "body"))
    story.append(_code_block("cd C:\\BESS\n.\\scripts\\build_descargar_ion.ps1"))
    story.append(Spacer(1, 6))
    story.append(_p("El archivo queda en: <font face='Courier'>C:\\BESS\\dist\\descargar_ion.exe</font>", "body"))
    story.append(
        _p(
            "Distribuya solo ese <b>.exe</b>; no necesita copiar carpetas <b>data</b> ni <b>bess</b>.",
            "body",
        )
    )

    story.extend(_section("10. Integración con BESS"))
    story.append(_p("El CSV descargado puede importarse al pipeline BESS:", "body"))
    story.append(
        _code_block("python scripts\\import_perfil_csv.py --medidor ION ruta\\al\\archivo.csv")
    )
    story.append(Spacer(1, 6))
    story.append(
        _p(
            "O use la sincronización automática diaria "
            "(<font face='Courier'>scripts\\sincronizar_perfiles.py</font>) cuando el medidor "
            "esté en la red del servidor BESS.",
            "body",
        )
    )

    story.append(Spacer(1, 20))
    story.append(_p("Manual de uso descargar_ion.exe — IUSASOL · Sistema BESS", "footer"))
    return story


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="Manual descargar_ion.exe",
        author="IUSASOL",
    )
    doc.build(_build_story(), onFirstPage=_header_footer, onLaterPages=_header_footer)
    print(f"PDF generado: {PDF_OUT}")


if __name__ == "__main__":
    main()
