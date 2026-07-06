"""Idcodes y resolución de medidores ISOL."""

from __future__ import annotations

from typing import Any

# Patrones de serial en ISOL/Meters (CS3878=BESS IUSA1, CS3190=BESS IUSA2).
ALIAS_SERIAL: dict[str, tuple[str, ...]] = {
    "BESS": ("CS3878", "BESS"),
    "banco1": ("CS1996", "BANCO1", "BANCO"),
    "banco": ("CS1996", "BANCO1", "BANCO"),
    "banco2": ("BANCO2",),
    "bess_iusa2": ("CS3190", "BESS_IUSA2", "BESSIUSA2"),
    "cogeneracion": ("CS1305", "COGENERACION", "COGEN"),
}

# Referencia histórica (puede estar desactualizada; preferir resolver_id_medidor).
MEDIDORES_ISOL: dict[str, str] = {
    'banco1': 'GWE6odW7OrhHrb4ZXx4jj2-omXF9l0UhvnpxCOqCpnIGZOJS3I6muHaiHYnL2oJ9',
    'BESS': '7AsKPv5OgZNSZD8GE0TTOReNjVWpBDa5Te883xmMMeLqfj7sYuI2eMS8GD6jiyWJ',
    'banco2': 'lDND_R3WT0QPZ-xyx2Qh1riOE4j37GAukMilMhR3IPfORYinfLxsTDQOFLetq4ex',
}


def _normalizar_alias(medidor_o_id: str) -> str:
    return medidor_o_id.strip()


def _es_idcode(valor: str) -> bool:
    return len(valor) >= 32 and ' ' not in valor


def serial_patron(numero_serie: str) -> str:
    """Primer token del Numero_Serie del catálogo (ej. CS1980 de 'CS1980 VL2E 19NB')."""
    texto = (numero_serie or "").strip().upper()
    if not texto:
        return ""
    return texto.split()[0]


def buscar_idcode_por_serie(numero_serie: str, medidores_api: Any) -> str | None:
    """Busca idcode en ISOL/Meters por coincidencia con Numero_Serie del catálogo."""
    patron = serial_patron(numero_serie)
    if not patron:
        return None

    items = medidores_api.get("meters", []) if isinstance(medidores_api, dict) else medidores_api
    if not isinstance(items, list):
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        serial = str(item.get("serial", "")).upper()
        idcode = item.get("idcode") or item.get("id")
        if not idcode:
            continue
        if patron in serial:
            return str(idcode)
    return None


def resolver_id_medidor(
    medidor_o_id: str,
    medidores_api: Any | None = None,
    *,
    numero_serie: str | None = None,
) -> str:
    """Resuelve nombre/alias/serial → idcode usando la lista ISOL/Meters."""
    if numero_serie and medidores_api is not None:
        idcode = buscar_idcode_por_serie(numero_serie, medidores_api)
        if idcode:
            return idcode

    clave = _normalizar_alias(medidor_o_id)
    if _es_idcode(clave):
        return clave

    alias_key = clave
    for nombre in ALIAS_SERIAL:
        if nombre.lower() == clave.lower():
            alias_key = nombre
            break

    if medidores_api is not None:
        idcode = _buscar_en_api(alias_key, medidores_api)
        if idcode:
            return idcode

    if alias_key in MEDIDORES_ISOL:
        return MEDIDORES_ISOL[alias_key]
    if clave.lower() in {k.lower() for k in MEDIDORES_ISOL}:
        for nombre, idcode in MEDIDORES_ISOL.items():
            if nombre.lower() == clave.lower():
                return idcode

    raise ValueError(
        f'No se encontró idcode para "{medidor_o_id}"'
        + (f' (serie {serial_patron(numero_serie)!r})' if numero_serie else "")
        + ". Verifique Numero_Serie en Medidores.csv o ejecute "
        "scripts/listar_medidores_iusasol.py --pretty."
    )


def _buscar_en_api(alias: str, medidores_api: Any) -> str | None:
    items = medidores_api.get('meters', []) if isinstance(medidores_api, dict) else medidores_api
    if not isinstance(items, list):
        return None

    patrones = ALIAS_SERIAL.get(alias, (alias,))
    patrones_upper = tuple(p.upper() for p in patrones)

    for item in items:
        if not isinstance(item, dict):
            continue
        serial = str(item.get('serial', '')).upper()
        idcode = item.get('idcode') or item.get('id')
        if not idcode:
            continue
        if any(p in serial for p in patrones_upper):
            return str(idcode)
    return None
