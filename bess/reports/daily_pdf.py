"""Reporte diario BESS en PDF (ReportLab)."""

from __future__ import annotations

import io
import os
from datetime import datetime, timedelta

import pandas as pd

from bess.config.paths import DIRECTORIO_REPORTES, DIRECTORIO_REPORTES_DIARIOS
from bess.core.console import log
from bess.core.numbers import a_num as _a_num, kwh_para_calculo, redondear_arriba_kw
from bess.cfe.arbitrage import calcular_arbitraje_dia
from bess.cfe.daily_data import obtener_bess_energia_dia
from bess.reports.assets import buscar_logo, formatear_fecha_espanol
from bess.tariffs.loader import cargar_tarifas

print = log


def _celdas_kwh_tabla(base, intermedio, punta):
    """kWh por periodo redondeados; total = suma de periodos redondeados."""
    b = kwh_para_calculo(base)
    i = kwh_para_calculo(intermedio)
    p = kwh_para_calculo(punta)
    t = b + i + p
    return f"{b:,}", f"{i:,}", f"{p:,}", f"{t:,}"


# ========== REPORTE PDF — ESTILOS Y HELPERS ==========
_PDF = {
    'primary': '#1a5276',
    'secondary': '#2e86c1',
    'base': '#2980b9',
    'intermedio': '#b7950b',
    'punta': '#c0392b',
    'success': '#27ae60',
    'carga': '#27ae60',
    'descarga': '#e74c3c',
    'iusa': '#2e86c1',
    'bg_light': '#f4f7f9',
    'bg_row': '#f8fafb',
    'bg_arbitraje': '#eafaf1',
    'border': '#d5dce3',
    'text_muted': '#7f8c8d',
    'text_dark': '#2c3e50',
    'content_width_in': 10.35,
    'chart_height_in': 3.85,
    # Ancho tabla = título sección (Periodo + Base + Intermedio + Punta + Total)
    'table_cols_in': (1.68, 0.86, 0.86, 0.86, 0.98),
    'logo_width_in': 1.3125,
    'logo_max_height_in': 0.725,
    'logo_col_in': 1.44,
    'gap_chart_table_in': 0.28,
}

def _pdf_ancho_tabla_in():
    return sum(_PDF['table_cols_in'])

def _pdf_ancho_tabla():
    from reportlab.lib.units import inch
    return _pdf_ancho_tabla_in() * inch

def _pdf_styles():
    """Estilos tipográficos del reporte PDF (compacto, una página)."""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='PdfTitle', parent=styles['Normal'],
        fontSize=14, fontName='Helvetica-Bold',
        textColor=colors.HexColor(_PDF['primary']),
        alignment=TA_RIGHT, spaceAfter=1, leading=16,
    ))
    styles.add(ParagraphStyle(
        name='PdfSubtitle', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica',
        textColor=colors.HexColor(_PDF['text_muted']),
        alignment=TA_RIGHT, spaceAfter=0, leading=10,
    ))
    styles.add(ParagraphStyle(
        name='PdfSection', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold',
        textColor=colors.HexColor(_PDF['primary']),
        alignment=TA_LEFT, spaceAfter=0, leading=11,
    ))
    styles.add(ParagraphStyle(
        name='PdfSectionSub', parent=styles['Normal'],
        fontSize=6.5, fontName='Helvetica',
        textColor=colors.HexColor(_PDF['text_muted']),
        alignment=TA_LEFT, spaceAfter=0, leading=8,
    ))
    return styles

def _pdf_guardar_logo(logo_path, archivos_temp):
    """Prepara imagen del logo y devuelve flowable ReportLab."""
    from reportlab.platypus import Image
    from reportlab.lib.units import inch
    from PIL import Image as PILImage

    img_logo = PILImage.open(logo_path)
    logo_width = _PDF['logo_width_in'] * inch
    logo_height = logo_width * (img_logo.height / img_logo.width)
    max_h = _PDF['logo_max_height_in'] * inch
    if logo_height > max_h:
        logo_height = max_h
        logo_width = max_h * (img_logo.width / img_logo.height)
    buf = io.BytesIO()
    img_logo.save(buf, format='PNG')
    buf.seek(0)
    return Image(buf, width=logo_width, height=logo_height)

