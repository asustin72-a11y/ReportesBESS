"""Esquemas tarifarios por subestación (horario de periodos y precios de energía)."""

from __future__ import annotations

ESQUEMA_DIST = "DIST"
ESQUEMA_GDMTH = "GDMTH"
# Catálogo CFE (ingest/presets); no son esquemas de cálculo BESS.
ESQUEMA_PDBT = "PDBT"
ESQUEMA_T1 = "T1"
ESQUEMA_DEFAULT = ESQUEMA_DIST

# Esquemas usados en periodos / recibo / energía BESS.
ESQUEMAS_CALCULO = frozenset({ESQUEMA_DIST, ESQUEMA_GDMTH})
# Esquemas con CSV en data/Tarifas y filas en catalog_tarifas.
ESQUEMAS_CATALOGO = frozenset(
    {ESQUEMA_DIST, ESQUEMA_GDMTH, ESQUEMA_PDBT, ESQUEMA_T1}
)
# Alias histórico: validación de cálculo BESS.
ESQUEMAS_VALIDOS = ESQUEMAS_CALCULO

FACTOR_CFE_CAPACIDAD_DIST = 0.74
FACTOR_CFE_CAPACIDAD_GDMTH = 0.57

_FACTORES_CFE_CAPACIDAD: dict[str, float] = {
    ESQUEMA_DIST: FACTOR_CFE_CAPACIDAD_DIST,
    ESQUEMA_GDMTH: FACTOR_CFE_CAPACIDAD_GDMTH,
}

# Netmetering: energía por periodo = Σ REC − Σ ENT (puede ser negativa).
# Sin netmetering: energía = Σ max(0, REC−ENT) por intervalo.
_NETMETERING: dict[str, bool] = {
    ESQUEMA_DIST: False,
    ESQUEMA_GDMTH: True,
}


def normalizar_esquema_tarifa(valor: str | None) -> str:
    clave = (valor or ESQUEMA_DEFAULT).strip().upper()
    if clave not in ESQUEMAS_CALCULO:
        return ESQUEMA_DEFAULT
    return clave


def normalizar_esquema_catalogo(valor: str | None) -> str:
    """Normaliza IDs de catálogo (DIST/GDMTH/PDBT/T1); desconocidos → DIST."""
    clave = (valor or ESQUEMA_DEFAULT).strip().upper()
    if clave in ("1", "01"):
        return ESQUEMA_T1
    if clave not in ESQUEMAS_CATALOGO:
        return ESQUEMA_DEFAULT
    return clave


def esquema_id_desde_codigo_cfe(codigo: str | None) -> str:
    """Mapea código CFE del catálogo al id de persistencia (p. ej. 1 → T1)."""
    clave = (codigo or "").strip().upper()
    if clave in ("1", "01", "T1"):
        return ESQUEMA_T1
    if clave in ESQUEMAS_CATALOGO:
        return clave
    return clave


def factor_cfe_capacidad(esquema_id: str | None = None) -> float:
    """Factor de carga CFE para DemandaCalculadaCFE (DIST 0.74 · GDMTH 0.57)."""
    return _FACTORES_CFE_CAPACIDAD.get(
        normalizar_esquema_tarifa(esquema_id),
        FACTOR_CFE_CAPACIDAD_DIST,
    )


def usa_netmetering(esquema_id: str | None = None) -> bool:
    """True si el esquema acumula energía como Σ REC − Σ ENT por periodo (GDMTH)."""
    return _NETMETERING.get(
        normalizar_esquema_tarifa(esquema_id),
        False,
    )


def esquema_tarifa_subestacion(sub_id: str | None) -> str:
    from bess.config.subestaciones import subestacion_por_id

    sub = subestacion_por_id(sub_id or "")
    return sub.esquema_tarifa_id if sub else ESQUEMA_DEFAULT


def esquema_tarifa_prefijo(prefijo: str | None) -> str:
    from bess.config.subestaciones import subestacion_por_prefijo

    sub = subestacion_por_prefijo(prefijo or "")
    return sub.esquema_tarifa_id if sub else ESQUEMA_DEFAULT
