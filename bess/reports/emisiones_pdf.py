"""PDF de huella de carbono / emisiones CO2."""

from __future__ import annotations

import io
from typing import Any

from bess.cfe.emisiones import CITA_FACTORES_EMISION, EF_GAS_PLANO_KG_KWH, FACTORES_EMISION
from bess.config.constants import slug_medidor
from bess.reports.assets import buscar_logo, formatear_fecha_espanol
from bess.reports.daily_pdf import _PDF, _pdf_dibujar_pie, _pdf_guardar_logo, _pdf_styles


def nombre_archivo_emisiones(fecha, prefijo: str, escenario_id: str) -> str:
    return (
        f"Emisiones_{slug_medidor(prefijo)}_{escenario_id}_"
        f"{fecha.strftime('%Y%m')}.pdf"
    )


def _fmt_kwh(v: float) -> str:
    return f"{v:,.0f}"


def _fmt_t(v: float | None, *, con_signo: bool = False) -> str:
    if v is None:
        return "-"
    if con_signo and v > 0:
        return f"+{v:,.2f}"
    return f"{v:,.2f}"


def _fmt_pct(v: float | None, *, con_signo: bool = False) -> str:
    if v is None:
        return "-"
    if con_signo and v > 0:
        return f"+{v:,.2f}%"
    return f"{v:,.2f}%"


def _fmt_mwh(v: float) -> str:
    return f"{v / 1000.0:,.2f}"


def _con_subindice_co2(texto: str) -> str:
    """Subíndice tipográfico en ReportLab (Helvetica no incluye el Unicode ₂)."""
    return str(texto).replace("CO₂", "CO<sub>2</sub>").replace("CO2", "CO<sub>2</sub>")


