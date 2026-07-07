"""HTML y CSS del recibo simulado CFE."""

from __future__ import annotations

import html

from bess.cfe.receipt.build import _celda_mem
from bess.cfe.receipt.css import _recibo_logo_ancho_px, css_recibo_cfe
from bess.config.esquema_tarifa import ESQUEMA_GDMTH
from bess.cfe.receipt.format import (
    _fmt_cargo_fp_recibo,
    _fmt_mxn_decimal,
    _fmt_mxn_entero,
    _monto_a_letras_mxn,
)
from bess.reports.assets import logo_cfe_html


def _html_servicio_celda(etiqueta, valor):
    return f'<td class="cfe-servicio-item"><span>{etiqueta}</span><b>{valor}</b></td>'

def _html_fila_mem(concepto, celda, es_total=False):
    cls = 'cfe-mem-row cfe-mem-total' if es_total else 'cfe-mem-row'
    pkwh = '—' if celda['precio_kwh'] == 0 else f"{celda['precio_kwh']:.4f}"
    pkw = '—' if celda['precio_kw'] == 0 else f"{celda['precio_kw']:,.2f}"
    imp = f"{celda['importe']:,.2f}"
    return (
        f'<tr class="{cls}">'
        f'<td>{concepto}</td>'
        f'<td class="num">{pkwh}</td>'
        f'<td class="num">{pkw}</td>'
        f'<td class="num">{imp}</td>'
        f'</tr>'
    )

def _html_fila_desglose(concepto: str, importe: str) -> str:
    return f'<tr><td>{concepto}</td><td class="num">{importe}</td></tr>'


def _html_filas_desglose(datos, d: dict) -> str:
    es_gdmth = datos.get('esquema_tarifa') == ESQUEMA_GDMTH
    filas = [
        _html_fila_desglose('Cargo Fijo', _fmt_mxn_decimal(d['cargo_fijo'])),
        _html_fila_desglose('Energía', _fmt_mxn_decimal(d['energia'])),
    ]
    if es_gdmth:
        filas.append(
            _html_fila_desglose(
                'Cargo factor de potencia',
                _fmt_cargo_fp_recibo(d['cargo_fp']),
            )
        )
    else:
        filas.append(
            _html_fila_desglose(
                f"Capacidad ({datos['capacidad_kw']:,} kW · {datos['capacidad_criterio']})",
                _fmt_mxn_decimal(d['capacidad']),
            )
        )
        filas.append(
            _html_fila_desglose('Cargo FP', _fmt_cargo_fp_recibo(d['cargo_fp']))
        )
    return ''.join(filas)


