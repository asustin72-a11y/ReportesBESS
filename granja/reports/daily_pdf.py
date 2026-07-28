"""PDF diario Granja Solar (energía + tarifa DIST únicamente)."""

from __future__ import annotations

import io
import re
from datetime import date, datetime
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
from bess.reports.assets import buscar_logo, formatear_fecha_espanol

from granja.config import NOMBRE_APP
from granja.data.aggregates import ProgressCallback, acumulado_mes, perfil_potencia_dia, resumen_dia

# --- Sistema visual ---
_AZUL = "#1a5276"
_AZUL_SUAVE = "#2e86c1"
_SLATE = "#334155"
_MUTED = "#64748b"
_BORDE = "#e2e8f0"
_FONDO_CARD = "#f8fafc"
_AMARILLO = "#EAB308"
_AMARILLO_BORDE = "#CA8A04"
_AMARILLO_TXT = "#A16207"
_CIELO = "#38BDF8"
_CIELO_BORDE = "#0EA5E9"
_CIELO_TXT = "#0284C7"

_MARGEN_H = 1.15 * cm
_ANCHO_UTIL = letter[0] - 2 * _MARGEN_H
_ANCHO_GRAFICA = _ANCHO_UTIL * 0.84

# Paleta ordenada para 21 MEGAs (legible en impresión).
_COLORES_MEGA = (
    "#1a5276", "#2e86c1", "#38bdf8", "#0ea5e9", "#0284c7",
    "#eab308", "#f59e0b", "#f97316", "#ea580c", "#dc2626",
    "#16a34a", "#22c55e", "#84cc16", "#65a30d", "#0d9488",
    "#8b5cf6", "#a855f7", "#d946ef", "#ec4899", "#64748b",
    "#0f766e",
)


def _fmt_mxn(valor: float) -> str:
    """Vista: MXN a entero half-up, igual que kWh."""
    return f"${redondear_kwh(valor):,}"


def _fmt_precio(valor: float) -> str:
    return f"{float(valor):.4f}"


def _num_mega(etiq: str) -> int:
    m = re.search(r"(\d+)", str(etiq))
    return int(m.group(1)) if m else 999


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "marca": ParagraphStyle(
            "MarcaGranja",
            parent=base["Normal"],
            fontSize=11,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor(_AZUL),
            alignment=TA_LEFT,
            leading=13,
        ),
        "fecha_hdr": ParagraphStyle(
            "FechaHdr",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor(_MUTED),
            alignment=TA_RIGHT,
            leading=10,
        ),
        "card_label": ParagraphStyle(
            "CardLabel",
            parent=base["Normal"],
            fontSize=5.5,
            textColor=colors.HexColor(_MUTED),
            alignment=TA_LEFT,
            leading=7,
        ),
        "card_value": ParagraphStyle(
            "CardValue",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor(_SLATE),
            alignment=TA_LEFT,
            leading=12,
        ),
        "card_sub": ParagraphStyle(
            "CardSub",
            parent=base["Normal"],
            fontSize=6,
            textColor=colors.HexColor("#94a3b8"),
            alignment=TA_LEFT,
            leading=7,
        ),
        "aviso": ParagraphStyle(
            "Aviso",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#94a3b8"),
            alignment=TA_LEFT,
        ),
    }


def _card(label: str, value: str, sub: str, color: str, ancho: float, estilos: dict) -> Table:
    """KPI con acento izquierdo y fondo suave."""
    filas = [
        [Paragraph(label.upper(), estilos["card_label"])],
        [Paragraph(value, estilos["card_value"])],
    ]
    if sub:
        filas.append([Paragraph(sub, estilos["card_sub"])])
    t = Table(filas, colWidths=[ancho])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_FONDO_CARD)),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(_BORDE)),
            ("LINEBEFORE", (0, 0), (0, -1), 2.8, colors.HexColor(color)),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (0, 0), 5),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -2), 0),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    return t