def _pdf_encabezado(story, styles, logo_path, fecha_espanol, archivos_temp):
    """Cabecera con logo, título y franja de color."""
    from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    titulo = Paragraph('Reporte Diario BESS', styles['PdfTitle'])
    fecha_p = Paragraph(fecha_espanol, styles['PdfSubtitle'])
    ubicacion = Paragraph('Pastejé, Jocotitlán, Estado de México', styles['PdfSubtitle'])
    cw = _PDF['content_width_in'] * inch

    if logo_path:
        try:
            logo_img = _pdf_guardar_logo(logo_path, archivos_temp)
            info_cell = [[titulo], [fecha_p], [ubicacion]]
            logo_col = _PDF['logo_col_in'] * inch
            info_tbl = Table(info_cell, colWidths=[cw - logo_col])
            info_tbl.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            header = Table([[logo_img, info_tbl]], colWidths=[logo_col, cw - logo_col])
            header.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(header)
        except Exception as e:
            print(f"Error al cargar logo: {e}")
            story.append(titulo)
            story.append(fecha_p)
            story.append(ubicacion)
    else:
        story.append(titulo)
        story.append(fecha_p)
        story.append(ubicacion)

    linea = Table([['']], colWidths=[cw], rowHeights=[2])
    linea.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(_PDF['primary'])),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(1, 0.04 * inch))
    story.append(linea)
    story.append(Spacer(1, 0.06 * inch))

def _pdf_grafica_perfil(df_dia, prefijo, fecha_dt, archivos_temp):
    """Genera gráfica de perfil de carga con estilo alineado al dashboard."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from reportlab.platypus import Image
    from reportlab.lib.units import inch

    horas = df_dia['DATETIME'].values
    iusa_con = df_dia[f'IUSA_CON_BESS_{prefijo}_kW'].values
    bess_rec = df_dia['BESS_REC_kW'].values
    bess_ent = -df_dia['BESS_ENT_kW'].values

    fig, ax = plt.subplots(figsize=(11, 3.62), facecolor='white', dpi=120)
    ax.set_facecolor('white')

    ax.fill_between(horas, 0, iusa_con, alpha=0.12, color=_PDF['iusa'])
    ax.fill_between(horas, 0, bess_rec, alpha=0.15, color=_PDF['carga'])
    ax.fill_between(horas, bess_ent, 0, alpha=0.15, color=_PDF['descarga'])

    ax.plot(horas, iusa_con, color=_PDF['iusa'], linewidth=1.8, label='Demanda con BESS')
    ax.plot(horas, bess_rec, color=_PDF['carga'], linewidth=1.5, label='Carga BESS')
    ax.plot(horas, bess_ent, color=_PDF['descarga'], linewidth=1.5, label='Descarga BESS')

    ax.set_title(
        'Perfil de carga del día',
        fontsize=11, fontweight='bold', color=_PDF['primary'],
        loc='center', pad=26,
    )
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles, labels,
        loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3,
        fontsize=7, frameon=True, facecolor='white',
        edgecolor=_PDF['border'], framealpha=0.95,
        borderpad=0.35, labelspacing=0.35, handlelength=1.4,
    )

    ax.set_xlabel('Hora', fontsize=8, color=_PDF['text_dark'], labelpad=2)
    ax.set_ylabel('Potencia (kW)', fontsize=8, color=_PDF['text_dark'], labelpad=2)
    ax.grid(True, axis='y', alpha=0.35, color=_PDF['border'], linestyle='-', linewidth=0.5)
    ax.grid(True, axis='x', alpha=0.2, color=_PDF['border'], linestyle='-', linewidth=0.4)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(_PDF['border'])
    ax.spines['bottom'].set_color(_PDF['border'])
    ax.tick_params(colors=_PDF['text_muted'], labelsize=7, pad=1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha='right')

    fig.subplots_adjust(top=0.78, bottom=0.16, left=0.07, right=0.98)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none', pad_inches=0.04)
    buf.seek(0)
    plt.close(fig)

    cw = _PDF['content_width_in'] * inch
    ch = _PDF['chart_height_in'] * inch
    return Image(buf, width=cw, height=ch)

def _pdf_titulo_seccion(story, styles, titulo, subtitulo=''):
    """Título de sección con barra lateral de acento."""
    from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    filas = [[Paragraph(titulo, styles['PdfSection'])]]
    if subtitulo:
        filas.append([Paragraph(subtitulo, styles['PdfSectionSub'])])
    tbl = Table(filas, colWidths=[_pdf_ancho_tabla()])
    tbl.setStyle(TableStyle([
        ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor(_PDF['primary'])),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.12 * inch))

def _pdf_tabla_energia(data):
    """Tabla de detalle de energía con columnas por periodo tarifario."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    n_filas = len(data)
    cols = [w * inch for w in _PDF['table_cols_in']]
    tabla = Table(data, colWidths=cols)
    estilo = TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9.5),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor(_PDF['primary'])),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor(_PDF['base'])),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor(_PDF['intermedio'])),
        ('BACKGROUND', (3, 0), (3, 0), colors.HexColor(_PDF['punta'])),
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor(_PDF['text_dark'])),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor(_PDF['text_dark'])),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (4, 1), (4, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor(_PDF['border'])),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor(_PDF['primary'])),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor(_PDF['border'])),
    ])
    # Filas alternadas
    for i in range(1, n_filas):
        if i % 2 == 0:
            estilo.add('BACKGROUND', (0, i), (-1, i), colors.HexColor(_PDF['bg_row']))
    # Fila de arbitraje (última)
    estilo.add('BACKGROUND', (0, n_filas - 1), (-1, n_filas - 1), colors.HexColor(_PDF['bg_arbitraje']))
    estilo.add('FONTNAME', (0, n_filas - 1), (-1, n_filas - 1), 'Helvetica-Bold')
    estilo.add('TEXTCOLOR', (0, n_filas - 1), (0, n_filas - 1), colors.HexColor(_PDF['success']))
    estilo.add('TEXTCOLOR', (4, n_filas - 1), (4, n_filas - 1), colors.HexColor(_PDF['success']))
    tabla.setStyle(estilo)
    return tabla

