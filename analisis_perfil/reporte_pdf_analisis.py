"""PDF de Análisis de Perfil: resumen de energía + gráficas."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_AZUL = colors.HexColor("#1a5276")
_AZUL2 = colors.HexColor("#2e86c1")
_TEXTO = colors.HexColor("#1a202c")
_MUTED = colors.HexColor("#64748b")
_BORDE = colors.HexColor("#e2e8f0")
_FONDO = colors.HexColor("#f8fafc")
_VERDE = colors.HexColor("#27ae60")
_NARANJA = colors.HexColor("#f39c12")


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "marca": ParagraphStyle(
            "MarcaAP",
            parent=base["Normal"],
            fontSize=11,
            fontName="Helvetica-Bold",
            textColor=_AZUL,
            alignment=TA_LEFT,
        ),
        "titulo": ParagraphStyle(
            "TituloAP",
            parent=base["Normal"],
            fontSize=16,
            fontName="Helvetica-Bold",
            textColor=_TEXTO,
            spaceAfter=6,
            alignment=TA_LEFT,
        ),
        "subtitulo": ParagraphStyle(
            "SubAP",
            parent=base["Normal"],
            fontSize=11,
            fontName="Helvetica-Bold",
            textColor=_AZUL,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "cuerpo": ParagraphStyle(
            "CuerpoAP",
            parent=base["Normal"],
            fontSize=9,
            textColor=_TEXTO,
            leading=12,
        ),
        "muted": ParagraphStyle(
            "MutedAP",
            parent=base["Normal"],
            fontSize=8,
            textColor=_MUTED,
            leading=10,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabelAP",
            parent=base["Normal"],
            fontSize=8,
            textColor=_MUTED,
            alignment=TA_CENTER,
        ),
        "metric_val": ParagraphStyle(
            "MetricValAP",
            parent=base["Normal"],
            fontSize=12,
            fontName="Helvetica-Bold",
            textColor=_TEXTO,
            alignment=TA_CENTER,
        ),
        "pie": ParagraphStyle(
            "PieAP",
            parent=base["Normal"],
            fontSize=7,
            textColor=_MUTED,
            alignment=TA_CENTER,
        ),
    }


def _fmt_kwh(v: float) -> str:
    return f"{float(v):,.1f} kWh"


def _bloques_metricas(resumen: dict) -> list[tuple[str, float, colors.Color]]:
    """Lista (etiqueta, total_kwh, color) según layout del resumen."""
    if resumen.get("layout") == "neteo":
        renglones = resumen["columnas"]["flujos"]["renglones"]
        colores = (_AZUL, _AZUL2, _NARANJA)
        return [
            (r["etiqueta"], float(r["valores"]["total"]), c)
            for r, c in zip(renglones, colores)
        ]
    if resumen.get("layout") == "bidireccional_3col":
        cf = resumen["columnas"]["consumo_facturado"]
        gen = resumen["columnas"]["generacion"]
        real = resumen["columnas"]["consumo_real"]
        entregada, recibida, neteo = cf["renglones"]
        generada = gen["renglones"][0]
        consumo_real = real["renglones"][0]
        return [
            (entregada["etiqueta"], float(entregada["valores"]["total"]), _AZUL),
            (recibida["etiqueta"], float(recibida["valores"]["total"]), _AZUL2),
            (generada["etiqueta"], float(generada["valores"]["total"]), _VERDE),
            (neteo["etiqueta"], float(neteo["valores"]["total"]), _NARANJA),
            (
                consumo_real["etiqueta"],
                float(consumo_real["valores"]["total"]),
                colors.HexColor("#e74c3c"),
            ),
        ]
    out: list[tuple[str, float, colors.Color]] = []
    for clave, bloque in resumen.get("flujos", {}).items():
        etiq = resumen.get("etiquetas", {}).get(clave, clave)
        color = _VERDE if resumen.get("servicio") == "generacion" else _AZUL
        out.append((etiq, float(bloque["total"]), color))
    return out


def _tabla_metricas(resumen: dict, styles: dict, ancho: float) -> Table:
    items = _bloques_metricas(resumen)
    if not items:
        return Table([[Paragraph("Sin métricas", styles["muted"])]])
    n = len(items)
    col_w = ancho / n
    fila_l = [
        Paragraph(etiq, styles["metric_label"]) for etiq, _, _ in items
    ]
    fila_v = [
        Paragraph(_fmt_kwh(val), styles["metric_val"]) for _, val, _ in items
    ]
    t = Table([fila_l, fila_v], colWidths=[col_w] * n)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, -1), _FONDO),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, _BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, (_, _, col) in enumerate(items):
        estilo.append(("LINEABOVE", (i, 0), (i, 0), 2.5, col))
    t.setStyle(TableStyle(estilo))
    return t


def _tabla_periodos(resumen: dict, styles: dict, ancho: float) -> Table | None:
    if not resumen.get("horaria"):
        return None
    from servicio_config import PERIODOS

    filas = [["Flujo", *PERIODOS, "Total"]]
    if resumen.get("layout") in ("bidireccional_3col", "neteo"):
        renglones = []
        for grupo in resumen["columnas"].values():
            renglones.extend(grupo["renglones"])
        for ren in renglones:
            vals = ren["valores"]
            filas.append(
                [
                    ren["etiqueta"],
                    *[
                        f"{vals['por_periodo'].get(p, 0.0):,.1f}"
                        for p in PERIODOS
                    ],
                    f"{vals['total']:,.1f}",
                ]
            )
    else:
        for clave, bloque in resumen.get("flujos", {}).items():
            etiq = resumen.get("etiquetas", {}).get(clave, clave)
            filas.append(
                [
                    etiq,
                    *[
                        f"{bloque['por_periodo'].get(p, 0.0):,.1f}"
                        for p in PERIODOS
                    ],
                    f"{bloque['total']:,.1f}",
                ]
            )
    if len(filas) <= 1:
        return None
    ncols = len(filas[0])
    col0 = ancho * 0.28
    resto = (ancho - col0) / (ncols - 1)
    t = Table(filas, colWidths=[col0] + [resto] * (ncols - 1))
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _FONDO]),
                ("GRID", (0, 0), (-1, -1), 0.4, _BORDE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _pares_precio(bloque: dict) -> list[tuple[str, float]]:
    precios = bloque.get("precios") or {}
    etiq = bloque.get("etiquetas_escalones") or ()
    if etiq:
        return [
            (str(nombre), float(precios[clave]))
            for clave, nombre in etiq
            if clave in precios
        ]
    return [(str(k).capitalize(), float(v)) for k, v in precios.items()]


def _filas_escalones(pago: dict, etiquetas) -> list[list[str]]:
    escalones = pago.get("escalones") or {}
    if not escalones:
        return []
    pares = etiquetas or tuple((k, str(k).capitalize()) for k in escalones)
    filas = []
    for clave, nombre in pares:
        esc = escalones.get(clave) or {}
        filas.append(
            [
                str(nombre),
                f"{float(esc.get('kwh', 0)):,.1f}",
                f"${float(esc.get('importe', 0)):,.2f}",
            ]
        )
    return filas


def _seccion_precios(bloque: dict, styles: dict, ancho: float) -> list:
    """Detalle de precios vigentes ($/kWh) + vigencia."""
    elems = []
    titulo = bloque.get("titulo_tarifa") or bloque.get("esquema") or "Tarifa"
    fecha = bloque.get("fecha_tarifa") or "—"
    elems.append(
        Paragraph(
            f"Tarifa vigente: <b>{titulo}</b> · {fecha}",
            styles["cuerpo"],
        )
    )
    pares = _pares_precio(bloque)
    if pares:
        filas = [["Concepto", "Precio ($/kWh)"]]
        for nombre, precio in pares:
            filas.append([nombre, f"${precio:.4f}"])
        t = Table(filas, colWidths=[ancho * 0.55, ancho * 0.45])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.4, _BORDE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _FONDO]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elems.append(Spacer(1, 4))
        elems.append(t)
    bloques = bloque.get("bloques_kwh")
    if bloques:
        elems.append(
            Paragraph(
                f"Bloques: básico {float(bloques.get('basico', 0)):.0f} kWh / "
                f"intermedio {float(bloques.get('intermedio', 0)):.0f} kWh / resto",
                styles["muted"],
            )
        )
    elems.append(Spacer(1, 6))
    return elems


def _tabla_pago(
    titulo: str,
    pago: dict,
    etiquetas,
    styles: dict,
    ancho: float,
) -> list:
    elems = [
        Paragraph(
            f"{titulo}: <b>${float(pago.get('importe', 0)):,.2f}</b> "
            f"({float(pago.get('kwh', 0)):,.1f} kWh)",
            styles["cuerpo"],
        )
    ]
    filas_esc = _filas_escalones(pago, etiquetas)
    if filas_esc:
        tabla = [["Escalón / Periodo", "kWh", "Importe (MXN)"]] + filas_esc
        t = Table(tabla, colWidths=[ancho * 0.4, ancho * 0.3, ancho * 0.3])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _AZUL2),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.4, _BORDE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _FONDO]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elems.append(Spacer(1, 3))
        elems.append(t)
    elems.append(Spacer(1, 6))
    return elems


def _nota_dac_y_metodo(bloque: dict, styles: dict) -> list:
    elems = []
    metodo = bloque.get("metodo") or ""
    if metodo == "promedio_meses_cfe":
        elems.append(
            Paragraph(
                "Método: promedio simple de precios de los meses del periodo; "
                "bloques (150/130/resto) sobre el kWh total (recibo CFE).",
                styles["muted"],
            )
        )
    dac = bloque.get("dac") or {}
    if dac:
        prom = float(dac.get("promedio_mensual_kwh") or 0)
        lim = float(dac.get("limite_kwh_mes") or 250)
        txt = (
            f"Promedio mensual equivalente ≈ {prom:,.1f} kWh/mes "
            f"(límite DAC {lim:.0f} kWh/mes)"
        )
        if dac.get("supera_dac"):
            txt += " — supera el límite; riesgo de reclasificación DAC."
        elems.append(Paragraph(txt, styles["muted"]))
    if elems:
        elems.append(Spacer(1, 4))
    return elems


def _seccion_costos(resumen: dict, styles: dict, ancho: float) -> list:
    """Costo de energía (consumo) o ahorro (bidireccional) con precios."""
    elems: list = []
    costo = resumen.get("costo_energia")
    ahorro = resumen.get("ahorro_energia")
    if not costo and not ahorro:
        return elems

    if costo:
        elems.append(Paragraph("Costo de energía", styles["subtitulo"]))
        elems.extend(_seccion_precios(costo, styles, ancho))
        elems.extend(_nota_dac_y_metodo(costo, styles))
        etiq = tuple(costo.get("etiquetas_escalones") or ())
        cons = costo.get("consumo") or {}
        elems.extend(
            _tabla_pago("Costo consumo", cons, etiq or None, styles, ancho)
        )

    if ahorro:
        elems.append(Paragraph("Ahorro de energía", styles["subtitulo"]))
        elems.extend(_seccion_precios(ahorro, styles, ancho))
        elems.extend(_nota_dac_y_metodo(ahorro, styles))
        etiq = tuple(ahorro.get("etiquetas_escalones") or ())
        elems.extend(
            _tabla_pago(
                "Costo neteo",
                ahorro.get("neteo") or {},
                etiq or None,
                styles,
                ancho,
            )
        )
        elems.append(
            Paragraph(
                f"Ahorro (Real − Neteo): "
                f"<b>${float(ahorro.get('ahorro', 0)):,.2f}</b>",
                styles["cuerpo"],
            )
        )
        elems.append(Spacer(1, 4))
        elems.extend(
            _tabla_pago(
                ahorro.get("etiqueta_real") or "Costo consumo real",
                ahorro.get("real") or {},
                etiq or None,
                styles,
                ancho,
            )
        )

    return elems


def _tabla_aportaciones(aportaciones: dict, styles: dict, ancho: float) -> list:
    elems = []
    for bloque in aportaciones.values():
        meds = bloque.get("medidores") or []
        if not meds:
            continue
        elems.append(Paragraph(bloque.get("titulo", "Medidores"), styles["subtitulo"]))
        filas = [["Medidor", "kWh", "%"]]
        for m in meds:
            filas.append(
                [
                    str(m["nombre"]),
                    f"{float(m['kwh']):,.1f}",
                    f"{float(m['pct']):.1f}%",
                ]
            )
        total = sum(float(m["kwh"]) for m in meds)
        filas.append(["Total", f"{total:,.1f}", "100%"])
        t = Table(filas, colWidths=[ancho * 0.55, ancho * 0.25, ancho * 0.2])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _AZUL2),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.4, _BORDE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, _FONDO]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elems.append(t)
        elems.append(Spacer(1, 6))
    return elems


def asegurar_graficas_diarias(diario: Path, servicio: str) -> list[Path]:
    """Genera PNG de energía diaria si faltan; reutiliza los existentes."""
    from graficar_energia_diaria import SERIES, generar

    servicio_n = servicio
    base = diario.stem
    for suf in (
        "_gdmth_energia_por_dia",
        "_t01_energia_por_dia",
        "_sin_energia_por_dia",
        "_energia_por_dia",
    ):
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    existentes: list[Path] = []
    faltan = False
    for _col, _tit, _ck, slug in SERIES.get(servicio_n, SERIES["consumo"]):
        p = diario.with_name(f"{base}_grafica_energia_diaria_{slug}.png")
        if p.is_file():
            existentes.append(p)
        else:
            faltan = True
    if faltan or not existentes:
        return generar(diario, servicio_n)
    return existentes


def _imagenes_tipico(grupos_graficas: list[Path]) -> list[Path]:
    """Preferir comparativa; si no, todas las PNG de tipico."""
    if not grupos_graficas:
        return []
    comps = [p for p in grupos_graficas if "comparativa" in p.name.lower()]
    if comps:
        return comps
    return list(grupos_graficas)[:8]


def generar_pdf_analisis(
    *,
    resumen: dict,
    diario: Path | None,
    servicio: str,
    esquema: str,
    graficas_tipico: list[Path] | None = None,
    desglose: bool = True,
) -> bytes:
    """Devuelve el PDF en bytes."""
    styles = _estilos()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.4 * cm,
        title="Reporte Análisis de Perfil",
    )
    ancho = letter[0] - 2.8 * cm
    story: list = []

    story.append(Paragraph("IUSASOL · Análisis de Perfil", styles["marca"]))
    story.append(Paragraph("Reporte de energía", styles["titulo"]))
    periodo = (
        f"Periodo: <b>{resumen.get('fecha_min') or '—'}</b> → "
        f"<b>{resumen.get('fecha_max') or '—'}</b> "
        f"({resumen.get('n_dias', 0)} días)"
    )
    meta = (
        f"{periodo} · Tarifa <b>{esquema}</b> · "
        f"Servicio <b>{resumen.get('servicio', servicio)}</b>"
    )
    if resumen.get("region"):
        meta += f" · Región <b>{resumen['region']}</b>"
    story.append(Paragraph(meta, styles["cuerpo"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Resumen de energía", styles["subtitulo"]))
    story.append(_tabla_metricas(resumen, styles, ancho))
    story.append(Spacer(1, 8))

    if desglose and resumen.get("horaria"):
        tab_p = _tabla_periodos(resumen, styles, ancho)
        if tab_p is not None:
            story.append(Paragraph("Detalle por periodo horario", styles["subtitulo"]))
            story.append(tab_p)
            story.append(Spacer(1, 6))

    # Costos / ahorro con detalle de precios (si el resumen los trae)
    story.extend(_seccion_costos(resumen, styles, ancho))

    if resumen.get("aportaciones"):
        story.append(Paragraph("Aportación por medidor", styles["subtitulo"]))
        story.extend(_tabla_aportaciones(resumen["aportaciones"], styles, ancho))

    if diario and diario.is_file():
        story.append(Paragraph("Energía por día", styles["subtitulo"]))
        try:
            pngs = asegurar_graficas_diarias(diario, servicio)
        except Exception as exc:
            story.append(
                Paragraph(f"No se pudieron generar gráficas diarias: {exc}", styles["muted"])
            )
            pngs = []
        for png in pngs:
            if not png.is_file():
                continue
            img = Image(str(png))
            img._restrictSize(ancho, 8.5 * cm)
            story.append(
                KeepTogether(
                    [
                        Paragraph(png.stem.replace("_", " "), styles["muted"]),
                        img,
                        Spacer(1, 8),
                    ]
                )
            )

    tipicas = _imagenes_tipico(list(graficas_tipico or []))
    if tipicas:
        story.append(Paragraph("Perfil típico", styles["subtitulo"]))
        for png in tipicas:
            if not png.is_file():
                continue
            img = Image(str(png))
            img._restrictSize(ancho, 8.5 * cm)
            story.append(
                KeepTogether(
                    [
                        Paragraph(png.stem.replace("_", " "), styles["muted"]),
                        img,
                        Spacer(1, 8),
                    ]
                )
            )

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "Generado por Análisis de Perfil · suite IUSASOL",
            styles["pie"],
        )
    )

    doc.build(story)
    return buf.getvalue()