def _fila_cards(items: list[tuple[str, str, str, str]], estilos: dict) -> Table:
    n = len(items)
    gap = 0.18 * cm
    ancho = (_ANCHO_UTIL - gap * (n - 1)) / n
    celdas = [_card(lab, val, sub, col, ancho, estilos) for lab, val, sub, col in items]
    # Separación visual entre cards vía tabla con huecos
    fila_datos: list = []
    anchos: list[float] = []
    for i, cel in enumerate(celdas):
        if i:
            fila_datos.append("")
            anchos.append(gap)
        fila_datos.append(cel)
        anchos.append(ancho)
    fila = Table([fila_datos], colWidths=anchos)
    fila.setStyle(
        TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    return fila


def _encabezado(fecha_txt: str, estilos: dict) -> list:
    """Logo + marca + fecha en una franja con línea de acento."""
    elementos: list = []
    logo = buscar_logo()
    logo_cell: Image | str = ""
    if logo:
        try:
            logo_cell = Image(logo, width=3.1 * cm, height=1.05 * cm)
        except Exception:
            logo_cell = ""

    derecha = Table(
        [
            [Paragraph(NOMBRE_APP, estilos["marca"])],
            [Paragraph(f"Reporte diario · {fecha_txt}", estilos["fecha_hdr"])],
        ],
        colWidths=[_ANCHO_UTIL - 3.4 * cm],
    )
    derecha.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ])
    )

    hdr = Table(
        [[logo_cell, derecha]],
        colWidths=[3.4 * cm, _ANCHO_UTIL - 3.4 * cm],
    )
    hdr.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 1.6, colors.HexColor(_AZUL)),
        ])
    )
    elementos.append(hdr)
    elementos.append(Spacer(1, 0.28 * cm))
    return elementos