def _pdf_dibujar_pie(canvas, doc):
    """Pie de página fijo (no ocupa espacio en el flujo del contenido)."""
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from datetime import datetime as dt_now

    canvas.saveState()
    y_text = doc.bottomMargin - 16
    canvas.setFont('Helvetica', 6)
    canvas.setFillColor(colors.HexColor(_PDF['text_muted']))
    linea1 = 'Carretera Panamericana México–Querétaro S/N km. 100 · Pastejé, Jocotitlán, Estado de México'
    linea2 = f'Sistema BESS · Generado el {dt_now.now().strftime("%d/%m/%Y %H:%M")}'
    cx = doc.pagesize[0] / 2
    canvas.drawCentredString(cx, y_text + 7, linea1)
    canvas.drawCentredString(cx, y_text, linea2)
    canvas.restoreState()

def generar_reporte_pdf(fecha_str, medidor):
    """Genera un reporte PDF para una fecha específica"""
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Spacer
        from reportlab.lib.units import inch

        prefijo = 'ION' if medidor == 'ION' else 'BANCO'

        ruta_combinado = os.path.join(DIRECTORIO_REPORTES, f'COMBINADO_POR_MINUTO_{prefijo}.csv')
        ruta_acumulados = os.path.join(DIRECTORIO_REPORTES, f'ACUMULADOS_{prefijo}.csv')

        if not os.path.exists(ruta_combinado):
            return False, "No se encontraron datos para generar el reporte"

        df_combinado = pd.read_csv(ruta_combinado)
        df_combinado['DATETIME'] = pd.to_datetime(df_combinado['FECHA_HORA'], format='%d/%m/%Y %H:%M')

        fecha_dt = datetime.strptime(fecha_str, '%d/%m/%Y')
        inicio = fecha_dt.replace(hour=0, minute=0, second=0)
        fin = (fecha_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0)

        mask = (df_combinado['DATETIME'] >= inicio) & (df_combinado['DATETIME'] < fin)
        df_dia = df_combinado[mask].copy()
        df_dia = df_dia.sort_values('DATETIME').reset_index(drop=True)

        if len(df_dia) == 0:
            return False, f"No hay datos para la fecha {fecha_str}"

        nombre_archivo = f'Reporte_{medidor}_{fecha_dt.strftime("%Y%m%d")}.pdf'
        ruta_pdf = os.path.join(DIRECTORIO_REPORTES_DIARIOS, nombre_archivo)
        os.makedirs(DIRECTORIO_REPORTES_DIARIOS, exist_ok=True)

        doc = SimpleDocTemplate(
            ruta_pdf, pagesize=landscape(letter),
            rightMargin=18, leftMargin=18,
            topMargin=14, bottomMargin=32,
        )

        styles = _pdf_styles()
        archivos_temp = []
        story = []

        logo_path = buscar_logo()
        fecha_espanol = formatear_fecha_espanol(fecha_dt)
        _pdf_encabezado(story, styles, logo_path, fecha_espanol, archivos_temp)

        story.append(_pdf_grafica_perfil(df_dia, prefijo, fecha_dt, archivos_temp))
        story.append(Spacer(1, _PDF['gap_chart_table_in'] * inch))

        _pdf_titulo_seccion(
            story, styles,
            'Detalle de Energía',
            f'Acumulado mensual al {fecha_str} · Arbitraje del día {fecha_str}',
        )

        tarifas = cargar_tarifas()

        if os.path.exists(ruta_acumulados):
            df_acum = pd.read_csv(ruta_acumulados)
            fila_acum = df_acum[df_acum['FECHA'] == fecha_str]
        else:
            fila_acum = None

        data = [['Periodo', 'Base', 'Intermedio', 'Punta', 'Total']]

        if fila_acum is not None and len(fila_acum) > 0:
            fila = fila_acum.iloc[0]
            consumo_base = _a_num(fila.get('BASE_REC_ACUM', 0))
            consumo_intermedio = _a_num(fila.get('INTERMEDIO_REC_ACUM', 0))
            consumo_punta = _a_num(fila.get('PUNTA_REC_ACUM', 0))
            demanda_base = redondear_arriba_kw(fila.get('BASE_DEM_CON_BESS_MAX', 0))
            demanda_intermedio = redondear_arriba_kw(fila.get('INTERMEDIO_DEM_CON_BESS_MAX', 0))
            demanda_punta = redondear_arriba_kw(fila.get('PUNTA_DEM_CON_BESS_MAX', 0))
        else:
            consumo_base = consumo_intermedio = consumo_punta = 0
            demanda_base = demanda_intermedio = demanda_punta = 0

        bess_dia = obtener_bess_energia_dia(fecha_str)
        c_b, c_i, c_p, c_t = _celdas_kwh_tabla(consumo_base, consumo_intermedio, consumo_punta)
        g_b, g_i, g_p, g_t = _celdas_kwh_tabla(
            bess_dia['carga_base'], bess_dia['carga_intermedio'], bess_dia['carga_punta']
        )
        d_b, d_i, d_p, d_t = _celdas_kwh_tabla(
            bess_dia['descarga_base'], bess_dia['descarga_intermedio'], bess_dia['descarga_punta']
        )

        data.append(['Consumo Mensual (kWh)', c_b, c_i, c_p, c_t])
        data.append(['Demanda Rolada (kW)', f'{demanda_base:,}', f'{demanda_intermedio:,}', f'{demanda_punta:,}', f'{demanda_punta:,}'])
        data.append(['Carga del día BESS (kWh)', g_b, g_i, g_p, g_t])
        data.append(['Descarga del día BESS (kWh)', d_b, d_i, d_p, d_t])

        arb = calcular_arbitraje_dia(fecha_str, prefijo, tarifas=tarifas)
        data.append([
            'Arbitraje del día (MXN)',
            f'${arb["base"]:,.2f}', f'${arb["intermedio"]:,.2f}',
            f'${arb["punta"]:,.2f}', f'${arb["total"]:,.2f}',
        ])

        story.append(_pdf_tabla_energia(data))

        doc.build(story, onFirstPage=_pdf_dibujar_pie, onLaterPages=_pdf_dibujar_pie)

        for archivo in archivos_temp:
            if os.path.exists(archivo):
                try:
                    os.remove(archivo)
                except Exception:
                    pass

        return True, ruta_pdf

    except Exception as e:
        return False, str(e)
    

