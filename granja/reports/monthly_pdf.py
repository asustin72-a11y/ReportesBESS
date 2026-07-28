"""PDF mensual Granja Solar: comparativo por años (ingresos o energía)."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from bess.config.paths import DIRECTORIO_REPORTES_DIARIOS
from bess.core.numbers import fmt_kwh, redondear_kwh
from bess.reports.assets import buscar_logo

from granja.config import NOMBRE_APP
from granja.data.aggregates import (
    ProgressCallback,
    energia_mensuales_por_anio,
    ingresos_mensuales_por_anio,
)

_AZUL = "#1a5276"
_MUTED = "#64748b"
_BORDE = "#e2e8f0"
_MARGEN_H = 1.3 * cm
_ANCHO_UTIL = letter[0] - 2 * _MARGEN_H

_COLORES_ANIO = (
    "#2E86C1",
    "#E74C3C",
    "#27AE60",
    "#8E44AD",
    "#F39C12",
    "#16A085",
    "#C0392B",
    "#2980B9",
)


def _fmt_mxn(valor: float) -> str:
    return f"${redondear_kwh(valor):,}"


def _fmt_energia(valor: float) -> str:
    return f"{fmt_kwh(valor)}"


def _color_anio(idx: int) -> str:
    return _COLORES_ANIO[idx % len(_COLORES_ANIO)]


def _grafica_barras_mensual(
    tabla,
    anios: list[int],
    *,
    ylabel: str,
    formatear_eje_y: Callable[[float], str],
) -> Image | None:
    if not anios:
        return None

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    meses = [str(m) for m in tabla["Mes"].tolist()]
    x = np.arange(len(meses))
    n = len(anios)
    ancho = min(0.8 / max(n, 1), 0.22)

    fig, ax = plt.subplots(figsize=(10.5, 4.2), facecolor="white", dpi=140)
    ax.set_facecolor("white")
    for i, anio in enumerate(anios):
        col = str(anio)
        valores = [float(v) for v in tabla[col].tolist()]
        offset = (i - (n - 1) / 2) * ancho
        ax.bar(
            x + offset,
            valores,
            width=ancho,
            color=_color_anio(i),
            label=str(anio),
            edgecolor="white",
            linewidth=0.2,
        )

    ax.set_ylabel(ylabel, fontsize=9, color="#334155")
    ax.set_xlabel("Mes", fontsize=9, color="#334155")
    ax.set_xticks(x)
    ax.set_xticklabels(meses, rotation=35, ha="right", fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: formatear_eje_y(float(v)))
    )
    ax.yaxis.grid(True, linestyle=":", linewidth=0.5, color="#cbd5e1")
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.12),
        ncol=min(n, 6),
        fontsize=8,
        frameon=False,
    )
    fig.subplots_adjust(left=0.10, right=0.98, top=0.86, bottom=0.22)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=_ANCHO_UTIL, height=7.2 * cm)


def _encabezado(titulo: str, estilos: dict) -> Table:
    logo = buscar_logo()
    logo_cell: Image | str = ""
    if logo:
        try:
            logo_cell = Image(logo, width=3.2 * cm, height=1.1 * cm)
        except Exception:
            logo_cell = ""

    titulo_p = Paragraph(titulo, estilos["titulo"])
    sub = Paragraph(NOMBRE_APP, estilos["sub"])
    izq = Table([[titulo_p], [sub]], colWidths=[_ANCHO_UTIL - 3.6 * cm])
    izq.setStyle(
        TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    hdr = Table([[izq, logo_cell]], colWidths=[_ANCHO_UTIL - 3.6 * cm, 3.6 * cm])
    hdr.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 1.4, colors.HexColor(_AZUL)),
        ])
    )
    return hdr


def _prog(cb: ProgressCallback | None, step: int, total: int, label: str) -> None:
    if cb is not None:
        cb(step, total, label)


def _generar_pdf_comparativo(
    *,
    datos: dict,
    titulo: str,
    ylabel: str,
    formatear_valor: Callable[[float], str],
    formatear_eje_y: Callable[[float], str],
    pie_label: str,
    nombre_archivo: str,
    ruta_salida: Path | None,
    aviso_vacio: str,
    on_progress: ProgressCallback | None = None,
) -> Path:
    anios_sel = datos["anios"]
    tabla = datos["tabla"]
    totales = datos["totales"]
    total_acumulado = datos["total_acumulado"]

    total_pasos = 3
    _prog(on_progress, 0, total_pasos, "Preparando PDF…")

    DIRECTORIO_REPORTES_DIARIOS.mkdir(parents=True, exist_ok=True)
    if ruta_salida is None:
        etiqueta = (
            f"{min(anios_sel)}_{max(anios_sel)}" if anios_sel else "sin_datos"
        )
        ruta_salida = DIRECTORIO_REPORTES_DIARIOS / f"{nombre_archivo}_{etiqueta}.pdf"

    base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle(
            "TituloMensual",
            parent=base["Heading1"],
            fontSize=18,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1a202c"),
            alignment=TA_LEFT,
            spaceAfter=0,
            leading=20,
        ),
        "sub": ParagraphStyle(
            "SubMensual",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor(_MUTED),
            alignment=TA_LEFT,
            leading=10,
        ),
        "pie": ParagraphStyle(
            "PieMensual",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1a202c"),
            alignment=TA_LEFT,
            spaceBefore=8,
        ),
        "aviso": ParagraphStyle(
            "AvisoMensual",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor(_MUTED),
            alignment=TA_CENTER,
        ),
    }

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=_MARGEN_H,
        rightMargin=_MARGEN_H,
        topMargin=1.0 * cm,
        bottomMargin=1.2 * cm,
    )

    story: list = [_encabezado(titulo, estilos), Spacer(1, 0.35 * cm)]

    _prog(on_progress, 1, total_pasos, "Generando gráfica…")
    graf = _grafica_barras_mensual(
        tabla,
        anios_sel,
        ylabel=ylabel,
        formatear_eje_y=formatear_eje_y,
    )
    if graf is not None:
        story.append(graf)
        story.append(Spacer(1, 0.45 * cm))
    else:
        story.append(Paragraph(aviso_vacio, estilos["aviso"]))
        story.append(Spacer(1, 0.3 * cm))

    _prog(on_progress, 2, total_pasos, "Armando tabla y PDF…")
    encabezado = ["Mes"] + [str(a) for a in anios_sel]
    filas: list[list] = [encabezado]
    for _, row in tabla.iterrows():
        filas.append(
            [str(row["Mes"])]
            + [formatear_valor(float(row[str(a)])) for a in anios_sel]
        )
    if anios_sel:
        filas.append(
            ["Total"]
            + [formatear_valor(float(totales.get(a, 0.0))) for a in anios_sel]
        )

    n_cols = len(encabezado)
    ancho_mes = 2.6 * cm
    ancho_anio = (_ANCHO_UTIL - ancho_mes) / max(n_cols - 1, 1)
    col_widths = [ancho_mes] + [ancho_anio] * (n_cols - 1)

    t = Table(filas, colWidths=col_widths, repeatRows=1)
    estilo_tabla = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#334155")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(_BORDE)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -2 if anios_sel else -1),
            [colors.white, colors.HexColor("#f8fafc")],
        ),
    ]
    for i, anio in enumerate(anios_sel):
        estilo_tabla.append(
            ("TEXTCOLOR", (i + 1, 0), (i + 1, 0), colors.HexColor(_color_anio(i)))
        )
    if anios_sel:
        estilo_tabla.extend([
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef2f7")),
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor(_AZUL)),
        ])
    t.setStyle(TableStyle(estilo_tabla))
    story.append(t)
    story.append(Spacer(1, 0.45 * cm))
    story.append(
        Paragraph(
            f"{pie_label} = {formatear_valor(total_acumulado)}",
            estilos["pie"],
        )
    )
    story.append(
        Paragraph(
            f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle(
                "Gen",
                parent=estilos["sub"],
                alignment=TA_RIGHT,
                fontSize=7,
                spaceBefore=10,
            ),
        )
    )

    doc.build(story)
    ruta_salida.write_bytes(buffer.getvalue())
    _prog(on_progress, total_pasos, total_pasos, "PDF listo")
    return ruta_salida


def generar_pdf_mensual_ingresos(
    anios: list[int] | tuple[int, ...] | None = None,
    *,
    ruta_salida: Path | None = None,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """PDF Importe Acumulado: ingresos DIST mensuales por año."""
    # Progreso combinado: cálculo (pasos variables) + PDF (3 pasos)
    estado = {"base": 0, "calc_total": 1}

    def _wrap(step: int, total: int, label: str) -> None:
        estado["calc_total"] = max(total, 1)
        _prog(on_progress, step, estado["calc_total"] + 3, label)

    datos = ingresos_mensuales_por_anio(anios, on_progress=_wrap)
    base = estado["calc_total"]

    def _wrap_pdf(step: int, total: int, label: str) -> None:
        _prog(on_progress, base + step, base + 3, label)

    return _generar_pdf_comparativo(
        datos=datos,
        titulo="Importe Acumulado",
        ylabel="Importe (MN)",
        formatear_valor=lambda v: f"{_fmt_mxn(v)} MN",
        formatear_eje_y=lambda v: f"${v:,.0f}",
        pie_label="Importe Total Acumulado",
        nombre_archivo="Reporte_Granja_Mensual_Ingresos",
        ruta_salida=ruta_salida,
        aviso_vacio="Sin datos de ingreso para graficar.",
        on_progress=_wrap_pdf,
    )


def generar_pdf_mensual_energia(
    anios: list[int] | tuple[int, ...] | None = None,
    *,
    ruta_salida: Path | None = None,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """PDF Energía Acumulada: kWh mensuales por año."""
    estado = {"base": 0, "calc_total": 1}

    def _wrap(step: int, total: int, label: str) -> None:
        estado["calc_total"] = max(total, 1)
        _prog(on_progress, step, estado["calc_total"] + 3, label)

    datos = energia_mensuales_por_anio(anios, on_progress=_wrap)
    base = estado["calc_total"]

    def _wrap_pdf(step: int, total: int, label: str) -> None:
        _prog(on_progress, base + step, base + 3, label)

    return _generar_pdf_comparativo(
        datos=datos,
        titulo="Energía Acumulada",
        ylabel="Energía (kWh)",
        formatear_valor=lambda v: f"{_fmt_energia(v)} kWh",
        formatear_eje_y=lambda v: f"{v:,.0f}",
        pie_label="Energía Total Acumulada",
        nombre_archivo="Reporte_Granja_Mensual_Energia",
        ruta_salida=ruta_salida,
        aviso_vacio="Sin datos de energía para graficar.",
        on_progress=_wrap_pdf,
    )


def generar_pdf_mensual(
    anios: list[int] | tuple[int, ...] | None = None,
    *,
    ruta_salida: Path | None = None,
) -> Path:
    """Alias de compatibilidad: reporte mensual de ingresos."""
    return generar_pdf_mensual_ingresos(anios, ruta_salida=ruta_salida)
