"""Reporte acumulado BESS en PDF."""

from __future__ import annotations

from datetime import datetime

from bess.config import rutas as rutas_mod
from bess.config.subestaciones import medidor_consumo_por_prefijo
from bess.core.console import log
from bess.reports.accumulated import ReporteAcumuladoError, calcular_reporte_acumulado
from bess.reports.assets import buscar_logo
from bess.reports.daily_pdf import (
    _PDF,
    _pdf_dibujar_pie,
    _pdf_grafica_perfil,
    _pdf_guardar_logo,
    _pdf_styles,
)
from bess.reports.dia_tipo import cargar_perfil_dia, titulo_dia_tipo

print = log


def _pdf_celda_metrica(etiqueta: str, valor: str, subtitulo: str, color: str):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    estilo_lbl = ParagraphStyle(
        "MetricLbl", fontSize=7.5, fontName="Helvetica",
        textColor=colors.HexColor(_PDF["text_muted"]), alignment=TA_CENTER, leading=9,
    )
    estilo_val = ParagraphStyle(
        "MetricVal", fontSize=11, fontName="Helvetica-Bold",
        textColor=colors.HexColor(_PDF["text_dark"]), alignment=TA_CENTER, leading=13,
    )
    estilo_sub = ParagraphStyle(
        "MetricSub", fontSize=6.5, fontName="Helvetica",
        textColor=colors.HexColor(_PDF["text_muted"]), alignment=TA_CENTER, leading=8,
    )
    tbl = Table(
        [[Paragraph(etiqueta, estilo_lbl)], [Paragraph(valor, estilo_val)], [Paragraph(subtitulo, estilo_sub)]],
        colWidths=["*"],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(_PDF["border"])),
        ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor(color)),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _pdf_tarjetas_demanda(kw: int, mxn: float, disponible: bool):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import inch

    if not disponible:
        return None
    cw = _PDF["content_width_in"] * inch
    mitad = cw * 0.5
    kw_tbl = _pdf_celda_metrica(
        "Reducción de demanda BESS",
        f"{kw:,}",
        "kW (Shapley)",
        _PDF["primary"],
    )
    mxn_tbl = _pdf_celda_metrica(
        "Ahorro en demanda",
        f"${mxn:,.2f}",
        "MXN",
        _PDF["primary"],
    )
    bloque = Table([[kw_tbl, mxn_tbl]], colWidths=[mitad - 4, mitad - 4], hAlign="LEFT")
    bloque.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return bloque


