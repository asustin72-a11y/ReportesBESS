"""Catálogo de subestaciones y medidores desde CSV en data/Tarifas/."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from bess.config.paths import DIRECTORIO_TARIFAS

ARCHIVO_SUBESTACIONES = "Subestaciones.csv"
ARCHIVO_MEDIDORES = "Medidores.csv"
ARCHIVO_TIPO_MEDIDOR = "Tipo_Medidor.csv"

FORMATO_VALIDADO = "%d/%m/%Y %H:%M"
PUERTO_MODBUS_DEFAULT = 502
TIPO_FACTURACION = 1
TIPO_TESTIGO = 2
TIPO_BESS = 3
TIPO_GENERACION = 4
TIPO_COGENERACION = 5
DESCARGAS_VALIDAS = frozenset({"ION", "API"})
REACTIVOS_VALIDOS = frozenset({0, 1, 2})


class CatalogError(Exception):
    """Errores de carga o validación del catálogo."""

    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("\n".join(errores))


@dataclass(frozen=True)
class ReglasTipoMedidor:
    tipo: int
    descripcion: str
    neteo: bool
    invertir: bool
    reactivos: int


@dataclass(frozen=True)
class SubestacionCatalogo:
    numero: int
    nombre: str
    generacion: bool


@dataclass(frozen=True)
class MedidorCatalogo:
    nombre: str
    numero_serie: str
    subestacion_numero: int
    subestacion_nombre: str
    tipo_medidor: int
    descarga: str
    ip: str
    puerto: int
    grupo_generacion: str
    validado: datetime | None

    @property
    def es_facturacion(self) -> bool:
        return self.tipo_medidor == TIPO_FACTURACION

    @property
    def es_testigo(self) -> bool:
        return self.tipo_medidor == TIPO_TESTIGO

    @property
    def es_bess(self) -> bool:
        return self.tipo_medidor == TIPO_BESS

    @property
    def es_generacion(self) -> bool:
        return self.tipo_medidor == TIPO_GENERACION

    @property
    def es_cogeneracion(self) -> bool:
        return self.tipo_medidor == TIPO_COGENERACION

    @property
    def validado_ok(self) -> bool:
        return self.validado is not None


@dataclass(frozen=True)
class Catalogo:
    subestaciones: tuple[SubestacionCatalogo, ...]
    medidores: tuple[MedidorCatalogo, ...]
    tipos: tuple[ReglasTipoMedidor, ...]

    def subestacion_por_numero(self, numero: int) -> SubestacionCatalogo | None:
        for sub in self.subestaciones:
            if sub.numero == numero:
                return sub
        return None

    def subestacion_por_nombre(self, nombre: str) -> SubestacionCatalogo | None:
        clave = (nombre or "").strip()
        for sub in self.subestaciones:
            if sub.nombre == clave:
                return sub
        return None

    def medidor_por_nombre(self, nombre: str) -> MedidorCatalogo | None:
        clave = (nombre or "").strip()
        for med in self.medidores:
            if med.nombre == clave:
                return med
        return None

    def medidores_subestacion(self, subestacion_nombre: str) -> list[MedidorCatalogo]:
        return [m for m in self.medidores if m.subestacion_nombre == subestacion_nombre]

    def medidores_facturacion_y_testigo(self, subestacion_nombre: str) -> list[MedidorCatalogo]:
        return [
            m
            for m in self.medidores_subestacion(subestacion_nombre)
            if m.tipo_medidor in (TIPO_FACTURACION, TIPO_TESTIGO)
        ]

    def reglas_tipo(self, tipo: int) -> ReglasTipoMedidor | None:
        for regla in self.tipos:
            if regla.tipo == tipo:
                return regla
        return None

    def todos_validados(self) -> bool:
        return all(m.validado_ok for m in self.medidores_requieren_validacion())

    def medidores_sin_validar(self) -> list[MedidorCatalogo]:
        return [m for m in self.medidores if m.descarga in DESCARGAS_VALIDAS and not m.validado_ok]

    def medidores_requieren_validacion(self) -> list[MedidorCatalogo]:
        return [m for m in self.medidores if m.descarga in DESCARGAS_VALIDAS]


def _leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.is_file():
        raise CatalogError([f"No se encuentra el archivo: {ruta}"])
    with ruta.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _bool_csv(valor: str) -> bool:
    return str(valor or "").strip() in {"1", "true", "True", "SI", "si", "Sí"}


def _int_csv(valor: str, *, campo: str, fila: str) -> int:
    texto = str(valor or "").strip()
    if not texto:
        raise CatalogError([f'{fila}: falta "{campo}".'])
    try:
        return int(texto)
    except ValueError as exc:
        raise CatalogError([f'{fila}: "{campo}" debe ser entero ({texto}).']) from exc


def _parse_validado(valor: str) -> datetime | None:
    texto = str(valor or "").strip()
    if not texto:
        return None
    try:
        return datetime.strptime(texto, FORMATO_VALIDADO)
    except ValueError as exc:
        raise CatalogError(
            [f'Validado debe usar {FORMATO_VALIDADO!r} (recibido: {texto!r}).']
        ) from exc


def _parse_puerto(valor: str, descarga: str) -> int:
    texto = str(valor or "").strip()
    if not texto:
        if descarga == "ION":
            return PUERTO_MODBUS_DEFAULT
        return 0
    return _int_csv(texto, campo="Puerto", fila="Medidor")


def _cargar_tipos(directorio: Path) -> tuple[ReglasTipoMedidor, ...]:
    filas = _leer_csv(directorio / ARCHIVO_TIPO_MEDIDOR)
    if not filas:
        raise CatalogError([f"{ARCHIVO_TIPO_MEDIDOR} está vacío."])
    tipos: list[ReglasTipoMedidor] = []
    for fila in filas:
        tipo = _int_csv(fila.get("Tipo", ""), campo="Tipo", fila=ARCHIVO_TIPO_MEDIDOR)
        reactivos = _int_csv(
            fila.get("Reactivos", ""), campo="Reactivos", fila=ARCHIVO_TIPO_MEDIDOR
        )
        if reactivos not in REACTIVOS_VALIDOS:
            raise CatalogError(
                [f"Tipo {tipo}: Reactivos debe ser 0, 1 o 2 (recibido {reactivos})."]
            )
        tipos.append(
            ReglasTipoMedidor(
                tipo=tipo,
                descripcion=str(fila.get("Descripcion", "")).strip(),
                neteo=_bool_csv(fila.get("Neteo", "")),
                invertir=_bool_csv(fila.get("Invertir", "")),
                reactivos=reactivos,
            )
        )
    return tuple(tipos)


def _cargar_subestaciones(directorio: Path) -> tuple[SubestacionCatalogo, ...]:
    filas = _leer_csv(directorio / ARCHIVO_SUBESTACIONES)
    if not filas:
        raise CatalogError([f"{ARCHIVO_SUBESTACIONES} está vacío."])
    subs: list[SubestacionCatalogo] = []
    numeros: set[int] = set()
    nombres: set[str] = set()
    for fila in filas:
        numero = _int_csv(fila.get("Numero", ""), campo="Numero", fila=ARCHIVO_SUBESTACIONES)
        nombre = str(fila.get("Nombre", "")).strip()
        if not nombre:
            raise CatalogError([f"Subestación {numero}: falta Nombre."])
        if numero in numeros:
            raise CatalogError([f"Subestación duplicada: Numero={numero}."])
        if nombre in nombres:
            raise CatalogError([f"Subestación duplicada: Nombre={nombre}."])
        numeros.add(numero)
        nombres.add(nombre)
        subs.append(
            SubestacionCatalogo(
                numero=numero,
                nombre=nombre,
                generacion=_bool_csv(fila.get("Generacion", "")),
            )
        )
    return tuple(subs)


def _cargar_medidores(
    directorio: Path,
    subs: tuple[SubestacionCatalogo, ...],
    tipos: tuple[ReglasTipoMedidor, ...],
) -> tuple[MedidorCatalogo, ...]:
    filas = _leer_csv(directorio / ARCHIVO_MEDIDORES)
    if not filas:
        raise CatalogError([f"{ARCHIVO_MEDIDORES} está vacío."])
    sub_por_numero = {s.numero: s for s in subs}
    tipos_ok = {t.tipo for t in tipos}
    nombres_vistos: set[str] = set()
    medidores: list[MedidorCatalogo] = []

    for fila in filas:
        nombre = str(fila.get("Nombre", "")).strip()
        if not nombre:
            raise CatalogError(["Medidor sin Nombre en Medidores.csv."])
        if nombre in nombres_vistos:
            raise CatalogError([f'Medidor duplicado: "{nombre}".'])
        nombres_vistos.add(nombre)

        sub_num = _int_csv(
            fila.get("Subestacion", ""), campo="Subestacion", fila=f'Medidor "{nombre}"'
        )
        sub = sub_por_numero.get(sub_num)
        if sub is None:
            raise CatalogError(
                [f'Medidor "{nombre}": Subestacion={sub_num} no existe.']
            )

        tipo = _int_csv(
            fila.get("Tipo_Medidor", ""), campo="Tipo_Medidor", fila=f'Medidor "{nombre}"'
        )
        if tipo not in tipos_ok:
            raise CatalogError(
                [f'Medidor "{nombre}": Tipo_Medidor={tipo} no definido.']
            )

        descarga = str(fila.get("Descarga", "")).strip().upper()
        if descarga not in DESCARGAS_VALIDAS:
            raise CatalogError(
                [f'Medidor "{nombre}": Descarga debe ser ION o API.']
            )

        ip = str(fila.get("IP", "")).strip()
        puerto = _parse_puerto(fila.get("Puerto", ""), descarga)
        numero_serie = str(fila.get("Numero_Serie", "")).strip()
        grupo = str(fila.get("Grupo_Generacion", "")).strip()
        validado = _parse_validado(fila.get("Validado", ""))

        medidores.append(
            MedidorCatalogo(
                nombre=nombre,
                numero_serie=numero_serie,
                subestacion_numero=sub_num,
                subestacion_nombre=sub.nombre,
                tipo_medidor=tipo,
                descarga=descarga,
                ip=ip,
                puerto=puerto,
                grupo_generacion=grupo,
                validado=validado,
            )
        )
    return tuple(medidores)


def _validar_reglas_negocio(catalogo: Catalogo) -> list[str]:
    errores: list[str] = []

    for sub in catalogo.subestaciones:
        meds = catalogo.medidores_subestacion(sub.nombre)
        if not meds:
            errores.append(f'Subestación "{sub.nombre}": sin medidores asignados.')

        facturacion = [m for m in meds if m.tipo_medidor == TIPO_FACTURACION]
        testigos = [m for m in meds if m.tipo_medidor == TIPO_TESTIGO]
        bess = [m for m in meds if m.tipo_medidor == TIPO_BESS]
        generacion = [m for m in meds if m.tipo_medidor == TIPO_GENERACION]
        cogeneracion = [m for m in meds if m.tipo_medidor == TIPO_COGENERACION]

        if len(facturacion) != 1:
            errores.append(
                f'Subestación "{sub.nombre}": debe tener exactamente 1 medidor tipo 1 '
                f"(Neteo/facturación); tiene {len(facturacion)}."
            )
        if not bess:
            errores.append(
                f'Subestación "{sub.nombre}": requiere al menos 1 medidor tipo 3 (BESS).'
            )
        if generacion and not sub.generacion:
            errores.append(
                f'Subestación "{sub.nombre}": hay medidores tipo 4 pero Generacion=0.'
            )
        if sub.generacion:
            if not generacion:
                errores.append(
                    f'Subestación "{sub.nombre}": Generacion=1 pero no hay medidores tipo 4.'
                )
            sin_grupo = [m.nombre for m in generacion if not m.grupo_generacion]
            if sin_grupo:
                errores.append(
                    f'Subestación "{sub.nombre}": medidores tipo 4 sin Grupo_Generacion: '
                    f"{', '.join(sin_grupo)}."
                )
        if len(cogeneracion) > 1:
            errores.append(
                f'Subestación "{sub.nombre}": solo se permite 1 medidor tipo 5 (Cogeneración).'
            )
        if cogeneracion and sub.generacion:
            errores.append(
                f'Subestación "{sub.nombre}": tipo 5 (Cogeneración) y granja (tipo 4) '
                "no pueden coexistir."
            )

        _ = testigos  # varios permitidos

    for med in catalogo.medidores:
        if med.descarga == "ION":
            if not med.ip or med.ip == "0":
                errores.append(f'Medidor "{med.nombre}": ION requiere IP válida.')
        elif med.descarga == "API":
            if not med.numero_serie:
                errores.append(
                    f'Medidor "{med.nombre}": API requiere Numero_Serie.'
                )

    return errores


def cargar_catalogo(directorio: Path | None = None) -> Catalogo:
    """Lee y valida el catálogo. Lanza CatalogError si hay problemas."""
    base = Path(directorio or DIRECTORIO_TARIFAS)
    tipos = _cargar_tipos(base)
    subs = _cargar_subestaciones(base)
    medidores = _cargar_medidores(base, subs, tipos)
    catalogo = Catalogo(subestaciones=subs, medidores=medidores, tipos=tipos)
    errores = _validar_reglas_negocio(catalogo)
    if errores:
        raise CatalogError(errores)
    return catalogo


@lru_cache(maxsize=1)
def obtener_catalogo() -> Catalogo:
    """Catálogo en caché (proceso)."""
    return cargar_catalogo()


def invalidar_cache_catalogo() -> None:
    obtener_catalogo.cache_clear()


def ruta_medidores_csv() -> Path:
    return DIRECTORIO_TARIFAS / ARCHIVO_MEDIDORES


def _escribir_filas_medidores(filas: list[dict[str, str]], fieldnames: list[str]) -> None:
    ruta = ruta_medidores_csv()
    with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(filas)


def marcar_medidores_validados(
    nombres: list[str],
    cuando: datetime | None = None,
) -> list[str]:
    """Escribe fecha Validado en Medidores.csv para los nombres indicados."""
    if not nombres:
        return []
    cuando = cuando or datetime.now()
    texto = cuando.strftime(FORMATO_VALIDADO)
    filas = _leer_csv(ruta_medidores_csv())
    if not filas:
        return []
    fieldnames = list(filas[0].keys())
    if "Validado" not in fieldnames:
        fieldnames.append("Validado")
    pendientes = {n.strip() for n in nombres if n.strip()}
    marcados: list[str] = []
    for fila in filas:
        nombre = (fila.get("Nombre") or "").strip()
        if nombre in pendientes:
            fila["Validado"] = texto
            marcados.append(nombre)
    _escribir_filas_medidores(filas, fieldnames)
    invalidar_cache_catalogo()
    try:
        from bess.config.subestaciones import invalidar_cache_subestaciones

        invalidar_cache_subestaciones()
    except Exception:
        pass
    return marcados


def marcar_medidor_validado(nombre: str, cuando: datetime | None = None) -> bool:
    return nombre in marcar_medidores_validados([nombre], cuando=cuando)


def marcar_grupo_generacion_validado(grupo: str, cuando: datetime | None = None) -> list[str]:
    """Marca Validado en todos los medidores tipo 4 del mismo Grupo_Generacion."""
    cat = cargar_catalogo()
    nombres = [m.nombre for m in cat.medidores if m.grupo_generacion == grupo]
    return marcar_medidores_validados(nombres, cuando=cuando)