def render_html_recibo_cfe(datos):
    """HTML del recibo con layout similar al aviso CFE."""
    c = datos['cliente']
    dir_html = ''.join(f'<div>{linea}</div>' for linea in c['direccion'])
    carga = (
        f"{c['carga_conectada_kw']:,}"
        if c.get('carga_conectada_kw') is not None else '—'
    )
    demanda_cta = (
        f"{c['demanda_contratada_kw']:,}"
        if c.get('demanda_contratada_kw') is not None else '—'
    )
    kwh = datos['kwh']
    kw = datos['kw']
    d = datos['desglose']
    kvarh_txt = f"{int(round(datos['kvarh'])):,}" if datos['kvarh'] is not None else '—'
    fp_txt = f"{datos['factor_potencia_pct']:.2f}" if datos['factor_potencia_pct'] is not None else '—'

    filas_mem = ''.join(
        _html_fila_mem(nombre, celda)
        for nombre, celda in datos['mem'].items()
    )
    total_mem = _celda_mem(datos['total_mem'])
    filas_mem += _html_fila_mem('TOTAL', total_mem, es_total=True)
    logo_cfe = logo_cfe_html(_recibo_logo_ancho_px())
    campos_servicio = [
        ('NO. DE SERVICIO', c['no_servicio']),
        ('CUENTA', c['cuenta']),
        ('FECHA LÍMITE DE PAGO', datos['fecha_limite_pago']),
        ('CARGA CONECTADA kW', carga),
        ('DEMANDA CONTRATADA kW', demanda_cta),
        ('CORTE A PARTIR', datos['corte_partir']),
        ('TARIFA', c['tarifa']),
        ('MULTIPLICADOR', c['multiplicador']),
        ('NO HILOS', c['no_hilos']),
        ('NO. MEDIDOR', c['no_medidor']),
    ]
    fila_serv_1 = ''.join(
        _html_servicio_celda(etq, val) for etq, val in campos_servicio[:5]
    )
    fila_serv_2 = ''.join(
        _html_servicio_celda(etq, val) for etq, val in campos_servicio[5:]
    )

    es_gdmth = datos.get('esquema_tarifa') == ESQUEMA_GDMTH
    if es_gdmth:
        nota_mem = (
            f'Distribución: {datos["distribucion_kw"]:,} kW ({datos["distribucion_criterio"]}) · '
            f'Capacidad: {datos["capacidad_kw"]:,} kW ({datos["capacidad_criterio"]}). '
            '(1) SCnMEM: servicios del Mercado.'
        )
    else:
        nota_mem = '(1) SCnMEM: servicios del Mercado.'
    filas_desglose = _html_filas_desglose(datos, d)

    return f"""
<div class="cfe-recibo-wrap">
<div class="cfe-recibo">
  <div class="cfe-recibo-sim">SIMULACIÓN BESS · {datos['escenario']} · No sustituye el recibo oficial CFE</div>
  <table class="cfe-layout-table cfe-recibo-top">
    <tr>
      <td class="cfe-emisor" width="58%">
        <table class="cfe-layout-table cfe-emisor">
          <tr>
            <td class="cfe-logo-block" align="center" valign="middle"><div class="cfe-logo-inner">{logo_cfe}</div></td>
            <td class="cfe-emisor-texto">
              <div class="cfe-emisor-nombre">Comisión Federal de Electricidad</div>
              <div class="cfe-emisor-dir">Av. Paseo de la Reforma 164, Col. Juárez,<br>
              Alcaldía: Cuauhtémoc, C.P. 06600, Ciudad de México.</div>
              <div class="cfe-emisor-rfc">RFC: CFE370814QI0</div>
            </td>
          </tr>
        </table>
      </td>
      <td class="cfe-receptor" width="42%">
        <div class="cfe-receptor-etq">DATOS DEL RECEPTOR</div>
        <div class="cfe-receptor-nombre">{c['razon_social']}</div>
        <div class="cfe-receptor-dir">{dir_html}</div>
      </td>
    </tr>
  </table>
  <table class="cfe-layout-table cfe-servicio">
    <tr>{fila_serv_1}</tr>
    <tr>{fila_serv_2}</tr>
  </table>
  <div class="cfe-periodo">
    <span class="cfe-periodo-etq">PERIODO FACTURADO:</span>
    <b>{datos['periodo_facturado']}</b>
    <span class="cfe-periodo-dias">· {datos['dias_mes']} días acumulados · corte {datos['fecha_corte'].strftime('%d/%m/%Y')}</span>
  </div>
  <table class="cfe-layout-table cfe-total-wrap">
    <tr>
      <td class="cfe-total-left" width="68%">
        <div class="cfe-total-label">TOTAL A PAGAR:</div>
        <div class="cfe-total-letras">{_monto_a_letras_mxn(d['total'])}</div>
      </td>
      <td class="cfe-total-monto-box" width="32%" align="center">
        <div class="cfe-total-monto">{_fmt_mxn_entero(d['total'])}</div>
      </td>
    </tr>
  </table>
  <table class="cfe-layout-table cfe-body">
    <tr>
      <td class="cfe-consumo-panel">
        <div class="cfe-panel-title">Consumo</div>
        <table class="cfe-mini-table">
          <thead><tr><th>Concepto</th><th>Medida</th></tr></thead>
          <tbody>
            <tr><td>kWh base</td><td class="num">{kwh['base']:,}</td></tr>
            <tr><td>kWh intermedia</td><td class="num">{kwh['intermedio']:,}</td></tr>
            <tr><td>kWh punta</td><td class="num">{kwh['punta']:,}</td></tr>
            <tr><td>kW base</td><td class="num">{kw['base']:,}</td></tr>
            <tr><td>kW intermedia</td><td class="num">{kw['intermedio']:,}</td></tr>
            <tr><td>kW punta</td><td class="num">{kw['punta']:,}</td></tr>
            <tr><td>KWMax</td><td class="num">{kw['kw_max']:,}</td></tr>
            <tr><td>kVArh</td><td class="num">{kvarh_txt}</td></tr>
            <tr><td>Factor de potencia %</td><td class="num">{fp_txt}</td></tr>
          </tbody>
        </table>
      </td>
      <td class="cfe-mem-panel">
        <div class="cfe-panel-title">Costos de la energía en el Mercado Eléctrico Mayorista</div>
        <table class="cfe-mem-table">
          <thead>
            <tr>
              <th>Concepto</th><th>$/kWh</th><th>$/kW</th><th>Importe (MXN)</th>
            </tr>
          </thead>
          <tbody>{filas_mem}</tbody>
        </table>
        <div class="cfe-mem-nota">
          {nota_mem}
        </div>
      </td>
    </tr>
  </table>
  <div class="cfe-desglose">
    <div class="cfe-panel-title">Desglose del importe a pagar</div>
    <table class="cfe-desglose-table">
      <tbody>
        {filas_desglose}
        <tr><td>Subtotal</td><td class="num">{_fmt_mxn_decimal(d['subtotal'])}</td></tr>
        <tr><td>IVA 16%</td><td class="num">{_fmt_mxn_decimal(d['iva'])}</td></tr>
        <tr class="cfe-desglose-total"><td>Facturación del periodo (simulada)</td><td class="num">{_fmt_mxn_decimal(d['total'])}</td></tr>
      </tbody>
    </table>
  </div>
  <div class="cfe-footnote">
    Documento informativo generado por el sistema BESS · IUSASOL. No sustituye el aviso recibo oficial de CFE.
  </div>
</div>
</div>
"""


def render_html_recibo_documento(datos):
    """Documento HTML completo para exportar a PDF (mismo aspecto que pantalla)."""
    css = css_recibo_cfe(for_pdf=True)
    cuerpo = render_html_recibo_cfe(datos)
    escenario = html.escape(datos["escenario"])
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Recibo simulado CFE · {escenario}</title>
<style>
@page {{ size: letter portrait; margin: 8mm; }}
html, body {{
    margin: 0;
    padding: 0;
    background: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}}
body {{ text-align: center; }}
.cfe-recibo-wrap {{ display: inline-block; text-align: left; }}
.cfe-recibo {{ page-break-inside: avoid; break-inside: avoid; }}
{css}
</style>
</head>
<body>
{cuerpo}
</body>
</html>"""