def _pdf_tarjetas_operacion(datos: dict):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import inch

    cw = _PDF["content_width_in"] * inch
    col_w = (cw - 12) / 4
    celdas = [
        _pdf_celda_metrica(
            "Energía cargada",
            f"{datos['carga_total_kwh']:,}",
            "kWh acumulados",
            _PDF["carga"],
        ),
        _pdf_celda_metrica(
            "Energía descargada",
            f"{datos['descarga_total_kwh']:,}",
            "kWh acumulados",
            _PDF["descarga"],
        ),
        _pdf_celda_metrica(
            "Ahorro por arbitraje",
            f"${datos['arbitraje_mxn']:,.2f}",
            "MXN acumulado",
            "#f39c12",
        ),
        _pdf_celda_metrica(
            "Ahorro total del mes",
            f"${datos['ahorro_total_mxn']:,.2f}",
            "Arbitraje + demanda",
            _PDF["success"],
        ),
    ]
    tbl = Table([celdas], colWidths=[col_w] * 4, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tbl


def generar_reporte_acumulado_pdf(fecha_corte, prefijo: str):
    """Genera PDF acumulado del mes a fecha_corte (date o str dd/mm/yyyy)."""
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch

        if isinstance(fecha_corte, str):
            fecha_dt = datetime.strptime(fecha_corte, "%d/%m/%Y")
            fecha = fecha_dt.date()
        else:
            fecha = fecha_corte
            fecha_dt = datetime.combine(fecha, datetime.min.time())

        med = medidor_consumo_por_prefijo(prefijo)
        if not med:
            return False, f"Medidor desconocido: {prefijo}"

        datos = calcular_reporte_acumulado(prefijo, fecha)
        nombre_archivo = rutas_mod.nombre_pdf_acumulado(med.nombre, fecha_dt)
        ruta_pdf = rutas_mod.ruta_pdf_diario(med.subestacion_nombre, nombre_archivo)
        ruta_pdf.parent.mkdir(parents=True, exist_ok=True)
        ruta_pdf = str(ruta_pdf)

        doc = SimpleDocTemplate(
            ruta_pdf,
            pagesize=landscape(letter),
            rightMargin=18,
            leftMargin=18,
            topMargin=14,
            bottomMargin=32,
        )
        styles = _pdf_styles()
        archivos_temp: list = []
        story = []

        logo_path = buscar_logo()
        subtitulo = (
            f"Acumulado al {fecha.strftime('%d/%m/%Y')} · "
            f"{datos['periodo_label']} · {datos['subestacion_nombre']}"
        )

        from reportlab.platypus import Paragraph as P

        titulo_custom = P("Reporte Acumulado BESS", styles["PdfTitle"])
        fecha_p = P(subtitulo, styles["PdfSubtitle"])
        ubicacion = P("Pastejé, Jocotitlán, Estado de México", styles["PdfSubtitle"])
        cw = _PDF["content_width_in"] * inch

        if logo_path:
            try:
                logo_img = _pdf_guardar_logo(logo_path, archivos_temp)
                info_cell = [[titulo_custom], [fecha_p], [ubicacion]]
                logo_col = _PDF["logo_col_in"] * inch
                info_tbl = Table(info_cell, colWidths=[cw - logo_col])
                info_tbl.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]))
                header = Table([[logo_img, info_tbl]], colWidths=[logo_col, cw - logo_col])
                header.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]))
                story.append(header)
            except Exception as e:
                print(f"Error al cargar logo: {e}")
                story.extend([titulo_custom, fecha_p, ubicacion])
        else:
            story.extend([titulo_custom, fecha_p, ubicacion])

        linea = Table([[""]], colWidths=[cw], rowHeights=[2])
        linea.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_PDF["primary"])),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(Spacer(1, 0.04 * inch))
        story.append(linea)
        story.append(Spacer(1, 0.10 * inch))

        dia_tipo = datos.get("dia_tipo")
        titulo_dt = titulo_dia_tipo(prefijo)
        if dia_tipo:
            df_dia = cargar_perfil_dia(prefijo, dia_tipo["fecha"])
            if not df_dia.empty:
                gen_txt = " · incluye generación" if dia_tipo.get("incluye_generacion") else ""
                story.append(Paragraph(
                    f"Carga {dia_tipo['carga_kwh']:,} kWh · "
                    f"Descarga {dia_tipo['descarga_kwh']:,} kWh{gen_txt}.",
                    styles["PdfSectionSub"],
                ))
                story.append(Spacer(1, 0.04 * inch))
                fecha_dt_dia = datetime.combine(dia_tipo["fecha"], datetime.min.time())
                story.append(_pdf_grafica_perfil(
                    df_dia,
                    prefijo,
                    fecha_dt_dia,
                    archivos_temp,
                    titulo=titulo_dt,
                ))
                story.append(Spacer(1, 0.12 * inch))

        tarjeta_dem = _pdf_tarjetas_demanda(
            datos["shapley_bess_kw"],
            datos["shapley_bess_mxn"],
            datos["shapley_disponible"],
        )
        if tarjeta_dem is not None:
            story.append(tarjeta_dem)
            story.append(Spacer(1, 0.08 * inch))

        story.append(_pdf_tarjetas_operacion(datos))

        doc.build(story, onFirstPage=_pdf_dibujar_pie, onLaterPages=_pdf_dibujar_pie)

        for temp in archivos_temp:
            try:
                import os
                os.remove(temp)
            except OSError:
                pass

        print(f"OK Reporte acumulado: {ruta_pdf}")
        return True, ruta_pdf

    except ReporteAcumuladoError as exc:
        return False, str(exc)
    except Exception as exc:
        print(f"Error reporte acumulado: {exc}")
        return False, str(exc)
