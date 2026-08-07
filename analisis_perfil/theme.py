"""Paleta alineada con bess/config/theme.py de la suite IUSASOL."""

COLORES = {
    "primary": "#1a5276",
    "secondary": "#2e86c1",
    "success": "#27ae60",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "base": "#3498db",
    "intermedio": "#f1c40f",
    "punta": "#e74c3c",
    "muted": "#718096",
    "border": "#e2e8f0",
    "panel": "#f8fafc",
    "text": "#1a202c",
}

TARIFAS = {
    0: {"codigo": "0", "clave": "T01", "etiqueta": "Tarifa 01 (doméstica)"},
    1: {"codigo": "1", "clave": "GDMTH", "etiqueta": "GDMTH (horaria)"},
    2: {"codigo": "2", "clave": "DIST", "etiqueta": "DIST (horaria)"},
}

SERVICIOS = {
    "consumo": {
        "etiqueta": "Consumo",
        "desc": "Procesa KWH_REC · incluye gráficas",
    },
    "generacion": {
        "etiqueta": "Generación",
        "desc": "Procesa KWH_ENT · incluye gráficas",
    },
    "bidireccional": {
        "etiqueta": "Bidireccional",
        "desc": "REC+ENT del consumo y GEN (=KWH_ENT generacion) · con gráficas",
    },
    "neteo": {
        "etiqueta": "Neteo",
        "desc": "Un medidor: REC + ENT → entregada, recibida, neteo y costos · con gráficas",
    },
}

# 17 divisiones CNE (mismo orden que tarifas_cfe_catalog / reportes suite).
DIVISIONES = (
    "Baja California",
    "Baja California Sur",
    "Bajío",
    "Centro Occidente",
    "Centro Oriente",
    "Centro Sur",
    "Golfo Centro",
    "Golfo Norte",
    "Jalisco",
    "Noroeste",
    "Norte",
    "Oriente",
    "Peninsular",
    "Sureste",
    "Valle de México Centro",
    "Valle de México Norte",
    "Valle de México Sur",
)

REGION_POR_TARIFA = {
    "DIST": "Centro Sur",
    "GDMTH": "Valle de México Norte",
}
