"""Configuracion compartida: Consumo / Generacion / Bidireccional / Neteo."""

from __future__ import annotations

SERVICIOS = ("consumo", "generacion", "bidireccional", "neteo")

COLS_REC = ("BASE_REC", "INTERMEDIO_REC", "PUNTA_REC")
COLS_ENT = ("BASE_ENT", "INTERMEDIO_ENT", "PUNTA_ENT")
COLS_GEN = ("BASE_GEN", "INTERMEDIO_GEN", "PUNTA_GEN")
PERIODOS = ("Base", "Intermedio", "Punta")

PERIODO_A_REC = {
    "Base": "BASE_REC",
    "Intermedio": "INTERMEDIO_REC",
    "Punta": "PUNTA_REC",
}
PERIODO_A_ENT = {
    "Base": "BASE_ENT",
    "Intermedio": "INTERMEDIO_ENT",
    "Punta": "PUNTA_ENT",
}
PERIODO_A_GEN = {
    "Base": "BASE_GEN",
    "Intermedio": "INTERMEDIO_GEN",
    "Punta": "PUNTA_GEN",
}


def normalizar_servicio(valor: str) -> str:
    s = (valor or "consumo").strip().lower()
    if s in ("generación", "generacion"):
        s = "generacion"
    if s not in SERVICIOS:
        raise ValueError(f"Servicio invalido: {valor!r}. Use: {', '.join(SERVICIOS)}")
    return s


def es_bidireccional(servicio: str) -> bool:
    return normalizar_servicio(servicio) == "bidireccional"


def es_neteo(servicio: str) -> bool:
    return normalizar_servicio(servicio) == "neteo"


def es_generacion(servicio: str) -> bool:
    return normalizar_servicio(servicio) == "generacion"


def usa_rec_ent(servicio: str) -> bool:
    """Bidireccional o Neteo: procesan KWH_REC y KWH_ENT del mismo medidor."""
    s = normalizar_servicio(servicio)
    return s in ("bidireccional", "neteo")


def genera_graficas(servicio: str) -> bool:
    """PNG de perfil típico: todos los servicios."""
    return True


def columna_fuente(servicio: str) -> str:
    if es_generacion(servicio):
        return "KWH_ENT"
    return "KWH_REC"


def columnas_periodo(servicio: str) -> tuple[str, ...]:
    if es_bidireccional(servicio):
        return (
            *COLS_REC,
            "TOTAL_REC",
            *COLS_ENT,
            "TOTAL_ENT",
            *COLS_GEN,
            "TOTAL_GEN",
            "CONSUMO_REAL",
        )
    if es_neteo(servicio):
        return (
            *COLS_REC,
            "TOTAL_REC",
            *COLS_ENT,
            "TOTAL_ENT",
            "CONSUMO_REAL",  # = Neteo (REC − ENT)
        )
    return (*COLS_REC, "TOTAL_REC", "CONSUMO_REAL")


def fila_vacia(servicio: str) -> dict[str, float]:
    cols = list(COLS_REC)
    if usa_rec_ent(servicio):
        cols.extend(COLS_ENT)
    if es_bidireccional(servicio):
        cols.extend(COLS_GEN)
    return {c: 0.0 for c in cols}


def valores_con_totales(vals: dict[str, float], servicio: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in COLS_REC:
        out[c] = f"{vals.get(c, 0.0):.6f}"
    total_rec = sum(vals.get(c, 0.0) for c in COLS_REC)
    out["TOTAL_REC"] = f"{total_rec:.6f}"
    if usa_rec_ent(servicio):
        for c in COLS_ENT:
            out[c] = f"{vals.get(c, 0.0):.6f}"
        total_ent = sum(vals.get(c, 0.0) for c in COLS_ENT)
        out["TOTAL_ENT"] = f"{total_ent:.6f}"
        if es_bidireccional(servicio):
            for c in COLS_GEN:
                out[c] = f"{vals.get(c, 0.0):.6f}"
            total_gen = sum(vals.get(c, 0.0) for c in COLS_GEN)
            out["TOTAL_GEN"] = f"{total_gen:.6f}"
            out["CONSUMO_REAL"] = f"{total_rec + total_gen - total_ent:.6f}"
        else:
            # Neteo: CONSUMO_REAL = entregada − recibida
            out["CONSUMO_REAL"] = f"{total_rec - total_ent:.6f}"
    else:
        out["CONSUMO_REAL"] = f"{total_rec:.6f}"
    return out


def extraer_servicio(argv: list[str]) -> tuple[str, list[str]]:
    servicio = "consumo"
    resto: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--servicio" and i + 1 < len(argv):
            servicio = normalizar_servicio(argv[i + 1])
            i += 2
            continue
        if a.startswith("--servicio="):
            servicio = normalizar_servicio(a.split("=", 1)[1])
            i += 1
            continue
        resto.append(a)
        i += 1
    return servicio, resto
