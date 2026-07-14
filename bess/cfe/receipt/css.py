"""CSS del recibo simulado CFE (sin dependencias de HTML)."""

from __future__ import annotations

RECIBO_ANCHO_REF_PX = 920
RECIBO_FACTOR_ANCHO = 0.80
RECIBO_FACTOR_ALTURA = 1.20
RECIBO_LOGO_ANCHO_REF = 210
RECIBO_FACTOR_LOGO = 0.98


def _recibo_logo_ancho_px():
    return max(1, round(RECIBO_LOGO_ANCHO_REF * RECIBO_FACTOR_ANCHO * RECIBO_FACTOR_LOGO))


def _recibo_px(base, factor):
    return max(1, round(base * factor))


def css_recibo_cfe(for_pdf=False):
    """Estilos del recibo con valores fijos (compatibles con pantalla y PDF)."""
    v = RECIBO_FACTOR_ALTURA
    h = RECIBO_FACTOR_ANCHO
    pv = lambda n: _recibo_px(n, v)
    ph = lambda n: _recibo_px(n, h)
    fs = lambda n: max(6, n - 1) if for_pdf else n
    max_w = round(RECIBO_ANCHO_REF_PX * h)
    logo_w = _recibo_logo_ancho_px()
    lh = round(1.25 * v, 2)
    lh_sm = round(1.3 * v, 2)
    return f"""
        .cfe-recibo-wrap {{
            max-width: {max_w}px;
            margin: 0 auto 16px;
        }}
        .cfe-recibo {{
            font-family: Arial, Helvetica, sans-serif;
            color: #000;
            background: #fff;
            border: 2px solid #000;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
            font-size: {fs(11)}px;
            line-height: {lh};
        }}
        .cfe-layout-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .cfe-recibo-sim {{
            background: #f5f5f5;
            color: #444;
            text-align: center;
            font-size: {fs(10)}px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: {pv(5)}px {ph(8)}px;
            border-bottom: 3px solid #008250;
        }}
        .cfe-recibo-top td {{
            vertical-align: top;
            padding: {pv(10)}px {ph(12)}px {pv(8)}px;
            border-bottom: 1px solid #000;
        }}
        .cfe-emisor td {{
            vertical-align: top;
            padding: 0;
        }}
        .cfe-emisor .cfe-logo-block {{
            width: {logo_w}px;
            vertical-align: middle;
            text-align: center;
            padding-right: {ph(10)}px;
        }}
        .cfe-logo-inner {{
            text-align: center;
        }}
        .cfe-logo-img {{
            display: inline-block;
            height: auto;
            max-width: {logo_w}px;
            vertical-align: middle;
        }}
        .cfe-emisor-nombre, .cfe-receptor-nombre {{
            font-weight: 700;
            font-size: {fs(12)}px;
            margin-bottom: {pv(3)}px;
            color: #008250;
        }}
        .cfe-emisor-dir, .cfe-receptor-dir, .cfe-emisor-rfc {{
            color: #111;
            font-size: {fs(10)}px;
            line-height: {lh_sm};
        }}
        .cfe-receptor {{
            text-align: right;
            border-left: 1px solid #ccc;
            padding-left: {ph(10)}px;
        }}
        .cfe-receptor-etq {{
            font-size: {fs(9)}px;
            font-weight: 700;
            letter-spacing: 0.05em;
            color: #555;
            margin-bottom: {pv(4)}px;
        }}
        .cfe-servicio td {{
            width: 20%;
            padding: {pv(5)}px {ph(7)}px;
            border: 1px solid #000;
            vertical-align: top;
            min-height: {pv(34)}px;
        }}
        .cfe-servicio-item span {{
            display: block;
            color: #333;
            font-size: {fs(8)}px;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            margin-bottom: {pv(2)}px;
        }}
        .cfe-servicio-item b {{
            font-size: {fs(11)}px;
            color: #000;
            font-weight: 700;
        }}
        .cfe-periodo {{
            padding: {pv(6)}px {ph(12)}px;
            background: #e8f5ee;
            border-bottom: 2px solid #008250;
            font-size: {fs(11)}px;
        }}
        .cfe-periodo-etq {{
            font-weight: 700;
            letter-spacing: 0.03em;
        }}
        .cfe-periodo-dias {{
            color: #444;
            font-size: {fs(10)}px;
            margin-left: 4px;
        }}
        .cfe-total-wrap td {{
            vertical-align: middle;
            padding: {pv(10)}px {ph(12)}px;
            border-bottom: 2px solid #000;
        }}
        .cfe-total-label {{
            font-weight: 800;
            font-size: {fs(14)}px;
            letter-spacing: 0.04em;
            color: #000;
        }}
        .cfe-total-monto-box {{
            border: 2px solid #000;
            padding: {pv(8)}px {ph(14)}px;
            background: #fff;
            text-align: center;
            width: {ph(220)}px;
        }}
        .cfe-total-monto {{
            font-size: {fs(26)}px;
            font-weight: 800;
            color: #000;
            white-space: nowrap;
            letter-spacing: 0.02em;
        }}
        .cfe-total-letras {{
            margin-top: {pv(4)}px;
            font-size: {fs(9)}px;
            color: #333;
            line-height: {lh};
            max-width: 95%;
        }}
        .cfe-body td {{
            vertical-align: top;
            padding: {pv(8)}px {ph(10)}px;
            border-bottom: 1px solid #000;
        }}
        .cfe-consumo-panel {{
            width: 31%;
            border-right: 1px solid #000;
            background: #fff;
        }}
        .cfe-mem-panel {{
            width: 69%;
            background: #fff;
        }}
        .cfe-panel-title {{
            font-weight: 800;
            font-size: {fs(10)}px;
            text-transform: uppercase;
            color: #008250;
            margin-bottom: {pv(6)}px;
            letter-spacing: 0.04em;
            border-bottom: 1px solid #008250;
            padding-bottom: {pv(3)}px;
        }}
        .cfe-mini-table, .cfe-mem-table, .cfe-desglose-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: {fs(10)}px;
        }}
        .cfe-mini-table th, .cfe-mem-table th {{
            background: #ececec;
            color: #000;
            padding: {pv(4)}px {ph(5)}px;
            text-align: center;
            font-size: {fs(9)}px;
            font-weight: 700;
            border: 1px solid #000;
        }}
        .cfe-mini-table td, .cfe-mem-table td, .cfe-desglose-table td {{
            border: 1px solid #000;
            padding: {pv(3)}px {ph(5)}px;
            vertical-align: middle;
        }}
        .cfe-mini-table td:first-child, .cfe-desglose-table td:first-child {{
            font-weight: 600;
        }}
        .cfe-mem-table td:first-child {{ font-weight: 600; }}
        .cfe-mem-row:nth-child(even) td {{ background: #fafafa; }}
        .cfe-mem-total td {{
            background: #e8f5ee;
            font-weight: 800;
        }}
        .cfe-mem-nota {{
            margin-top: {pv(5)}px;
            font-size: {fs(8)}px;
            color: #555;
            line-height: {lh};
            font-style: italic;
        }}
        .cfe-desglose {{
            padding: {pv(8)}px {ph(12)}px {pv(10)}px;
            background: #fff;
        }}
        .cfe-desglose-table td:last-child {{ text-align: right; width: 36%; }}
        .cfe-desglose-total td {{
            background: #e8f5ee;
            font-weight: 800;
            border-top: 2px solid #008250;
        }}
        .cfe-footnote {{
            padding: {pv(6)}px {ph(12)}px {pv(8)}px;
            font-size: {fs(8)}px;
            color: #555;
            background: #f5f5f5;
            border-top: 1px solid #ccc;
            text-align: center;
        }}
        .cfe-recibo .num {{ text-align: right; white-space: nowrap; }}
"""
