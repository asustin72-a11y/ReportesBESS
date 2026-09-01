"""Consulta tarifas CFE vía Playwright (todas las familias de formulario CRE).

Las páginas públicas usan ASP.NET + Incapsula; urllib/POST queda bloqueado,
por eso se automatiza Chromium (ya requerido por recibos PDF).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from bess.cfe.receipt.pdf import _CHROMIUM_LAUNCH_ARGS, _ensure_playwright_chromium
from bess.config.constants import TIPOS_TARIFA
from bess.config.esquema_tarifa import ESQUEMA_DEFAULT, esquema_id_desde_codigo_cfe
from bess.data.ingest.cfe.catalog import FamiliaForm, TarifaCFEDef, tarifa_por_codigo

# —— Selectores ASP.NET ——
_SEL_ANIO = "#ContentPlaceHolder1_Fecha_ddAnio"
_SEL_ANIO_9N = "#ContentPlaceHolder1_Fecha1_ddAnio"
_SEL_MES_T1 = "#ContentPlaceHolder1_MesVerano1_ddMesConsulta"
_SEL_MES_VERANO_INICIO = "#ContentPlaceHolder1_MesVerano1_ddMesVerano"
_SEL_MES_VERANO_CONSULTA = "#ContentPlaceHolder1_MesVerano2_ddMesConsulta"
_SEL_MES_DAC = "#ContentPlaceHolder1_Fecha1_ddMes"
_SEL_MES_GEO = "#ContentPlaceHolder1_Fecha2_ddMes"
_SEL_ESTADO = "#ContentPlaceHolder1_EdoMpoDiv_ddEstado"
_SEL_MUNICIPIO = "#ContentPlaceHolder1_EdoMpoDiv_ddMunicipio"
_SEL_DIVISION = "#ContentPlaceHolder1_EdoMpoDiv_ddDivision"

_MESES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}

_MAPA_CARGO = {
    "base": "Base",
    "basico": "Base",
    "básico": "Base",
    "intermedio": "Intermedio",
    "intermedia": "Intermedio",
    "intermedio bajo": "Intermedio",
    "intermedio alto": "Punta",
    "punta": "Punta",
    "excedente": "Punta",
    "capacidad": "Capacidad",
    "fijo": "CargoFijo",
    "distribucion": "Distribucion",
    "distribución": "Distribucion",
    "energia": "Energia",
    "energía": "Energia",
    "diurno": "Base",
    "nocturno": "Intermedio",
    "cargo unico": "Energia",
    "cargo único": "Energia",
}


class CfeTarifasError(RuntimeError):
    """Error al consultar o interpretar la página de tarifas CFE."""


@dataclass(frozen=True)
class ConsultaTarifaCFE:
    url: str
    anio: int
    mes: int
    estado: str = ""
    municipio: str = ""
    division: str = ""
    esquema_id: str = ESQUEMA_DEFAULT
    region_tabla: str | None = None
    familia: FamiliaForm = FamiliaForm.GEO
    inicio_verano: str = ""  # FEBRERO…MAYO para 1A–1F

    @property
    def requiere_geo(self) -> bool:
        return self.familia == FamiliaForm.GEO


@dataclass
class TablaTarifaCFE:
    """Tabla ya tipada para UI (p. ej. DAC por región)."""

    titulo: str
    columnas: list[str]
    filas: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ResultadoTarifaCFE:
    esquema_id: str
    anio: int
    mes: int
    estado: str
    municipio: str
    division: str
    url: str
    cargos: dict[str, float] = field(default_factory=dict)
    filas_crudas: list[list[str]] = field(default_factory=list)
    tablas: list[TablaTarifaCFE] = field(default_factory=list)
    codigo_tarifa: str = ""
    nombre_tarifa: str = ""
    inicio_verano: str = ""

    def a_matriz_mes(
        self,
        base: dict[str, dict[int, float]] | None = None,
    ) -> dict[str, dict[int, float]]:
        """Matriz TIPOS_TARIFA × 1..12; escribe solo el mes consultado."""
        out: dict[str, dict[int, float]] = {
            tipo: {m: 0.0 for m in range(1, 13)} for tipo in TIPOS_TARIFA
        }
        if base:
            for tipo, valores in base.items():
                if tipo not in out:
                    out[tipo] = {m: 0.0 for m in range(1, 13)}
                for m, v in valores.items():
                    out[tipo][int(m)] = float(v or 0)
        for tipo, valor in self.cargos.items():
            if tipo == "Energia":
                # PDBT / 9CU: un solo $/kWh → Base, sin pisar Base ya parseado.
                if "Base" not in self.cargos:
                    out["Base"][self.mes] = float(valor)
                continue
            if tipo not in out:
                out[tipo] = {m: 0.0 for m in range(1, 13)}
            out[tipo][self.mes] = float(valor)
        if "CargoFijo" in self.cargos and "Suministro" not in self.cargos:
            out["Suministro"][self.mes] = float(self.cargos["CargoFijo"])
        return out

    def publicado(self) -> bool:
        """True si hay al menos un cargo numérico distinto de cero."""
        if any(abs(float(v or 0)) > 1e-9 for v in self.cargos.values()):
            return True
        for tabla in self.tablas:
            for fila in tabla.filas:
                for clave, valor in fila.items():
                    if clave == "Región":
                        continue
                    try:
                        if abs(float(valor or 0)) > 1e-9:
                            return True
                    except (TypeError, ValueError):
                        continue
        return False


def _fold(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").casefold().strip()


def _parse_numero(texto: str) -> float | None:
    limpio = (texto or "").strip().replace(",", "").replace("$", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", limpio):
        return None
    return float(limpio)


def _valor_en_fila(celdas: list[str]) -> float | None:
    for celda in celdas[1:]:
        valor = _parse_numero(celda)
        if valor is not None:
            return valor
    return _parse_numero(celdas[-1]) if celdas else None


def _es_encabezado_tarifa(celdas: list[str]) -> bool:
    folds = {_fold(c) for c in celdas}
    return "tarifa" in folds and ("unidades" in folds or "cargo" in folds)


def _resolver_tipo_cargo(clave: str, primera: str) -> str | None:
    # Preferir tokens compuestos primero.
    for token in ("intermedio bajo", "intermedio alto", "cargo unico", "cargo único"):
        if token in clave:
            return _MAPA_CARGO[token]
    for token, nombre in _MAPA_CARGO.items():
        if token in clave.split() or f" {token} " in f" {clave} ":
            return nombre
    tipo = _MAPA_CARGO.get(_fold(primera))
    if tipo:
        return tipo
    if "energia" in clave or "variable" in clave:
        return "Energia"
    return None


def _extraer_cargos(filas: list[list[str]]) -> dict[str, float]:
    cargos: dict[str, float] = {}
    encabezados = 0
    for fila in filas:
        celdas = [c.strip() for c in fila if str(c).strip()]
        if not celdas:
            continue
        if _es_encabezado_tarifa(celdas):
            encabezados += 1
            if encabezados > 1:
                break
            continue
        if len(celdas) < 2:
            continue
        valor = _valor_en_fila(celdas)
        if valor is None:
            continue
        unidos = " ".join(celdas)
        clave = _fold(unidos)
        if "semipunta" in clave:
            continue
        tipo = _resolver_tipo_cargo(clave, celdas[0])
        if tipo is None:
            # Conservar etiqueta cruda para UI de consulta.
            etiqueta = re.sub(r"\s+", " ", celdas[0]).strip()
            if etiqueta and _parse_numero(etiqueta) is None:
                cargos[etiqueta] = round(valor, 4)
            continue
        cargos[tipo] = round(valor, 4)
    if not cargos:
        raise CfeTarifasError("No se encontraron cargos numéricos en la tabla de tarifas.")
    return cargos


def _es_tabla_regional(filas: list[list[str]]) -> bool:
    if not filas:
        return False
    plano = _fold(" ".join(c for fila in filas[:3] for c in fila))
    return "region" in plano and ("cargo" in plano or "energia" in plano or "fijo" in plano)


def _es_fila_unidad_dac(celdas: list[str]) -> bool:
    plano = _fold(" ".join(celdas))
    if not plano:
        return True
    if plano.startswith("$/") or plano in {"$/mes", "$/kwh"}:
        return True
    return "temporada" in plano and _parse_numero(celdas[0]) is None


def _es_encabezado_regional(celdas: list[str]) -> bool:
    plano = _fold(" ".join(celdas))
    return "region" in plano and ("cargo" in plano or "fijo" in plano)


def _parsear_tabla_dac(filas: list[list[str]]) -> TablaTarifaCFE | None:
    """Convierte una tabla regional DAC (verano o plana) a columnas tipadas."""
    if not _es_tabla_regional(filas):
        return None

    tiene_verano = "verano" in _fold(
        " ".join(c for fila in filas[:3] for c in fila)
    )
    datos: list[dict[str, Any]] = []
    for fila in filas:
        celdas = [c.strip() for c in fila if str(c).strip()]
        if not celdas or _es_encabezado_regional(celdas) or _es_fila_unidad_dac(celdas):
            continue
        region = re.sub(r"\s+", " ", celdas[0]).strip()
        if not region or _parse_numero(region) is not None:
            continue
        nums = [v for c in celdas[1:] if (v := _parse_numero(c)) is not None]
        if not nums:
            continue
        if tiene_verano and len(nums) >= 3:
            datos.append(
                {
                    "Región": region,
                    "Cargo Fijo ($/mes)": round(nums[0], 4),
                    "Energía Verano ($/kWh)": round(nums[1], 4),
                    "Energía Fuera de Verano ($/kWh)": round(nums[2], 4),
                }
            )
        elif len(nums) >= 2:
            datos.append(
                {
                    "Región": region,
                    "Cargo Fijo ($/mes)": round(nums[0], 4),
                    "Energía ($/kWh)": round(nums[1], 4),
                }
            )
        elif len(nums) == 1:
            datos.append(
                {
                    "Región": region,
                    "Cargo Fijo ($/mes)": round(nums[0], 4),
                }
            )

    if not datos:
        return None

    if tiene_verano:
        columnas = [
            "Región",
            "Cargo Fijo ($/mes)",
            "Energía Verano ($/kWh)",
            "Energía Fuera de Verano ($/kWh)",
        ]
        titulo = "Regiones con temporada de verano"
    else:
        columnas = ["Región", "Cargo Fijo ($/mes)", "Energía ($/kWh)"]
        titulo = "Regiones con cargo único de energía"

    return TablaTarifaCFE(titulo=titulo, columnas=columnas, filas=datos)


def _extraer_dac(
    tablas_crudas: list[list[list[str]]],
) -> tuple[dict[str, float], list[TablaTarifaCFE], list[list[str]]]:
    """Parsea todas las tablas regionales DAC (fijo + energía por temporada)."""
    tablas: list[TablaTarifaCFE] = []
    cargos: dict[str, float] = {}
    filas_crudas: list[list[str]] = []

    for bloque in tablas_crudas:
        if not _es_tabla_regional(bloque):
            continue
        if filas_crudas:
            filas_crudas.append([])
        filas_crudas.extend(bloque)
        parseada = _parsear_tabla_dac(bloque)
        if parseada is None:
            continue
        tablas.append(parseada)
        for fila in parseada.filas:
            region = str(fila.get("Región") or "")
            for col, valor in fila.items():
                if col == "Región":
                    continue
                try:
                    num = float(valor)
                except (TypeError, ValueError):
                    continue
                cargos[f"{region} · {col}"] = num

    if not tablas:
        # Fallback: concatenar y usar parser genérico.
        plano = [c for bloque in tablas_crudas for c in bloque]
        return _extraer_cargos(plano), [], plano
    return cargos, tablas, filas_crudas


def _elegir_opcion(opciones: list[dict[str, str]], buscado: str) -> str:
    objetivo = _fold(buscado)
    exactas = [o for o in opciones if _fold(o["label"]) == objetivo]
    if exactas:
        return exactas[0]["value"]
    parciales = [
        o
        for o in opciones
        if objetivo and (objetivo in _fold(o["label"]) or _fold(o["label"]) in objetivo)
    ]
    if len(parciales) == 1:
        return parciales[0]["value"]
    if parciales:
        labels = ", ".join(o["label"] for o in parciales[:8])
        raise CfeTarifasError(f"Opción ambigua {buscado!r}. Coincidencias: {labels}")
    disponibles = ", ".join(o["label"] for o in opciones[:12])
    raise CfeTarifasError(f"No se encontró {buscado!r} en el combo. Ejemplos: {disponibles}")


def _leer_opciones(page: Any, selector: str) -> list[dict[str, str]]:
    return page.eval_on_selector(
        selector,
        """(el) => Array.from(el.options).map(o => ({
            value: o.value,
            label: (o.label || o.text || '').trim()
        }))""",
    )


def listar_opciones_combo(page: Any, selector: str) -> list[str]:
    return [o["label"] for o in _leer_opciones(page, selector) if o["value"] not in ("", "0")]


def _seleccionar(
    page: Any,
    selector: str,
    etiqueta: str,
    *,
    timeout_ms: int,
    settle_ms: int = 700,
) -> str:
    page.wait_for_selector(selector, timeout=timeout_ms)
    opciones = _leer_opciones(page, selector)
    value = _elegir_opcion(opciones, etiqueta)
    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=timeout_ms):
            page.select_option(selector, value=value)
    except Exception:
        page.select_option(selector, value=value)
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 15_000))
        except Exception:
            page.wait_for_timeout(min(settle_ms, 800))
    page.wait_for_timeout(settle_ms)
    return value


def _leer_tablas(
    page: Any,
    region_tabla: str | None = None,
    *,
    todas: bool = False,
) -> list[list[list[str]]]:
    """Lee tablas de cuotas CFE. Con `todas=True` conserva el orden de página."""
    page.wait_for_timeout(300)
    bloques = page.evaluate(
        """({ regionHint, todas }) => {
          const norm = (s) => (s || '')
            .normalize('NFD')
            .replace(/[\\u0300-\\u036f]/g, '')
            .toLowerCase()
            .replace(/\\s+/g, ' ')
            .trim();
          const hint = norm(regionHint || '');

          const bordered = Array.from(
            document.querySelectorAll('table.table-bordered.table-striped')
          );
          const candidates = bordered.length
            ? bordered
            : Array.from(document.querySelectorAll('table'));

          const readRows = (table) => Array.from(table.querySelectorAll('tr')).map(tr =>
            Array.from(tr.querySelectorAll('th,td')).map(td =>
              (td.innerText || '').trim().replace(/\\s+/g, ' ')
            )
          ).filter(r => r.some(Boolean));

          const isTarifa = (rows) => {
            const flat = rows.flat().join(' ').toLowerCase();
            const tieneNum = /\\d/.test(flat);
            const clave = flat.includes('kwh') || flat.includes('$/kwh')
              || flat.includes('kilowatt') || flat.includes('$/mes')
              || flat.includes('cargo') || flat.includes('basico')
              || flat.includes('básico') || flat.includes('excedente')
              || flat.includes('diurno') || flat.includes('nocturno')
              || flat.includes('fijo') || flat.includes('capacidad')
              || flat.includes('region') || flat.includes('región');
            return tieneNum && clave;
          };

          const findLabel = (table) => {
            let el = table;
            for (let depth = 0; depth < 6 && el; depth++) {
              let sib = el.previousElementSibling;
              while (sib) {
                const t = (sib.innerText || '').trim().replace(/\\s+/g, ' ');
                if (t && t.length < 120) return t;
                sib = sib.previousElementSibling;
              }
              el = el.parentElement;
            }
            return '';
          };

          const labeled = [];
          for (const table of candidates) {
            const rows = readRows(table);
            if (!isTarifa(rows)) continue;
            // Excluir el layout gigante de navegación/texto legal.
            if (rows.length > 30) continue;
            labeled.push({ label: findLabel(table), rows });
          }
          if (!labeled.length) return [];

          if (todas) {
            return labeled.map(x => x.rows);
          }

          if (hint) {
            const match = labeled.find(x => {
              const l = norm(x.label);
              const flat = norm(x.rows.flat().join(' '));
              return l.includes(hint) || hint.includes(l) || flat.includes(hint);
            });
            if (match) return [match.rows];
          }
          labeled.sort((a, b) => a.rows.length - b.rows.length);
          return [labeled[0].rows];
        }""",
        {"regionHint": region_tabla, "todas": todas},
    )
    if not bloques:
        raise CfeTarifasError("No apareció la tabla de cuotas tras la selección.")
    return bloques


def _leer_tabla(page: Any, region_tabla: str | None = None) -> list[list[str]]:
    return _leer_tablas(page, region_tabla, todas=False)[0]


def _aplicar_familia(page: Any, consulta: ConsultaTarifaCFE, *, timeout_ms: int) -> None:
    mes_label = _MESES[consulta.mes]
    familia = consulta.familia

    if familia == FamiliaForm.AGRICOLA_9N:
        _seleccionar(page, _SEL_ANIO_9N, str(consulta.anio), timeout_ms=timeout_ms)
        _seleccionar(page, _SEL_MES_T1, mes_label, timeout_ms=timeout_ms)
        return

    if familia == FamiliaForm.DAC:
        page.wait_for_selector(_SEL_ANIO, timeout=timeout_ms)
        _seleccionar(page, _SEL_ANIO, str(consulta.anio), timeout_ms=timeout_ms)
        _seleccionar(page, _SEL_MES_DAC, mes_label, timeout_ms=timeout_ms)
        return

    if familia == FamiliaForm.VERANO:
        page.wait_for_selector(_SEL_ANIO, timeout=timeout_ms)
        _seleccionar(page, _SEL_ANIO, str(consulta.anio), timeout_ms=timeout_ms)
        inicio = (consulta.inicio_verano or "MAYO").upper()
        _seleccionar(page, _SEL_MES_VERANO_INICIO, inicio, timeout_ms=timeout_ms)
        _seleccionar(page, _SEL_MES_VERANO_CONSULTA, mes_label, timeout_ms=timeout_ms)
        return

    if familia == FamiliaForm.T1:
        page.wait_for_selector(_SEL_ANIO, timeout=timeout_ms)
        _seleccionar(page, _SEL_ANIO, str(consulta.anio), timeout_ms=timeout_ms)
        _seleccionar(page, _SEL_MES_T1, mes_label, timeout_ms=timeout_ms)
        return

    # GEO (default)
    page.wait_for_selector(_SEL_MES_GEO, timeout=timeout_ms)
    _seleccionar(page, _SEL_ANIO, str(consulta.anio), timeout_ms=timeout_ms)
    _seleccionar(page, _SEL_MES_GEO, mes_label, timeout_ms=timeout_ms)
    if not (consulta.estado and consulta.municipio and consulta.division):
        raise CfeTarifasError(
            "Esta tarifa requiere Estado, Municipio y División."
        )
    _seleccionar(page, _SEL_ESTADO, consulta.estado, timeout_ms=timeout_ms)
    _seleccionar(page, _SEL_MUNICIPIO, consulta.municipio, timeout_ms=timeout_ms)
    _seleccionar(page, _SEL_DIVISION, consulta.division, timeout_ms=timeout_ms)


def _resultado_desde_bloques(
    consulta: ConsultaTarifaCFE,
    bloques: list[list[list[str]]],
) -> ResultadoTarifaCFE:
    tablas: list[TablaTarifaCFE] = []
    if consulta.familia == FamiliaForm.DAC:
        cargos, tablas, filas = _extraer_dac(bloques)
    else:
        filas = bloques[0]
        cargos = _extraer_cargos(filas)
    return ResultadoTarifaCFE(
        esquema_id=consulta.esquema_id,
        anio=consulta.anio,
        mes=consulta.mes,
        estado=consulta.estado,
        municipio=consulta.municipio,
        division=consulta.division,
        url=consulta.url,
        cargos=cargos,
        filas_crudas=filas,
        tablas=tablas,
        inicio_verano=consulta.inicio_verano,
    )


def consultar_tarifas_cfe(
    consulta: ConsultaTarifaCFE,
    *,
    headless: bool = True,
    timeout_ms: int = 90_000,
) -> ResultadoTarifaCFE:
    if consulta.mes not in _MESES:
        raise CfeTarifasError(f"Mes inválido: {consulta.mes}")
    _ensure_playwright_chromium()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=list(_CHROMIUM_LAUNCH_ARGS),
        )
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(consulta.url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(400)
            _aplicar_familia(page, consulta, timeout_ms=timeout_ms)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:
                pass
            page.wait_for_timeout(500)
            es_dac = consulta.familia == FamiliaForm.DAC
            bloques = _leer_tablas(
                page,
                consulta.region_tabla or consulta.division or None,
                todas=es_dac,
            )
            return _resultado_desde_bloques(consulta, bloques)
        finally:
            browser.close()


def enumerar_geo_completo(
    url: str,
    *,
    anio: int,
    mes: int,
    headless: bool = True,
    timeout_ms: int = 90_000,
    progreso: Any | None = None,
) -> list[dict[str, str]]:
    """Recorre Estado → Municipio → División y devuelve todas las combinaciones."""
    if mes not in _MESES:
        raise CfeTarifasError(f"Mes inválido: {mes}")
    _ensure_playwright_chromium()
    from playwright.sync_api import sync_playwright

    mes_label = _MESES[mes]
    triples: list[dict[str, str]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=list(_CHROMIUM_LAUNCH_ARGS),
        )
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            _seleccionar(page, _SEL_ANIO, str(anio), timeout_ms=timeout_ms)
            _seleccionar(page, _SEL_MES_GEO, mes_label, timeout_ms=timeout_ms)
            estados = listar_opciones_combo(page, _SEL_ESTADO)
            for i, estado in enumerate(estados, start=1):
                if progreso:
                    progreso(f"Estados {i}/{len(estados)}: {estado}")
                _seleccionar(
                    page, _SEL_ESTADO, estado, timeout_ms=timeout_ms, settle_ms=250
                )
                municipios = listar_opciones_combo(page, _SEL_MUNICIPIO)
                for municipio in municipios:
                    _seleccionar(
                        page,
                        _SEL_MUNICIPIO,
                        municipio,
                        timeout_ms=timeout_ms,
                        settle_ms=200,
                    )
                    for division in listar_opciones_combo(page, _SEL_DIVISION):
                        triples.append(
                            {
                                "estado": estado,
                                "municipio": municipio,
                                "division": division,
                            }
                        )
        finally:
            browser.close()
    return triples


def consultar_geo_por_divisiones(
    defn: TarifaCFEDef,
    *,
    anio: int,
    mes: int,
    representantes: list[dict[str, str]],
    headless: bool = True,
    timeout_ms: int = 90_000,
    progreso: Any | None = None,
) -> dict[str, ResultadoTarifaCFE]:
    """Consulta una vez por división usando un (estado, municipio) representante."""
    if mes not in _MESES:
        raise CfeTarifasError(f"Mes inválido: {mes}")
    if defn.familia != FamiliaForm.GEO:
        raise CfeTarifasError(f"{defn.codigo} no es tarifa GEO.")
    _ensure_playwright_chromium()
    from playwright.sync_api import sync_playwright

    out: dict[str, ResultadoTarifaCFE] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=list(_CHROMIUM_LAUNCH_ARGS),
        )
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            for i, rep in enumerate(representantes, start=1):
                division = rep["division"]
                if progreso:
                    progreso(
                        f"Cuotas {i}/{len(representantes)}: {division} "
                        f"({rep['estado']} / {rep['municipio']})"
                    )
                consulta = consulta_desde_catalogo(
                    defn,
                    anio=anio,
                    mes=mes,
                    estado=rep["estado"],
                    municipio=rep["municipio"],
                    division=division,
                )
                page.goto(consulta.url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(300)
                _aplicar_familia(page, consulta, timeout_ms=timeout_ms)
                page.wait_for_timeout(400)
                bloques = _leer_tablas(
                    page,
                    consulta.region_tabla or consulta.division or None,
                    todas=False,
                )
                resultado = _resultado_desde_bloques(consulta, bloques)
                resultado.codigo_tarifa = defn.codigo
                resultado.nombre_tarifa = defn.nombre
                out[division] = resultado
        finally:
            browser.close()
    return out


def consulta_desde_catalogo(
    defn: TarifaCFEDef,
    *,
    anio: int,
    mes: int,
    estado: str = "",
    municipio: str = "",
    division: str = "",
    region_tabla: str | None = None,
    inicio_verano: str = "",
    esquema_id: str | None = None,
) -> ConsultaTarifaCFE:
    return ConsultaTarifaCFE(
        url=defn.url,
        anio=anio,
        mes=mes,
        estado=estado,
        municipio=municipio,
        division=division,
        esquema_id=(esquema_id or esquema_id_desde_codigo_cfe(defn.codigo)).upper(),
        region_tabla=region_tabla,
        familia=defn.familia,
        inicio_verano=inicio_verano,
    )


def consultar_tarifa_catalogo(
    codigo: str,
    *,
    anio: int,
    mes: int,
    estado: str = "",
    municipio: str = "",
    division: str = "",
    region_tabla: str | None = None,
    inicio_verano: str = "",
    headless: bool = True,
    timeout_ms: int = 90_000,
) -> ResultadoTarifaCFE:
    defn = tarifa_por_codigo(codigo)
    if defn is None:
        raise CfeTarifasError(f"Código de tarifa desconocido: {codigo!r}")
    consulta = consulta_desde_catalogo(
        defn,
        anio=anio,
        mes=mes,
        estado=estado,
        municipio=municipio,
        division=division,
        region_tabla=region_tabla,
        inicio_verano=inicio_verano,
    )
    resultado = consultar_tarifas_cfe(
        consulta, headless=headless, timeout_ms=timeout_ms
    )
    resultado.codigo_tarifa = defn.codigo
    resultado.nombre_tarifa = defn.nombre
    return resultado


def explorar_opciones_geo(
    url: str,
    *,
    anio: int,
    mes: int,
    estado: str | None = None,
    municipio: str | None = None,
    headless: bool = True,
    timeout_ms: int = 90_000,
) -> dict[str, list[str]]:
    """Devuelve opciones de Estado / Municipio / División tras seleccionar cascada."""
    if mes not in _MESES:
        raise CfeTarifasError(f"Mes inválido: {mes}")
    _ensure_playwright_chromium()
    from playwright.sync_api import sync_playwright

    mes_label = _MESES[mes]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=list(_CHROMIUM_LAUNCH_ARGS),
        )
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            _seleccionar(page, _SEL_ANIO, str(anio), timeout_ms=timeout_ms)
            _seleccionar(page, _SEL_MES_GEO, mes_label, timeout_ms=timeout_ms)
            out: dict[str, list[str]] = {
                "estados": listar_opciones_combo(page, _SEL_ESTADO),
            }
            if estado:
                _seleccionar(page, _SEL_ESTADO, estado, timeout_ms=timeout_ms)
                out["municipios"] = listar_opciones_combo(page, _SEL_MUNICIPIO)
            if estado and municipio:
                _seleccionar(page, _SEL_MUNICIPIO, municipio, timeout_ms=timeout_ms)
                out["divisiones"] = listar_opciones_combo(page, _SEL_DIVISION)
            return out
        finally:
            browser.close()
