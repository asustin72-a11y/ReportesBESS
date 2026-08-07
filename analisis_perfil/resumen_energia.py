"""Resumen de energia a partir del CSV diario generado."""

from __future__ import annotations

import csv
from pathlib import Path

from servicio_config import (
    COLS_ENT,
    COLS_GEN,
    COLS_REC,
    PERIODOS,
    es_bidireccional,
    es_neteo,
)


def _bloque(sumas: dict[str, float], cols: tuple[str, ...], total_key: str, horaria: bool) -> dict:
    por_periodo = {}
    if horaria:
        for periodo, col in zip(PERIODOS, cols):
            por_periodo[periodo] = sumas.get(col, 0.0)
    total = sumas.get(total_key)
    if total is None:
        total = sum(sumas.get(c, 0.0) for c in cols)
    return {"total": float(total), "por_periodo": por_periodo}


def _neto(a: dict, b: dict, horaria: bool) -> dict:
    """a - b (totales y por periodo)."""
    por = {}
    if horaria:
        for p in PERIODOS:
            por[p] = a["por_periodo"].get(p, 0.0) - b["por_periodo"].get(p, 0.0)
    return {"total": a["total"] - b["total"], "por_periodo": por}


def _suma(a: dict, b: dict, horaria: bool) -> dict:
    por = {}
    if horaria:
        for p in PERIODOS:
            por[p] = a["por_periodo"].get(p, 0.0) + b["por_periodo"].get(p, 0.0)
    return {"total": a["total"] + b["total"], "por_periodo": por}


def resumen_desde_diario(
    diario: Path,
    esquema: str,
    servicio: str,
    region: str | None = None,
) -> dict:
    """Lee el diario y agrega totales del periodo (y por horario si aplica)."""
    sumas: dict[str, float] = {}
    n_dias = 0
    fecha_min = None
    fecha_max = None

    with diario.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Diario sin encabezado: {diario}")
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        for row in reader:
            n_dias += 1
            fh = row[campos["FECHA"]].strip()[:10]
            if fecha_min is None or fh < fecha_min:
                fecha_min = fh
            if fecha_max is None or fh > fecha_max:
                fecha_max = fh
            for key, col in campos.items():
                if key == "FECHA":
                    continue
                try:
                    sumas[key] = sumas.get(key, 0.0) + float(row[col] or 0)
                except ValueError:
                    continue

    horaria = esquema.upper() in ("DIST", "GDMTH")
    bidi = es_bidireccional(servicio)
    neteo_svc = es_neteo(servicio)
    es_t01 = esquema.upper() in ("T01", "SIN")

    rec = _bloque(sumas, COLS_REC, "TOTAL_REC", horaria)

    base = {
        "esquema": "T01" if es_t01 else esquema,
        "servicio": servicio,
        "horaria": horaria,
        "n_dias": n_dias,
        "fecha_min": fecha_min,
        "fecha_max": fecha_max,
        "region": region or "",
    }

    if not bidi and not neteo_svc:
        etiquetas = {
            "consumo": {"REC": "Consumo (KWH_REC)"},
            "generacion": {"REC": "Generacion (KWH_ENT)"},
        }
        resultado = {
            **base,
            "layout": "simple",
            "flujos": {"REC": rec},
            "etiquetas": etiquetas.get(servicio, etiquetas["consumo"]),
        }
        if servicio == "consumo" and fecha_max:
            costo = _costo_consumo(
                esquema,
                rec,
                fecha_max,
                es_t01,
                region=region,
                fecha_min=fecha_min,
            )
            if costo:
                resultado["costo_energia"] = costo
        return resultado

    ent = _bloque(sumas, COLS_ENT, "TOTAL_ENT", horaria)
    neteo = _neto(rec, ent, horaria)

    if neteo_svc:
        # Sin medidor de generación: real = entregada (REC); neteo = REC − ENT
        resultado = {
            **base,
            "layout": "neteo",
            "columnas": {
                "flujos": {
                    "titulo": "Energía",
                    "renglones": [
                        {
                            "etiqueta": "Energia Entregada",
                            "detalle": "KWH_REC",
                            "valores": rec,
                        },
                        {
                            "etiqueta": "Energia Recibida",
                            "detalle": "KWH_ENT",
                            "valores": ent,
                        },
                        {
                            "etiqueta": "Neteo",
                            "detalle": "Entregada - Recibida",
                            "valores": neteo,
                        },
                    ],
                },
            },
        }
        _adjuntar_ahorro(
            resultado,
            neteo,
            rec,
            esquema,
            es_t01,
            fecha_min,
            fecha_max,
            region,
        )
        return resultado

    gen = _bloque(sumas, COLS_GEN, "TOTAL_GEN", horaria)
    consumo_real = _neto(_suma(rec, gen, horaria), ent, horaria)

    resultado = {
        **base,
        "layout": "bidireccional_3col",
        "columnas": {
            "consumo_facturado": {
                "titulo": "Consumo Facturado",
                "renglones": [
                    {
                        "etiqueta": "Energia Entregada",
                        "detalle": "KWH_REC consumo",
                        "valores": rec,
                    },
                    {
                        "etiqueta": "Energia Recibida",
                        "detalle": "KWH_ENT consumo",
                        "valores": ent,
                    },
                    {
                        "etiqueta": "Neteo",
                        "detalle": "Entregada - Recibida",
                        "valores": neteo,
                    },
                ],
            },
            "generacion": {
                "titulo": "Generacion",
                "renglones": [
                    {
                        "etiqueta": "Energia Generada",
                        "detalle": "KWH_ENT generacion",
                        "valores": gen,
                    },
                ],
            },
            "consumo_real": {
                "titulo": "Consumo Real",
                "renglones": [
                    {
                        "etiqueta": "Consumo Real",
                        "detalle": "REC + GEN - ENT",
                        "valores": consumo_real,
                    },
                ],
            },
        },
    }

    _adjuntar_ahorro(
        resultado,
        neteo,
        consumo_real,
        esquema,
        es_t01,
        fecha_min,
        fecha_max,
        region,
    )
    return resultado