def _fig_a_imagen(fig, *, alto_cm: float) -> Table:
    """Exporta la figura a imagen centrada y con ancho reducido."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight", pad_inches=0.08)
    import matplotlib.pyplot as plt

    plt.close(fig)
    buf.seek(0)
    img = Image(buf, width=_ANCHO_GRAFICA, height=alto_cm * cm)
    wrap = Table([[img]], colWidths=[_ANCHO_UTIL])
    wrap.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(_BORDE)),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    return wrap


def _estilo_ejes(ax) -> None:
    ax.set_facecolor(_FONDO_CARD)
    ax.tick_params(colors=_MUTED, labelsize=6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(_BORDE)
    ax.spines["bottom"].set_color(_BORDE)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, linestyle=":", linewidth=0.5, color="#cbd5e1")
    ax.set_axisbelow(True)


def _grafica_energia_ingreso_megas(detalle, titulo: str) -> Table | None:
    """Barras horizontales: energía (amarillo) e ingreso (azul cielo)."""
    if detalle is None or getattr(detalle, "empty", True):
        return None

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    etiquetas = [str(x) for x in detalle["etiqueta"].tolist()]
    energia = [float(redondear_kwh(v)) for v in detalle["Total"].tolist()]
    ingreso = [float(redondear_kwh(v)) for v in detalle["Ingreso_Total"].tolist()]
    if not energia:
        return None

    # Orden ascendente por número de MEGA
    pares = sorted(
        zip(etiquetas, energia, ingreso),
        key=lambda t: _num_mega(t[0]),
    )
    etiquetas, energia, ingreso = map(list, zip(*pares))

    y = np.arange(len(etiquetas))
    alto_barra = 0.36

    fig, ax1 = plt.subplots(figsize=(7.6, 9.2), facecolor="white", dpi=140)
    _estilo_ejes(ax1)
    b1 = ax1.barh(
        y - alto_barra / 2,
        energia,
        height=alto_barra,
        color=_AMARILLO,
        edgecolor=_AMARILLO_BORDE,
        linewidth=0.35,
        label="Energía (kWh)",
        zorder=3,
    )
    ax1.set_xlabel("kWh", fontsize=7, color=_AMARILLO_TXT, labelpad=4, fontweight="bold")
    ax1.tick_params(axis="x", labelsize=6, colors=_AMARILLO_TXT)
    ax1.set_yticks(y)
    ax1.set_yticklabels(etiquetas, fontsize=6.5, color=_SLATE)
    ax1.invert_yaxis()

    ax2 = ax1.twiny()
    ax2.set_facecolor("none")
    b2 = ax2.barh(
        y + alto_barra / 2,
        ingreso,
        height=alto_barra,
        color=_CIELO,
        edgecolor=_CIELO_BORDE,
        linewidth=0.35,
        label="Ingreso (MXN)",
        zorder=3,
    )
    ax2.set_xlabel("MXN", fontsize=7, color=_CIELO_TXT, labelpad=4, fontweight="bold")
    ax2.tick_params(axis="x", labelsize=6, colors=_CIELO_TXT, pad=1)
    ax2.spines["top"].set_color(_CIELO_TXT)
    ax2.spines["right"].set_visible(False)
    ax2.spines["left"].set_visible(False)
    ax2.spines["bottom"].set_visible(False)
    ax1.spines["bottom"].set_color(_AMARILLO_TXT)

    fig.suptitle(titulo, fontsize=9, color=_AZUL, fontweight="bold", y=0.988)
    fig.legend(
        [b1, b2],
        ["Energía (kWh)", "Ingreso (MXN)"],
        loc="upper center",
        bbox_to_anchor=(0.52, 0.958),
        ncol=2,
        fontsize=7,
        frameon=True,
        fancybox=False,
        edgecolor=_BORDE,
        framealpha=1.0,
        facecolor="white",
        columnspacing=1.8,
        handlelength=1.6,
        borderpad=0.45,
    )
    fig.subplots_adjust(left=0.14, right=0.97, top=0.86, bottom=0.06)
    return _fig_a_imagen(fig, alto_cm=11.6)


def _grafica_perfil_potencia(dia: date) -> Table | None:
    """Perfil de potencia estimado (MW) por cada MEGA."""
    pot = perfil_potencia_dia(dia)
    if pot is None or pot.empty:
        return None

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    pot = pot.copy()
    pot["mw"] = pot["kw"] / 1000.0
    pot["etiqueta"] = pot["etiqueta"].astype(str)
    pot["_ord"] = pot["etiqueta"].map(_num_mega)
    pot = pot.sort_values(["_ord", "fecha"])

    fig, ax = plt.subplots(figsize=(7.6, 4.5), facecolor="white", dpi=140)
    _estilo_ejes(ax)
    ax.xaxis.grid(True, linestyle=":", linewidth=0.5, color="#cbd5e1")
    ax.yaxis.grid(True, linestyle=":", linewidth=0.5, color="#cbd5e1")

    etiquetas = sorted(pot["etiqueta"].unique().tolist(), key=_num_mega)
    for i, etiq in enumerate(etiquetas):
        serie = pot.loc[pot["etiqueta"] == etiq].sort_values("fecha")
        ax.plot(
            serie["fecha"],
            serie["mw"],
            color=_COLORES_MEGA[i % len(_COLORES_MEGA)],
            linewidth=1.15,
            label=etiq,
            alpha=0.92,
        )

    ymax = float(pot["mw"].max()) if len(pot) else 1.0
    ax.set_ylim(0, max(ymax * 1.12, 0.1))
    ax.set_ylabel("MW", fontsize=7, color=_MUTED, fontweight="bold")
    ax.set_title(
        "Perfil de potencia estimado (MW) — Por MEGA",
        fontsize=8.5,
        color=_AZUL,
        pad=6,
        fontweight="bold",
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.tick_params(axis="x", labelsize=6)
    ax.tick_params(axis="y", labelsize=6)

    handles, labels = ax.get_legend_handles_labels()
    orden = sorted(range(len(labels)), key=lambda i: _num_mega(labels[i]))
    ax.legend(
        [handles[i] for i in orden],
        [labels[i] for i in orden],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=7,
        fontsize=5,
        frameon=False,
        columnspacing=0.9,
        handlelength=1.3,
        labelcolor=_SLATE,
    )
    fig.subplots_adjust(left=0.09, right=0.98, top=0.88, bottom=0.26)
    return _fig_a_imagen(fig, alto_cm=6.5)


def _texto_precios(precios: dict) -> str:
    return (
        f"Tarifa DIST  ·  Base ${_fmt_precio(precios.get('Base', 0))}   "
        f"Intermedio ${_fmt_precio(precios.get('Intermedio', 0))}   "
        f"Punta ${_fmt_precio(precios.get('Punta', 0))}  MXN/kWh"
    )


def _dibujar_pie(canvas, _doc, texto: str) -> None:
    canvas.saveState()
    y = 0.7 * cm
    # Barra de acento
    canvas.setFillColor(colors.HexColor(_AZUL))
    canvas.rect(_MARGEN_H, y + 0.42 * cm, _ANCHO_UTIL, 0.06 * cm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(colors.HexColor(_MUTED))
    canvas.drawCentredString(letter[0] / 2, y, texto)
    canvas.setFont("Helvetica", 5.5)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.drawRightString(letter[0] - _MARGEN_H, y, "IUSASOL")
    canvas.restoreState()


def generar_pdf_diario(
    dia: date | datetime | str,
    *,
    ruta_salida: Path | None = None,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """
    Genera el reporte PDF del día en una sola página: KPIs, gráfica
    energía/ingreso por MEGA, perfil de potencia y precios DIST en el pie.
    """
    def _p(step: int, total: int, label: str) -> None:
        if on_progress is not None:
            on_progress(step, total, label)

    total_pasos = 5
    _p(0, total_pasos, "Calculando energía e ingresos…")

    if isinstance(dia, str):
        dia_d = date.fromisoformat(dia[:10])
    elif isinstance(dia, datetime):
        dia_d = dia.date()
    else:
        dia_d = dia

    resumen = resumen_dia(dia_d)
    _p(1, total_pasos, "Acumulado del mes…")
    acum = acumulado_mes(dia_d)
    detalle = resumen["detalle"]
    precios = resumen.get("precios") or {}

    DIRECTORIO_REPORTES_DIARIOS.mkdir(parents=True, exist_ok=True)
    if ruta_salida is None:
        ruta_salida = (
            DIRECTORIO_REPORTES_DIARIOS
            / f"Reporte_Granja_{dia_d.strftime('%d_%m_%y')}.pdf"
        )

    estilos = _estilos()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=_MARGEN_H,
        rightMargin=_MARGEN_H,
        topMargin=0.65 * cm,
        bottomMargin=1.35 * cm,
    )

    fecha_txt = formatear_fecha_espanol(datetime.combine(dia_d, datetime.min.time()))
    story: list = []
    story.extend(_encabezado(fecha_txt, estilos))

    kpis = [
        ("Energía del periodo", fmt_kwh(resumen["energia_total"]), "kWh", _AZUL),
        ("Ingreso del periodo", _fmt_mxn(resumen["ingreso_total"]), "MXN", "#0e9f6e"),
        ("Energía mes (acum.)", fmt_kwh(acum["energia_kwh"]), "kWh", _AZUL_SUAVE),
        ("Ingreso mes (acum.)", _fmt_mxn(acum["ingreso_mxn"]), "MXN", "#059669"),
    ]
    story.append(_fila_cards(kpis, estilos))
    story.append(Spacer(1, 0.22 * cm))

    story.append(Spacer(1, 0.32 * cm))
    periodos = [
        (
            "Base",
            f"{fmt_kwh(resumen['energia_base'])} kWh",
            _fmt_mxn(resumen["ingreso_base"]),
            "#3498db",
        ),
        (
            "Intermedio",
            f"{fmt_kwh(resumen['energia_intermedio'])} kWh",
            _fmt_mxn(resumen["ingreso_intermedio"]),
            "#f39c12",
        ),
        (
            "Punta",
            f"{fmt_kwh(resumen['energia_punta'])} kWh",
            _fmt_mxn(resumen["ingreso_punta"]),
            "#e74c3c",
        ),
    ]
    story.append(_fila_cards(periodos, estilos))
    story.append(Spacer(1, 0.4 * cm))

    _p(2, total_pasos, "Gráfica energía e ingreso…")
    graf = _grafica_energia_ingreso_megas(
        detalle,
        f"Energía e ingreso por MEGA  ·  {fecha_txt}",
    )
    if graf is not None:
        story.append(graf)
    else:
        story.append(Paragraph("Sin datos de energía/ingreso para graficar.", estilos["aviso"]))
    story.append(Spacer(1, 0.22 * cm))

    _p(3, total_pasos, "Perfil de potencia…")
    perfil = _grafica_perfil_potencia(dia_d)
    if perfil is not None:
        story.append(perfil)
    else:
        story.append(Paragraph("Sin datos de perfil de potencia.", estilos["aviso"]))

    pie_txt = _texto_precios(precios)

    def _on_page(canvas, doc_):
        _dibujar_pie(canvas, doc_, pie_txt)

    _p(4, total_pasos, "Escribiendo PDF…")
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    ruta_salida.write_bytes(buffer.getvalue())
    _p(total_pasos, total_pasos, "PDF listo")
    return ruta_salida