def generar_emisiones_pdf_bytes(datos: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    page_w, _page_h = letter
    left_m = 0.55 * inch
    right_m = 0.55 * inch
    cw = page_w - left_m - right_m
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=left_m,
        rightMargin=right_m,
        topMargin=0.45 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = _pdf_styles()
    story = []
    archivos_temp: list = []

    estilo_celda = ParagraphStyle(
        "EmCelda",
        fontSize=8,
        fontName="Helvetica",
        textColor=colors.HexColor(_PDF["text_dark"]),
        alignment=TA_RIGHT,
        leading=10,
    )
    estilo_celda_izq = ParagraphStyle(
        "EmCeldaIzq",
        parent=estilo_celda,
        alignment=TA_LEFT,
    )
    estilo_th = ParagraphStyle(
        "EmTh",
        fontSize=7.5,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
        leading=9,
    )

    def _P(texto: str, estilo=None):
        return Paragraph(_con_subindice_co2(texto), estilo or styles["PdfSection"])

    def _cell(texto: str, *, header: bool = False, left: bool = False):
        if header:
            return Paragraph(_con_subindice_co2(str(texto)), estilo_th)
        est = estilo_celda_izq if left else estilo_celda
        return Paragraph(_con_subindice_co2(str(texto)), est)

    logo_path = buscar_logo()
    logo_flow = _pdf_guardar_logo(logo_path, archivos_temp) if logo_path else None

    titulo = _P("Reporte de emisiones CO2", styles["PdfTitle"])
    sub = _P(
        f"{datos['subestacion_nombre']} · "
        f"Mes al {formatear_fecha_espanol(datos['fecha'])}<br/>"
        f"EF: Base {FACTORES_EMISION['base']:.2f} / "
        f"Inter {FACTORES_EMISION['intermedio']:.2f} / "
        f"Punta {FACTORES_EMISION['punta']:.2f} kg CO2/kWh",
        styles["PdfSubtitle"],
    )
    if logo_flow:
        logo_col = 1.4 * inch
        cab = Table(
            [
                [logo_flow, titulo],
                ["", sub],
            ],
            colWidths=[logo_col, cw - logo_col],
        )
        cab.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (0, -1), "MIDDLE"),
                    ("VALIGN", (1, 0), (1, -1), "BOTTOM"),
                    ("SPAN", (0, 0), (0, 1)),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, 0), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                    ("TOPPADDING", (0, 1), (-1, 1), 2),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
                ]
            )
        )
        story.append(cab)
    else:
        story.append(titulo)
        story.append(Spacer(1, 4))
        story.append(sub)

    linea = Table([[""]], colWidths=[cw], rowHeights=[2])
    linea.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_PDF["primary"])),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(Spacer(1, 0.04 * inch))
    story.append(linea)
    story.append(Spacer(1, 0.08 * inch))

    estilo_lbl = ParagraphStyle(
        "EmLbl",
        fontSize=7.5,
        fontName="Helvetica",
        textColor=colors.HexColor(_PDF["text_muted"]),
        alignment=TA_CENTER,
        leading=9,
    )
    estilo_val = ParagraphStyle(
        "EmVal",
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor(_PDF["text_dark"]),
        alignment=TA_CENTER,
        leading=13,
    )
    estilo_nota = ParagraphStyle(
        "EmNota",
        fontSize=7.5,
        fontName="Helvetica",
        textColor=colors.HexColor(_PDF["text_muted"]),
        alignment=TA_LEFT,
        leading=9,
    )

    def _kpi(lbl: str, val: str, color: str):
        t = Table(
            [
                [Paragraph(_con_subindice_co2(lbl), estilo_lbl)],
                [Paragraph(_con_subindice_co2(val), estilo_val)],
            ],
            colWidths=["*"],
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(_PDF["border"])),
                    ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor(color)),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return t

    def _tabla(rows, col_w):
        flow_rows = []
        for i, row in enumerate(rows):
            flow_rows.append(
                [
                    _cell(c, header=(i == 0), left=(j == 0))
                    for j, c in enumerate(row)
                ]
            )
        tbl = Table(flow_rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_PDF["primary"])),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(_PDF["border"])),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(_PDF["bg_light"])),
                ]
            )
        )
        return tbl

    # --- 1. Comparacion ---
    story.append(Paragraph("1. Comparacion Con BESS vs Sin BESS", styles["PdfSection"]))
    story.append(Spacer(1, 4))

    kpis = []
    if datos.get("tiene_sin_bess") and datos.get("co2_sin_t") is not None:
        kpis.append(
            _kpi("Huella Sin BESS", f"{_fmt_t(datos['co2_sin_t'])} t CO2", _PDF["punta"])
        )
    kpis.append(
        _kpi("Huella Con BESS", f"{_fmt_t(datos['co2_con_t'])} t CO2", _PDF["secondary"])
    )
    if datos.get("tiene_sin_bess") and datos.get("ahorro_bess_t") is not None:
        ahorro = datos["ahorro_bess_t"]
        pct = datos.get("ahorro_bess_pct")
        color_ah = _PDF["success"] if ahorro >= 0 else _PDF["punta"]
        pct_txt = f" ({_fmt_pct(pct, con_signo=True)})" if pct is not None else ""
        kpis.append(
            _kpi(
                "Efecto BESS (Sin - Con)",
                f"{_fmt_t(ahorro, con_signo=True)} t CO2{pct_txt}",
                color_ah,
            )
        )

    n = len(kpis)
    w = (7.2 * inch) / n
    story.append(Table([kpis], colWidths=[w] * n))
    story.append(Spacer(1, 8))

    headers = [
        "Periodo",
        "EF",
        "CO2 Sin BESS (t)",
        "CO2 Con BESS (t)",
        "Ahorro (t)",
        "Ahorro (%)",
    ]
    rows = [headers]
    for fila in datos["por_periodo"]:
        rows.append(
            [
                fila["etiqueta"],
                f"{fila['ef_kg_kwh']:.2f}",
                _fmt_t(fila.get("co2_sin_t")) if datos.get("tiene_sin_bess") else "-",
                _fmt_t(fila["co2_con_t"]),
                _fmt_t(fila.get("ahorro_t"), con_signo=True)
                if datos.get("tiene_sin_bess")
                else "-",
                _fmt_pct(fila.get("ahorro_pct"), con_signo=True)
                if datos.get("tiene_sin_bess")
                else "-",
            ]
        )
    rows.append(
        [
            "Total",
            "-",
            _fmt_t(datos.get("co2_sin_t")) if datos.get("tiene_sin_bess") else "-",
            _fmt_t(datos["co2_con_t"]),
            _fmt_t(datos.get("ahorro_bess_t"), con_signo=True)
            if datos.get("tiene_sin_bess")
            else "-",
            _fmt_pct(datos.get("ahorro_bess_pct"), con_signo=True)
            if datos.get("tiene_sin_bess")
            else "-",
        ]
    )
    story.append(
        _tabla(
            rows,
            [1.0 * inch, 0.55 * inch, 1.25 * inch, 1.25 * inch, 1.05 * inch, 1.0 * inch],
        )
    )
    story.append(Spacer(1, 10))

    # --- 2. Generacion ---
    story.append(Paragraph("2. Generacion local", styles["PdfSection"]))
    story.append(Spacer(1, 4))
    if datos.get("tiene_generacion"):
        etiq = datos.get("generacion_etiqueta") or "Generacion"
        tipo = datos.get("generacion_tipo")
        if tipo == "gas":
            gen_kpis = [
                _kpi(
                    f"Energia · {etiq}",
                    f"{_fmt_mwh(datos['total_generacion_kwh'])} MWh",
                    _PDF["success"],
                ),
                _kpi(
                    "Si viniera de la red",
                    f"{_fmt_t(datos['co2_gen_desplazado_t'])} t CO2",
                    _PDF["secondary"],
                ),
                _kpi(
                    "Cogen (EF plano)",
                    f"{_fmt_t(datos['co2_gen_local_t'])} t CO2",
                    _PDF["punta"],
                ),
                _kpi(
                    "Beneficio neto vs red",
                    (
                        f"{_fmt_t(datos['co2_gen_neto_t'])} t CO2"
                        + (
                            f" ({_fmt_pct(datos.get('co2_gen_neto_pct'), con_signo=True)})"
                            if datos.get("co2_gen_neto_pct") is not None
                            else ""
                        )
                    ),
                    _PDF["success"],
                ),
            ]
            story.append(Table([gen_kpis], colWidths=[1.8 * inch] * 4))
            story.append(Spacer(1, 4))
            story.append(
                Paragraph(
                    _con_subindice_co2(
                        f"{etiq}: emisiones locales con escenario plano "
                        f"({EF_GAS_PLANO_KG_KWH:.2f} kg CO2/kWh) vs emisiones de red Marcado "
                        f"(Base {FACTORES_EMISION['base']:.2f} / "
                        f"Inter {FACTORES_EMISION['intermedio']:.2f} / "
                        f"Punta {FACTORES_EMISION['punta']:.2f}) si esos kWh se tomaran de la red. "
                        "Beneficio neto = CO2 red - CO2 gas plano; "
                        "% = beneficio / CO2 si viniera de la red."
                    ),
                    estilo_nota,
                )
            )
        else:
            gen_kpis = [
                _kpi(
                    f"Energia · {etiq}",
                    f"{_fmt_mwh(datos['total_generacion_kwh'])} MWh",
                    _PDF["success"],
                ),
                _kpi(
                    "CO2 red desplazado (neto)",
                    f"{_fmt_t(datos['co2_gen_neto_t'])} t",
                    _PDF["success"],
                ),
            ]
            story.append(Table([gen_kpis], colWidths=[3.6 * inch, 3.6 * inch]))
            story.append(Spacer(1, 4))
            story.append(
                Paragraph(
                    f"{etiq}: beneficio = kWh que dejan de importarse de la red "
                    "al EF Marcado del periodo (sin emisiones locales de combustion).",
                    estilo_nota,
                )
            )
    else:
        story.append(Paragraph("Sin recurso de generacion en esta subestacion.", estilo_nota))
    story.append(Spacer(1, 10))

    # --- 3. Energia ---
    story.append(Paragraph("3. Balance energetico (kWh)", styles["PdfSection"]))
    story.append(Spacer(1, 4))
    gen_col = datos.get("generacion_etiqueta") or "Generacion"
    headers_e = ["Periodo", "Sin BESS", "Con BESS", gen_col]
    rows_e = [headers_e]
    for fila in datos["por_periodo"]:
        rows_e.append(
            [
                fila["etiqueta"],
                _fmt_kwh(fila.get("consumo_sin_kwh", 0)) if datos.get("tiene_sin_bess") else "-",
                _fmt_kwh(fila["consumo_con_kwh"]),
                _fmt_kwh(fila["generacion_kwh"]),
            ]
        )
    rows_e.append(
        [
            "Total",
            _fmt_kwh(datos.get("total_consumo_sin_kwh") or 0)
            if datos.get("tiene_sin_bess")
            else "-",
            _fmt_kwh(datos["total_consumo_con_kwh"]),
            _fmt_kwh(datos["total_generacion_kwh"]),
        ]
    )
    story.append(_tabla(rows_e, [1.4 * inch, 1.7 * inch, 1.7 * inch, 2.0 * inch]))
    story.append(Spacer(1, 10))

    # --- 4. Factores y cita ---
    story.append(Paragraph("4. Factores de emision y fuente", styles["PdfSection"]))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            _con_subindice_co2(
                f"Base {FACTORES_EMISION['base']:.2f} · "
                f"Intermedio {FACTORES_EMISION['intermedio']:.2f} · "
                f"Punta {FACTORES_EMISION['punta']:.2f} kg CO2/kWh."
            ),
            estilo_nota,
        )
    )
    story.append(Spacer(1, 3))
    story.append(
        Paragraph(
            _con_subindice_co2(datos.get("cita_factores") or CITA_FACTORES_EMISION),
            estilo_nota,
        )
    )
    story.append(Spacer(1, 6))
    nota = (
        "Efecto BESS = huella Sin BESS - Con BESS (positivo = menos emisiones con bateria). "
        "Ahorro % = efecto BESS / huella Sin BESS x 100. "
        "Huella Scope 2 = suma (kWh x kg CO2/kWh) / 1000."
    )
    if datos.get("netmetering"):
        nota += " Consumo Con BESS = REC - ENT (netmetering)."
    story.append(Paragraph(_con_subindice_co2(nota), estilo_nota))

    def _pie(canvas, _doc):
        _pdf_dibujar_pie(canvas, _doc)

    doc.build(story, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()