def _adjuntar_ahorro(
    resultado: dict,
    neteo: dict,
    real: dict,
    esquema: str,
    es_t01: bool,
    fecha_min,
    fecha_max,
    region: str | None,
) -> None:
    if not fecha_max:
        return
    if es_t01:
        from tarifa_01 import calcular_ahorro

        resultado["ahorro_energia"] = calcular_ahorro(
            neteo["total"],
            real["total"],
            fecha_max,
            fecha_inicio_periodo=fecha_min,
        )
        if resultado.get("layout") == "neteo":
            resultado["ahorro_energia"]["etiqueta_real"] = "Costo Real (Entregada)"
            resultado["ahorro_energia"]["etiqueta_ahorro"] = "Ahorro (Real − Neteo)"
    elif esquema.upper() == "DIST":
        from tarifa_dist import calcular_ahorro as calcular_ahorro_dist

        resultado["ahorro_energia"] = calcular_ahorro_dist(
            neteo.get("por_periodo") or {},
            real.get("por_periodo") or {},
            fecha_max,
            region=region,
        )
        if resultado.get("layout") == "neteo":
            resultado["ahorro_energia"]["etiqueta_real"] = "Costo Real (Entregada)"
    elif esquema.upper() == "GDMTH":
        from tarifa_gdmth import calcular_ahorro as calcular_ahorro_gdmth

        resultado["ahorro_energia"] = calcular_ahorro_gdmth(
            neteo.get("por_periodo") or {},
            real.get("por_periodo") or {},
            fecha_max,
            region=region,
        )
        if resultado.get("layout") == "neteo":
            resultado["ahorro_energia"]["etiqueta_real"] = "Costo Real (Entregada)"


def _costo_consumo(
    esquema: str,
    rec: dict,
    fecha_max: str,
    es_t01: bool,
    region: str | None = None,
    fecha_min: str | None = None,
) -> dict | None:
    """Costo del consumo (T01: prorrateo diario CFE si el periodo cruza meses)."""
    try:
        if es_t01:
            from tarifa_01 import calcular_costo

            return calcular_costo(
                rec["total"],
                fecha_max,
                fecha_inicio_periodo=fecha_min,
            )
        if esquema.upper() == "DIST":
            from tarifa_dist import calcular_costo as calcular_costo_dist

            return calcular_costo_dist(
                rec.get("por_periodo") or {}, fecha_max, region=region
            )
        if esquema.upper() == "GDMTH":
            from tarifa_gdmth import calcular_costo as calcular_costo_gdmth

            return calcular_costo_gdmth(
                rec.get("por_periodo") or {}, fecha_max, region=region
            )
    except (FileNotFoundError, ValueError):
        return None
    return None


