"""Estilos CSS globales de la app Streamlit."""

import streamlit as st


def aplicar_estilos():
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"]:not(:has(.login-page-marker)) > .main .block-container,
        [data-testid="stAppViewContainer"]:not(:has(.login-page-marker)) [data-testid="stMainBlockContainer"],
        [data-testid="stAppViewContainer"]:not(:has(.login-page-marker)) section[data-testid="stMain"] > div {
            max-width: unset !important;
            width: 100% !important;
        }
        [data-testid="stAppViewContainer"]:not(:has(.login-page-marker)) > .main {
            flex: 1 1 0% !important;
        }
        .main-container { padding: 0 10px; }
        .section-container {
            background: #ffffff;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid #f0f0f0;
        }
        .section-title {
            font-size: 17px;
            font-weight: 600;
            color: #1a5276;
            margin: 0 0 6px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #e8ecef;
        }
        .section-title-sm {
            font-size: 14px;
            font-weight: 600;
            color: #1a5276;
            margin: 0 0 8px 0;
            padding-bottom: 6px;
            border-bottom: 1px solid #e8ecef;
        }
        .section-desc {
            font-size: 12px;
            color: #718096;
            margin: 0 0 14px 0;
            line-height: 1.45;
        }
        .tabla-bloque {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 4px;
            margin: 10px 0 16px 0;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            overflow: hidden;
            background: #f8fafc;
            margin: 8px 0 14px 0;
        }
        .app-header {
            display: flex;
            align-items: center;
            gap: 18px;
            background: transparent;
            border-radius: 0;
            padding: 0;
            border: none;
            margin-bottom: 0;
        }
        .contexto-medidor {
            font-size: 13px;
            color: #4a5568;
            margin: 0 0 10px 0;
        }
        .panel-controles {
            background: #f8fafc;
            border-radius: 10px;
            padding: 14px 16px;
            border: 1px solid #e8ecef;
            margin-bottom: 16px;
        }
        .app-header-title {
            margin: 0;
            font-size: 1.55rem;
            color: #1a5276;
            font-weight: 700;
        }
        .app-header-sub {
            margin: 4px 0 0;
            color: #718096;
            font-size: 0.88rem;
        }
        .app-header-badge {
            color: #1a5276;
            font-weight: 600;
        }
        
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.stDateInput) {
            background: #f8fafc;
            border-radius: 12px;
            padding: 12px 16px;
            border-color: #e8ecef !important;
            margin-bottom: 28px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) {
            padding: 8px 12px !important;
            margin-bottom: 12px !important;
            border-radius: 10px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .section-title-sm {
            margin: 0 0 2px 0;
            padding-bottom: 4px;
            font-size: 13px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .section-desc {
            margin: 0 0 6px 0;
            font-size: 11px;
            line-height: 1.35;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .stDateInput label {
            font-size: 12px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .stDateInput > div {
            min-height: 0 !important;
            padding: 0 8px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .metric-compact {
            padding: 6px 6px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .metric-compact .label {
            font-size: 10px;
            margin-bottom: 2px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) .metric-compact .value {
            font-size: 13px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.panel-fecha-unica-anchor) [data-testid="column"] {
            padding-top: 0;
            padding-bottom: 0;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:not(:has(.stDateInput)):not(:has(form)) {
            background: #ffffff;
            border-radius: 12px;
            padding: 18px 20px;
            border-color: #e2e8f0 !important;
            border-width: 1px !important;
            margin-bottom: 18px;
            box-shadow: 0 1px 6px rgba(26, 82, 118, 0.05);
        }
        div[data-testid="stTabs"] {
            margin-top: 4px;
        }
        div[data-testid="stTabs"] button {
            font-size: 16px !important;
        }
        div[data-testid="stTabs"] button p {
            font-size: 16px !important;
        }
        div[data-testid="stTabs"] div[data-testid="stVerticalBlockBorderWrapper"] {
            box-shadow: none;
            border: none;
            padding: 0;
            margin-bottom: 12px;
            background: transparent;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.stDateInput) .stDateInput > div {
            background: white;
            border-radius: 8px;
            border: 1px solid #d5d8dc;
            padding: 2px 10px;
        }
        .fecha-resumen {
            background: linear-gradient(135deg, #e8f4f8 0%, #d4e9f7 100%);
            border-radius: 8px;
            padding: 10px 16px;
            border-left: 4px solid #1a5276;
            font-size: 13px;
            margin: 8px 0 12px 0;
        }
        
        .metric-card {
            background: white;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
            border: 1px solid #e8ecef;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }
        .metric-card .icon { display: none; }
        .metric-card .label { font-size: 13px; color: #718096; font-weight: 500; }
        .metric-card .value { font-size: 24px; font-weight: 700; color: #1a202c; }
        .metric-card .sub { font-size: 12px; color: #a0aec0; }

        .metric-card-total {
            text-align: left;
            padding: 20px 24px;
        }
        .metric-card-total .label {
            font-size: 18px;
            text-align: center;
            margin-bottom: 1rem;
        }
        .metric-card-total .total-grid {
            display: flex;
            justify-content: space-between;
            align-items: stretch;
            width: 100%;
            gap: 0;
            margin-top: 0.25rem;
        }
        .metric-card-total .total-item {
            flex: 1;
            text-align: center;
            min-width: 0;
            padding: 0.5rem 1.5rem;
        }
        .metric-card-total .total-item-mxn {
            border-left: 1px solid #e2e8f0;
        }
        .metric-card-total .total-item .item-label {
            font-size: 17px;
            color: #718096;
            font-weight: 500;
            margin-bottom: 0.35rem;
        }
        .metric-card-total .total-item .value {
            font-size: 29px;
            line-height: 1.2;
        }
        .metric-card-total .total-item .unit {
            font-size: 17px;
            color: #718096;
            font-weight: 500;
            margin-top: 0.2rem;
        }
        @media (max-width: 640px) {
            .metric-card-total .total-grid {
                flex-direction: column;
                gap: 1rem;
            }
            .metric-card-total .total-item-mxn {
                border-left: none;
                border-top: 1px solid #e2e8f0;
                padding-top: 1rem;
            }
        }

        .metric-compact {
            background: #fafbfc;
            border-radius: 8px;
            padding: 10px 8px;
            text-align: center;
            border: 1px solid #e8ecef;
        }
        .metric-compact .label {
            font-size: 11px;
            color: #718096;
            font-weight: 500;
            line-height: 1.3;
            margin-bottom: 4px;
        }
        .metric-compact .value {
            font-size: 15px;
            font-weight: 600;
            color: #1a202c;
            line-height: 1.25;
        }

        .sidebar-tarifas-grid {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-top: 4px;
        }
        .sidebar-tarifa-item {
            background: #f8fafc;
            border-radius: 6px;
            padding: 6px 10px;
            border: 1px solid #e8ecef;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
        }
        .sidebar-tarifa-item .label {
            font-size: 12px;
            color: #718096;
            font-weight: 500;
            line-height: 1.2;
            flex-shrink: 0;
        }
        .sidebar-tarifa-item .value {
            font-size: 13px;
            font-weight: 600;
            color: #1a202c;
            line-height: 1.25;
            text-align: right;
        }

        .sync-resumen {
            font-size: 0.78rem;
            line-height: 1.55;
            color: rgba(255, 255, 255, 0.88);
            background: rgba(0, 0, 0, 0.18);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 8px 10px;
            margin-top: 8px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .sync-resumen div {
            margin: 1px 0;
        }
        
        .arbitraje-card {
            border-radius: 10px;
            padding: 14px;
            text-align: center;
            border-left: 4px solid #27ae60;
            background: #f0fff4;
        }
        .arbitraje-card.negativo {
            border-left-color: #e74c3c;
            background: #fff5f5;
        }
        .arbitraje-card .periodo { font-size: 13px; font-weight: 600; color: #4a5568; }
        .arbitraje-card .valor { font-size: 20px; font-weight: 700; }
        .arbitraje-card .valor.positivo { color: #27ae60; }
        .arbitraje-card .valor.negativo { color: #e74c3c; }

        .capacidad-comparacion {
            display: flex;
            align-items: stretch;
            gap: 12px;
            margin: 8px 0 12px 0;
        }
        @media (max-width: 960px) {
            .capacidad-comparacion {
                flex-direction: column;
            }
            .cap-centro {
                order: -1;
            }
        }
        .cap-bloque {
            flex: 1;
            border-radius: 10px;
            padding: 16px 14px;
            text-align: center;
            border: 1px solid #e8ecef;
        }
        .cap-bloque.cap-sin {
            background: #fff5f5;
            border-left: 4px solid #e74c3c;
        }
        .cap-bloque.cap-con {
            background: #f0fff4;
            border-left: 4px solid #27ae60;
        }
        .cap-etiqueta {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #718096;
            margin-bottom: 6px;
        }
        .cap-demanda {
            font-size: 13px;
            color: #4a5568;
            margin-bottom: 4px;
        }
        .cap-costo {
            font-size: 22px;
            font-weight: 700;
            color: #1a202c;
        }
        .cap-centro {
            flex: 1.1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            border-radius: 12px;
            padding: 14px 10px;
            background: linear-gradient(135deg, #e8f8ef 0%, #d4efdf 100%);
            border: 2px solid #27ae60;
            text-align: center;
        }
        .cap-centro.negativo {
            background: linear-gradient(135deg, #fdecea 0%, #fadbd8 100%);
            border-color: #e74c3c;
        }
        .cap-ahorro-valor {
            font-size: 28px;
            font-weight: 800;
            color: #1e8449;
            line-height: 1.1;
        }
        .cap-centro.negativo .cap-ahorro-valor { color: #c0392b; }
        .cap-ahorro-label {
            font-size: 13px;
            font-weight: 600;
            color: #2c3e50;
            margin-top: 4px;
        }
        .cap-ahorro-sub {
            font-size: 12px;
            color: #718096;
            margin-top: 6px;
        }
        .cap-tarifa {
            font-size: 12px;
            color: #718096;
            text-align: center;
            margin-bottom: 8px;
        }

        
        .stButton button {
            border-radius: 8px;
            font-weight: 500;
        }
        .btn-primary button {
            background: #1a5276;
            color: white;
        }
        .btn-primary button:hover {
            background: #154360;
        }
        .js-plotly-plot .modebar-group {
            opacity: 1 !important;
        }
        .js-plotly-plot .modebar {
            opacity: 1 !important;
        }
        .js-plotly-plot .modebar-btn {
            opacity: 1 !important;
        }
        [data-testid="stDownloadButton"] button {
            font-weight: 600;
        }

        /* —— Navegación y ayuda flotante —— */
        .bess-nav-bar {
            margin-bottom: 4px;
        }
        /* Nav container: scroll horizontal en móvil */
        @media (max-width: 768px) {
            [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .bess-nav-col-marker) {
                overflow-x: auto !important;
                flex-wrap: nowrap !important;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: none;
                padding-bottom: 4px;
            }
            [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .bess-nav-col-marker)::-webkit-scrollbar {
                display: none;
            }
            [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .bess-nav-col-marker) > [data-testid="column"] {
                flex: 0 0 auto !important;
                min-width: fit-content !important;
                width: auto !important;
            }
        }
        #bess-nav-tooltip-root {
            position: fixed;
            top: 0;
            left: 0;
            width: 0;
            height: 0;
            overflow: visible;
            z-index: 999990;
            pointer-events: none;
        }
        .bess-floating-tip {
            display: none !important;
            position: fixed;
            top: -9999px;
            left: -9999px;
            width: min(268px, calc(100vw - 24px));
            background: #ffffff;
            border: 2px solid #2e86c1;
            border-radius: 12px;
            padding: 12px 14px 10px;
            box-shadow: 0 8px 24px rgba(26, 82, 118, 0.22);
            pointer-events: none;
            z-index: 999991;
        }
        .bess-floating-tip.visible {
            display: block !important;
        }
        .nav-hub-icon {
            font-size: 1.35rem;
            line-height: 1;
            margin-bottom: 6px;
        }
        .nav-hub-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: #1a5276;
            margin-bottom: 4px;
            line-height: 1.25;
        }
        .nav-hub-resumen {
            font-size: 0.72rem;
            color: #64748b;
            margin: 0 0 6px;
            line-height: 1.35;
        }
        .nav-hub-caps {
            margin: 0;
            padding-left: 14px;
            font-size: 0.68rem;
            color: #475569;
            line-height: 1.45;
        }
        .nav-hub-caps li { margin: 1px 0; }

        .nav-pills-label {
            margin: 0 0 4px;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #64748b;
        }

        div[data-testid="column"]:has(.bess-nav-col-marker) {
            position: relative !important;
            overflow: visible !important;
        }
        div[data-testid="column"]:has(.bess-nav-col-marker) [data-testid="stButton"] button {
            border-radius: 999px !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            min-height: 2.64rem !important;
            padding: 0.53rem 0.75rem !important;
            background: #f3f4f6 !important;
            border-color: #e2e5e9 !important;
            color: #31333f !important;
        }
        div[data-testid="column"]:has(.bess-nav-col-marker) [data-testid="stButton"] button:hover {
            background: #e8eaed !important;
            border-color: #2e86c1 !important;
            color: #31333f !important;
        }
        div[data-testid="column"]:has(.bess-nav-active) [data-testid="stButton"] button {
            background: #1a5276 !important;
            border-color: #1a5276 !important;
            color: #ffffff !important;
        }
        div[data-testid="column"]:has(.bess-nav-active) [data-testid="stButton"] button:hover {
            background: #154360 !important;
            border-color: #154360 !important;
            color: #ffffff !important;
        }

        .panel-medidor {
            background: linear-gradient(135deg, #f0f7fb 0%, #e8f4fc 100%);
            border: 1px solid #c5dff0;
            border-radius: 10px;
            padding: 10px 14px;
            margin-top: 8px;
        }
        .panel-medidor-label {
            margin: 0 0 4px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #1a5276;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }

        div[data-testid="stTabs"] button[data-baseweb="tab"] {
            font-weight: 600 !important;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #1a5276 !important;
            border-bottom-color: #1a5276 !important;
        }

        /* Sidebar — guía y flujo admin */
        .sidebar-guia {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 10px;
            padding: 10px 12px;
            margin-bottom: 12px;
        }
        .sidebar-guia-titulo {
            margin: 0 0 8px;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: rgba(255, 255, 255, 0.85);
        }
        .sidebar-modulo {
            display: flex;
            gap: 8px;
            align-items: flex-start;
            padding: 6px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .sidebar-modulo:last-child { border-bottom: none; }
        .sidebar-modulo-icon { font-size: 1rem; line-height: 1.2; }
        .sidebar-modulo strong {
            display: block;
            font-size: 0.8rem;
            color: #ffffff;
            margin-bottom: 2px;
        }
        .sidebar-modulo p {
            margin: 0;
            font-size: 0.7rem;
            color: rgba(255, 255, 255, 0.72);
            line-height: 1.35;
        }

        .sidebar-flujo {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 10px 12px;
            margin-bottom: 14px;
        }
        .sidebar-flujo-titulo {
            margin: 0 0 8px;
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #1a202c;
        }
        .sidebar-paso {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.78rem;
            color: #1a202c;
            padding: 4px 0;
        }
        .sidebar-paso span {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #2e86c1;
            color: #fff;
            font-size: 0.68rem;
            font-weight: 700;
            flex-shrink: 0;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
            font-weight: 600 !important;
            font-size: 0.9rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] {
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            margin-bottom: 8px;
        }

        /* Visualizador (user): barra lateral oculta */
        body.bess-rol-user-mode section[data-testid="stSidebar"],
        body:has(.bess-rol-user) section[data-testid="stSidebar"] {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
            overflow: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        body.bess-rol-user-mode [data-testid="stSidebarCollapsedControl"],
        body.bess-rol-user-mode [data-testid="collapsedControl"],
        body.bess-rol-user-mode [data-testid="stExpandSidebarButton"],
        body:has(.bess-rol-user) [data-testid="stSidebarCollapsedControl"],
        body:has(.bess-rol-user) [data-testid="collapsedControl"],
        body:has(.bess-rol-user) [data-testid="stExpandSidebarButton"] {
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }
        body.bess-rol-user-mode [data-testid="stAppViewContainer"] > .main,
        body:has(.bess-rol-user) [data-testid="stAppViewContainer"] > .main {
            margin-left: 0 !important;
            padding-left: 0 !important;
        }

        /* ====== RESPONSIVE MOBILE ====== */
        @media (max-width: 768px) {
            /* Header: reducir título y ocultar logo */
            .app-header {
                gap: 8px !important;
                flex-wrap: wrap;
            }
            .app-header > div:first-child {
                display: none !important;
            }
            .app-header-title {
                font-size: 1.1rem !important;
                white-space: nowrap;
            }
            .app-header-sub {
                font-size: 0.75rem !important;
            }

            /* Navegación: botones más compactos */
            div[data-testid="column"]:has(.bess-nav-col-marker) [data-testid="stButton"] button {
                font-size: 0.7rem !important;
                padding: 0.5rem 0.3rem !important;
                min-height: 44px !important;
                line-height: 1.2 !important;
            }

            /* Métricas: colapsar 4 cols a grid de 2 */
            [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .metric-card) {
                flex-wrap: wrap !important;
            }
            [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .metric-card) > [data-testid="column"] {
                flex: 0 0 48% !important;
                min-width: 48% !important;
                max-width: 48% !important;
                margin-bottom: 8px;
            }

            /* Métricas: reducir fuentes */
            .metric-card .value { font-size: 18px !important; }
            .metric-card .label { font-size: 11px !important; }
            .metric-card .sub { font-size: 11px !important; }
            .metric-card { padding: 10px 12px !important; }

            /* Card total */
            .metric-card-total { padding: 14px 12px !important; }
            .metric-card-total .total-item .value { font-size: 22px !important; }
            .metric-card-total .total-item .item-label { font-size: 14px !important; }
            .metric-card-total .total-item { padding: 0.4rem 0.8rem !important; }

            /* Secciones */
            .section-container { padding: 12px 10px !important; }
            .resumen-diario { padding: 10px !important; }

            /* Arbitraje */
            .arbitraje-card .valor { font-size: 16px !important; }
            .arbitraje-card { padding: 10px !important; }

            /* Sidebar */
            section[data-testid="stSidebar"] { min-width: 240px !important; }

            /* Ocultar tooltips (no funcionan en touch) */
            .bess-floating-tip { display: none !important; }
            #bess-nav-tooltip-root { display: none !important; }

            /* Reducir padding general */
            .block-container { padding: 1rem 0.5rem !important; }

            /* Panel medidor: más compacto */
            .panel-medidor { padding: 6px 10px !important; margin-top: 4px !important; }
            .panel-medidor-label { font-size: 0.7rem !important; }
        }

        @media (max-width: 480px) {
            /* Header: título abreviado */
            .app-header-title {
                font-size: 0.95rem !important;
            }

            /* Navegación ultra-compacta: solo iconos */
            div[data-testid="column"]:has(.bess-nav-col-marker) [data-testid="stButton"] button {
                font-size: 0.92rem !important;
                padding: 0.5rem 0.2rem !important;
                overflow: hidden;
            }

            /* Métricas: una sola columna */
            [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] .metric-card) > [data-testid="column"] {
                flex: 0 0 100% !important;
                min-width: 100% !important;
                max-width: 100% !important;
            }

            /* Total card: stack vertical */
            .metric-card-total .total-grid {
                flex-direction: column !important;
                gap: 0.8rem !important;
            }
            .metric-card-total .total-item-mxn {
                border-left: none !important;
                border-top: 1px solid #e2e8f0 !important;
                padding-top: 0.8rem !important;
            }

            /* Selectores de fecha: más espacio vertical */
            [data-testid="stDateInput"] { margin-bottom: 4px; }
        }

        /* Touch devices: ocultar tooltips hover */
        @media (hover: none) {
            .bess-floating-tip { display: none !important; }
            #bess-nav-tooltip-root { display: none !important; }
        }
    </style>
    """, unsafe_allow_html=True)


def aplicar_estilos_login():
    st.markdown("""
    <style>
        body.bess-login-mode section[data-testid="stSidebar"],
        body.bess-login-mode [data-testid="stSidebarCollapsedControl"],
        body.bess-login-mode [data-testid="collapsedControl"],
        body.bess-login-mode [data-testid="stExpandSidebarButton"],
        [data-testid="stAppViewContainer"]:has(.login-page-marker) [data-testid="stSidebar"],
        [data-testid="stAppViewContainer"]:has(.login-page-marker) [data-testid="stSidebarCollapsedControl"],
        [data-testid="stAppViewContainer"]:has(.login-page-marker) [data-testid="collapsedControl"] {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
            overflow: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        body.bess-login-mode .sidebar-guia,
        body.bess-login-mode .sidebar-modulo,
        body.bess-login-mode .sidebar-flujo,
        body.bess-login-mode .sidebar-paso,
        body.bess-login-mode .sidebar-guia-titulo,
        body.bess-login-mode .sidebar-flujo-titulo,
        body.bess-login-mode .sidebar-modulo-icon,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) .bess-floating-tip,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) #bess-nav-tooltip-root,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) .sidebar-guia,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) .sidebar-modulo,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) .sidebar-flujo,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) .sidebar-paso {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            width: 0 !important;
            overflow: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
            position: absolute !important;
            left: -9999px !important;
        }
        #bess-nav-tooltip-root,
        .bess-floating-tip {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
            position: fixed !important;
            left: -9999px !important;
            top: -9999px !important;
            width: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
        }
        body.bess-login-mode [data-testid="stAppViewContainer"] > .main,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) > .main {
            margin-left: 0 !important;
            padding-left: 0 !important;
            max-width: 100% !important;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) > .main .block-container,
        [data-testid="stAppViewContainer"]:has(.login-page-marker) [data-testid="stMainBlockContainer"],
        [data-testid="stAppViewContainer"]:has(.login-page-marker) section[data-testid="stMain"] > div {
            padding-top: 2.5rem;
            max-width: 100% !important;
            width: 100% !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-left: 1rem;
            padding-right: 1rem;
            box-sizing: border-box;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) [data-testid="column"] {
            min-width: 0 !important;
        }
        .login-page-marker {
            display: none;
        }
        .login-brand {
            text-align: center;
            margin-bottom: 1.25rem;
        }
        .login-logo-wrap {
            display: flex;
            justify-content: center;
            margin-bottom: 14px;
        }
        .login-logo-wrap img {
            display: block;
            max-width: min(288px, 100%);
            height: auto;
        }
        .login-title {
            margin: 0 0 6px 0;
            font-size: clamp(1.05rem, 2.2vw, 1.55rem);
            color: #1a5276;
            font-weight: 700;
            white-space: nowrap;
            line-height: 1.2;
        }
        .login-subtitle {
            margin: 0;
            color: #718096;
            font-size: 0.88rem;
            line-height: 1.45;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) {
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 6px rgba(26, 82, 118, 0.05);
            border: 1px solid #e2e8f0 !important;
            border-top: 3px solid #1a5276 !important;
            padding: 20px 18px;
            width: 100%;
            box-sizing: border-box;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) .stTextInput > div > div {
            background: #f8fafc;
            border-radius: 8px;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) label p {
            white-space: normal;
            word-break: normal;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) button[kind="primaryFormSubmit"] {
            background: #1a5276;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            white-space: nowrap;
            width: 100%;
        }
        [data-testid="stAppViewContainer"]:has(.login-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]:has(form[data-testid="stForm"]) button[kind="primaryFormSubmit"]:hover {
            background: #154360;
        }
    </style>
    """, unsafe_allow_html=True)

# ========== GRÁFICAS ==========
