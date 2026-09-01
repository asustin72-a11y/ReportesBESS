"""Sincroniza el catálogo de tarifas desde app.cfe.mx (CSV + SQLite)."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from bess.config.constants import TIPOS_TARIFA, archivo_tarifas_csv
from bess.config.esquema_tarifa import (
    ESQUEMA_DIST,
    ESQUEMA_GDMTH,
    ESQUEMA_PDBT,
    ESQUEMA_T1,
    ESQUEMAS_CATALOGO,
)
from bess.config.paths import DIRECTORIO_TARIFAS
from bess.data.tariffs_db import (
    fusionar_preferir_positivo,
    guardar_tarifas_dict,
    leer_matriz_para_sync,
    upsert_tarifas_hist_mes,
)
from bess.tariffs.loader import invalidar_cache_tarifas

# Un preset geográfico por esquema persistible.
PRESET_POR_ESQUEMA: dict[str, str] = {
    ESQUEMA_DIST: "jocotitlan",
    ESQUEMA_GDMTH: "aragon",
    ESQUEMA_PDBT: "miguel_hidalgo",
    ESQUEMA_T1: "tarifa1",
}


@dataclass
class ResultadoSyncTarifa:
    ok: bool
    esquema_id: str
    preset_id: str
    anio: int
    mes: int
    mensaje: str
    cargos: dict[str, float] = field(default_factory=dict)
    ruta_csv: str = ""


def _escribir_csv(esquema_id: str, anio: int, matriz: dict) -> Path:
    ruta = DIRECTORIO_TARIFAS / archivo_tarifas_csv(anio, esquema=esquema_id)
    DIRECTORIO_TARIFAS.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Tarifa", *[str(m) for m in range(1, 13)]])
        for tipo in TIPOS_TARIFA:
            valores = matriz.get(tipo, {})
            writer.writerow([tipo, *[valores.get(m, 0.0) for m in range(1, 13)]])
    return ruta


def persistir_resultado_cfe(resultado) -> Path:
    """Fusiona el mes consultado en CSV, catalog_tarifas y catalog_tarifas_hist.

    Protege datos ya cargados: CSV∪BD como base; un cero de CFE no pisa
    un mes/tipo con valor > 0.
    """
    base = leer_matriz_para_sync(resultado.esquema_id, resultado.anio)
    matriz = fusionar_preferir_positivo(
        base, resultado.a_matriz_mes(base)
    )
    ruta = _escribir_csv(resultado.esquema_id, resultado.anio, matriz)
    guardar_tarifas_dict(
        matriz,
        resultado.esquema_id,
        resultado.anio,
        preservar_positivos=True,
    )
    upsert_tarifas_hist_mes(
        matriz, resultado.esquema_id, resultado.anio, resultado.mes
    )
    invalidar_cache_tarifas()
    return ruta


def sincronizar_esquema_cfe(
    esquema_id: str,
    *,
    anio: int | None = None,
    mes: int | None = None,
) -> ResultadoSyncTarifa:
    """Consulta CFE (Playwright) y persiste el mes del esquema indicado."""
    from bess.data.ingest.cfe import CfeTarifasError, consultar_preset

    hoy = date.today()
    anio_i = int(anio or hoy.year)
    mes_i = int(mes or hoy.month)
    esquema = (esquema_id or "").strip().upper()
    if esquema not in ESQUEMAS_CATALOGO:
        return ResultadoSyncTarifa(
            ok=False,
            esquema_id=esquema,
            preset_id="",
            anio=anio_i,
            mes=mes_i,
            mensaje=(
                f"Esquema {esquema} no es persistible "
                f"({', '.join(sorted(ESQUEMAS_CATALOGO))})."
            ),
        )
    preset_id = PRESET_POR_ESQUEMA[esquema]
    try:
        resultado = consultar_preset(preset_id, anio=anio_i, mes=mes_i)
    except CfeTarifasError as exc:
        return ResultadoSyncTarifa(
            ok=False,
            esquema_id=esquema,
            preset_id=preset_id,
            anio=anio_i,
            mes=mes_i,
            mensaje=f"CFE aún no publica o falló el parseo: {exc}",
        )
    except Exception as exc:
        return ResultadoSyncTarifa(
            ok=False,
            esquema_id=esquema,
            preset_id=preset_id,
            anio=anio_i,
            mes=mes_i,
            mensaje=f"Error al consultar CFE: {exc}",
        )

    if not resultado.publicado():
        return ResultadoSyncTarifa(
            ok=False,
            esquema_id=esquema,
            preset_id=preset_id,
            anio=anio_i,
            mes=mes_i,
            mensaje=(
                "CFE respondió sin energía/capacidad > 0 "
                "(publicación parcial o mes aún no publicado)."
            ),
        )

    ruta = persistir_resultado_cfe(resultado)
    resumen = ", ".join(
        f"{k}={v}" for k, v in list(resultado.cargos.items())[:6]
    )
    return ResultadoSyncTarifa(
        ok=True,
        esquema_id=esquema,
        preset_id=preset_id,
        anio=anio_i,
        mes=mes_i,
        mensaje=f"Guardado {esquema}/{anio_i}-{mes_i:02d} → {ruta.name} · {resumen}",
        cargos=dict(resultado.cargos),
        ruta_csv=str(ruta),
    )


def sincronizar_catalogo_cfe(
    *,
    anio: int | None = None,
    mes: int | None = None,
    esquemas: tuple[str, ...] | None = None,
) -> list[ResultadoSyncTarifa]:
    """Sincroniza varios esquemas (por defecto todo ESQUEMAS_CATALOGO)."""
    orden = esquemas or (ESQUEMA_DIST, ESQUEMA_GDMTH, ESQUEMA_PDBT, ESQUEMA_T1)
    return [
        sincronizar_esquema_cfe(esquema, anio=anio, mes=mes) for esquema in orden
    ]