def _fmt_bloque(valores: dict, horaria: bool, indent: str = "    ") -> list[str]:
    lineas = [f"{indent}Total: {valores['total']:,.3f} kWh"]
    if horaria and valores.get("por_periodo"):
        for periodo in PERIODOS:
            val = valores["por_periodo"].get(periodo, 0.0)
            lineas.append(f"{indent}  {periodo:<11}: {val:,.3f} kWh")
    return lineas


def _fmt_escalones(
    escalones: dict | None,
    indent: str = "    ",
    etiquetas: tuple[tuple[str, str], ...] | None = None,
) -> list[str]:
    if not escalones:
        return []
    nombres = etiquetas or (
        ("basico", "Basico"),
        ("intermedio", "Intermedio"),
        ("excedente", "Excedente"),
    )
    lineas = []
    for clave, nombre in nombres:
        esc = escalones.get(clave) or {}
        lineas.append(
            f"{indent}{nombre:<11}: {float(esc.get('kwh', 0)):,.3f} kWh  "
            f"${float(esc.get('importe', 0)):,.2f}"
        )
    return lineas


def formatear_resumen(resumen: dict) -> str:
    lineas = [
        "RESUMEN DE ENERGIA",
        f"  Periodo : {resumen['fecha_min']} -> {resumen['fecha_max']}  "
        f"({resumen['n_dias']} dias)",
        f"  Tarifa  : {resumen['esquema']}",
        f"  Servicio: {resumen['servicio']}",
        "",
    ]
    horaria = resumen["horaria"]

    if resumen.get("layout") in ("bidireccional_3col", "neteo"):
        for col in resumen["columnas"].values():
            lineas.append(f"  === {col['titulo']} ===")
            for ren in col["renglones"]:
                lineas.append(f"  {ren['etiqueta']} ({ren['detalle']})")
                lineas.extend(_fmt_bloque(ren["valores"], horaria))
            lineas.append("")
        ahorro = resumen.get("ahorro_energia")
        if ahorro:
            etiq = tuple(ahorro.get("etiquetas_escalones") or ())
            titulo = ahorro.get("titulo_tarifa") or resumen["esquema"]
            precios = ahorro["precios"]
            precios_txt = "  ".join(
                f"{k[0].upper()}={v:.4f}" for k, v in precios.items()
            )
            etiqueta_real = (
                "Costo Real (Entregada)"
                if resumen.get("layout") == "neteo"
                else "Costo Consumo Real"
            )
            lineas.extend(
                [
                    "  === Ahorro de Energia (MXN) ===",
                    f"  Tarifa vigente ({titulo}): {ahorro['fecha_tarifa']}  "
                    f"({precios_txt})",
                    f"  Costo Neteo       : ${ahorro['neteo']['importe']:,.2f}  "
                    f"({ahorro['neteo']['kwh']:,.3f} kWh)",
                    *_fmt_escalones(
                        ahorro["neteo"].get("escalones"), "    ", etiq or None
                    ),
                    f"  Ahorro (Real-Neteo): ${ahorro['ahorro']:,.2f}",
                    f"  {etiqueta_real}: ${ahorro['real']['importe']:,.2f}  "
                    f"({ahorro['real']['kwh']:,.3f} kWh)",
                    *_fmt_escalones(
                        ahorro["real"].get("escalones"), "    ", etiq or None
                    ),
                    "",
                ]
            )
        return "\n".join(lineas).rstrip() + "\n"

    for clave, bloque in resumen["flujos"].items():
        titulo = resumen["etiquetas"].get(clave, clave)
        lineas.append(f"  {titulo}")
        lineas.extend(_fmt_bloque(bloque, horaria))
        lineas.append("")
    costo = resumen.get("costo_energia")
    if costo:
        etiq = tuple(costo.get("etiquetas_escalones") or ())
        titulo = costo.get("titulo_tarifa") or resumen["esquema"]
        precios = costo["precios"]
        precios_txt = "  ".join(f"{k[0].upper()}={v:.4f}" for k, v in precios.items())
        cons = costo["consumo"]
        lineas.extend(
            [
                "  === Costo de Energia (MXN) ===",
                f"  Tarifa vigente ({titulo}): {costo['fecha_tarifa']}  "
                f"({precios_txt})",
                f"  Costo Consumo     : ${cons['importe']:,.2f}  "
                f"({cons['kwh']:,.3f} kWh)",
                *_fmt_escalones(cons.get("escalones"), "    ", etiq or None),
                "",
            ]
        )
    return "\n".join(lineas).rstrip() + "\n"


def imprimir_resumen(resumen: dict) -> None:
    print("\n" + "=" * 60)
    print(formatear_resumen(resumen), end="")
    print("=" * 60)
