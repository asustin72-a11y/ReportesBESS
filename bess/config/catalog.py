"""Catálogo de subestaciones y medidores desde CSV en data/Tarifas/."""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from bess.config.esquema_tarifa import ESQUEMA_DEFAULT, normalizar_esquema_tarifa
from bess.config.paths import DIRECTORIO_TARIFAS

ARCHIVO_SUBESTACIONES = "Subestaciones.csv"
ARCHIVO_MEDIDORES = "Medidores.csv"
ARCHIVO_TIPO_MEDIDOR = "Tipo_Medidor.csv"

CAMPOS_TIPO_MEDIDOR = ("Tipo", "Descripcion", "Neteo", "Invertir", "Reactivos")
CAMPOS_SUBESTACIONES = ("Numero", "Nombre", "Generacion", "Esquema_Tarifa")
CAMPOS_MEDIDORES = (
    "Nombre",
    "Numero_Serie",
    "Subestacion",
    "Tipo_Medidor",
    "Descarga",
    "IP",
    "Puerto",
    "Grupo_Generacion",
    "Validado",
)

FORMATO_VALIDADO = "%d/%m/%Y %H:%M"
PUERTO_MODBUS_DEFAULT = 502
TIPO_FACTURACION = 1
TIPO_TESTIGO = 2
TIPO_BESS = 3
TIPO_GENERACION_MULTIPLE = 4
TIPO_GENERACION_INDIVIDUAL = 5
# Alias legacy (mismo número de tipo)
TIPO_GENERACION = TIPO_GENERACION_MULTIPLE
TIPO_COGENERACION = TIPO_GENERACION_INDIVIDUAL
DESCARGAS_VALIDAS = frozenset({"ION", "API"})
REACTIVOS_VALIDOS = frozenset({0, 1, 2})

# Subestaciones.csv columna Generacion
GENERACION_NINGUNA = 0
GENERACION_GRUPO = 1
GENERACION_INDIVIDUAL = 2
MODOS_GENERACION_VALIDOS = frozenset({GENERACION_NINGUNA, GENERACION_GRUPO, GENERACION_INDIVIDUAL})


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
    generacion: int
    esquema_tarifa: str = ESQUEMA_DEFAULT

    @property
    def tiene_generacion(self) -> bool:
        return self.generacion in (GENERACION_GRUPO, GENERACION_INDIVIDUAL)

    @property
    def generacion_grupo(self) -> bool:
        return self.generacion == GENERACION_GRUPO

    @property
    def generacion_individual(self) -> bool:
        return self.generacion == GENERACION_INDIVIDUAL


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
    def es_generacion_multiple(self) -> bool:
        return self.tipo_medidor == TIPO_GENERACION_MULTIPLE

    @property
    def es_generacion_individual(self) -> bool:
        return self.tipo_medidor == TIPO_GENERACION_INDIVIDUAL

    @property
    def es_generacion(self) -> bool:
        return self.es_generacion_multiple

    @property
    def es_cogeneracion(self) -> bool:
        return self.es_generacion_individual

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


def _modo_generacion_csv(valor: str, *, fila: str) -> int:
    """Generacion en Subestaciones.csv: 0=ninguna, 1=grupo (tipo 4), 2=individual (tipo 5)."""
    texto = str(valor or "").strip()
    if not texto:
        return GENERACION_NINGUNA
    try:
        modo = int(texto)
    except ValueError as exc:
        raise CatalogError(
            [f'Subestación "{fila}": Generacion debe ser 0, 1 o 2 (recibido: {texto!r}).']
        ) from exc
    if modo not in MODOS_GENERACION_VALIDOS:
        raise CatalogError(
            [f'Subestación "{fila}": Generacion debe ser 0, 1 o 2 (recibido: {modo}).']
        )
    return modo


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


def _cargar_tipos(
    directorio: Path | None = None,
    *,
    filas: list[dict[str, str]] | None = None,
) -> tuple[ReglasTipoMedidor, ...]:
    if filas is None:
        base = Path(directorio or DIRECTORIO_TARIFAS)
        filas = _leer_csv(base / ARCHIVO_TIPO_MEDIDOR)
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


def _cargar_subestaciones(
    directorio: Path | None = None,
    *,
    filas: list[dict[str, str]] | None = None,
) -> tuple[SubestacionCatalogo, ...]:
    if filas is None:
        base = Path(directorio or DIRECTORIO_TARIFAS)
        filas = _leer_csv(base / ARCHIVO_SUBESTACIONES)
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
                generacion=_modo_generacion_csv(fila.get("Generacion", ""), fila=nombre),
                esquema_tarifa=normalizar_esquema_tarifa(fila.get("Esquema_Tarifa", "")),
            )
        )
    return tuple(subs)


def _cargar_medidores(
    subs: tuple[SubestacionCatalogo, ...],
    tipos: tuple[ReglasTipoMedidor, ...],
    directorio: Path | None = None,
    *,
    filas: list[dict[str, str]] | None = None,
) -> tuple[MedidorCatalogo, ...]:
    if filas is None:
        base = Path(directorio or DIRECTORIO_TARIFAS)
        filas = _leer_csv(base / ARCHIVO_MEDIDORES)
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
        generacion_multiple = [m for m in meds if m.tipo_medidor == TIPO_GENERACION_MULTIPLE]
        generacion_individual = [m for m in meds if m.tipo_medidor == TIPO_GENERACION_INDIVIDUAL]

        if len(facturacion) != 1:
            errores.append(
                f'Subestación "{sub.nombre}": debe tener exactamente 1 medidor tipo 1 '
                f"(Neteo/facturación); tiene {len(facturacion)}."
            )
        if not bess:
            errores.append(
                f'Subestación "{sub.nombre}": requiere al menos 1 medidor tipo 3 (BESS).'
            )
        if generacion_multiple and sub.generacion == GENERACION_NINGUNA:
            errores.append(
                f'Subestación "{sub.nombre}": hay medidores tipo 4 (GeneracionMultiple) '
                f"pero Generacion=0."
            )
        if sub.generacion == GENERACION_GRUPO:
            if not generacion_multiple:
                errores.append(
                    f'Subestación "{sub.nombre}": Generacion=1 (grupo) requiere medidores '
                    f"tipo 4 (GeneracionMultiple)."
                )
            sin_grupo = [m.nombre for m in generacion_multiple if not m.grupo_generacion]
            if sin_grupo:
                errores.append(
                    f'Subestación "{sub.nombre}": medidores GeneracionMultiple sin '
                    f"Grupo_Generacion: {', '.join(sin_grupo)}."
                )
            if generacion_individual:
                errores.append(
                    f'Subestación "{sub.nombre}": Generacion=1 (grupo) no admite medidor '
                    f"tipo 5 (GeneracionIndividual)."
                )
        if sub.generacion == GENERACION_INDIVIDUAL:
            if not generacion_individual:
                errores.append(
                    f'Subestación "{sub.nombre}": Generacion=2 (individual) requiere 1 medidor '
                    f"tipo 5 (GeneracionIndividual)."
                )
            if len(generacion_individual) > 1:
                errores.append(
                    f'Subestación "{sub.nombre}": Generacion=2 permite solo 1 medidor '
                    f"GeneracionIndividual."
                )
            if generacion_multiple:
                errores.append(
                    f'Subestación "{sub.nombre}": Generacion=2 (individual) no admite medidores '
                    f"GeneracionMultiple."
                )
        if sub.generacion == GENERACION_NINGUNA and generacion_individual:
            errores.append(
                f'Subestación "{sub.nombre}": medidor GeneracionIndividual con Generacion=0.'
            )
        if len(generacion_individual) > 1 and sub.generacion != GENERACION_INDIVIDUAL:
            errores.append(
                f'Subestación "{sub.nombre}": solo se permite 1 medidor GeneracionIndividual.'
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
    """Lee y valida el catálogo desde SQLite. Lanza CatalogError si hay problemas."""
    from bess.data.catalog_db import ensure_catalog_listo, leer_filas_catalogo_bd

    ensure_catalog_listo(directorio)
    filas_tipos, filas_subs, filas_meds = leer_filas_catalogo_bd()
    tipos = _cargar_tipos(filas=filas_tipos)
    subs = _cargar_subestaciones(filas=filas_subs)
    medidores = _cargar_medidores(subs, tipos, filas=filas_meds)
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


def catalogo_desde_filas(
    filas_tipos: list[dict[str, str]],
    filas_subestaciones: list[dict[str, str]],
    filas_medidores: list[dict[str, str]],
    *,
    validar_negocio: bool = True,
) -> Catalogo:
    """Construye y valida un catálogo a partir de filas CSV (sin leer disco)."""
    tipos = _cargar_tipos(filas=filas_tipos)
    subs = _cargar_subestaciones(filas=filas_subestaciones)
    medidores = _cargar_medidores(subs, tipos, filas=filas_medidores)
    catalogo = Catalogo(subestaciones=subs, medidores=medidores, tipos=tipos)
    if validar_negocio:
        errores = _validar_reglas_negocio(catalogo)
        if errores:
            raise CatalogError(errores)
    return catalogo


def validar_filas_catalogo(
    filas_tipos: list[dict[str, str]],
    filas_subestaciones: list[dict[str, str]],
    filas_medidores: list[dict[str, str]],
) -> list[str]:
    """Devuelve lista de errores de validación (vacía si el catálogo es válido)."""
    try:
        catalogo_desde_filas(filas_tipos, filas_subestaciones, filas_medidores)
        return []
    except CatalogError as exc:
        return list(exc.errores)


def leer_filas_catalogo(directorio: Path | None = None) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Lee las tres tablas del catálogo desde SQLite (sin validar reglas de negocio)."""
    from bess.data.catalog_db import ensure_catalog_listo, leer_filas_catalogo_bd

    ensure_catalog_listo(directorio)
    return leer_filas_catalogo_bd()


def _respaldar_csv(ruta: Path) -> None:
    if ruta.is_file():
        shutil.copy2(ruta, ruta.with_suffix(".csv.bak"))


def _escribir_csv(ruta: Path, fieldnames: tuple[str, ...], filas: list[dict[str, str]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    _respaldar_csv(ruta)
    with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for fila in filas:
            writer.writerow({campo: fila.get(campo, "") for campo in fieldnames})


def _invalidar_caches_catalogo() -> None:
    invalidar_cache_catalogo()
    try:
        from bess.config.subestaciones import invalidar_cache_subestaciones

        invalidar_cache_subestaciones()
    except Exception:
        pass


def guardar_filas_catalogo(
    filas_tipos: list[dict[str, str]],
    filas_subestaciones: list[dict[str, str]],
    filas_medidores: list[dict[str, str]],
    directorio: Path | None = None,
) -> None:
    """Valida y persiste el catálogo en SQLite."""
    from bess.data.catalog_db import guardar_filas_catalogo_bd

    _ = directorio  # legacy; el catálogo vive en BD
    catalogo_desde_filas(filas_tipos, filas_subestaciones, filas_medidores)
    guardar_filas_catalogo_bd(filas_tipos, filas_subestaciones, filas_medidores)
    _invalidar_caches_catalogo()
    from bess.data.ingest.ion.db import _registrar_catalogo_medidores, conectar_bd

    with conectar_bd() as conn:
        _registrar_catalogo_medidores(conn)
        conn.commit()


def ruta_subestaciones_csv() -> Path:
    return DIRECTORIO_TARIFAS / ARCHIVO_SUBESTACIONES


def ruta_tipos_medidor_csv() -> Path:
    return DIRECTORIO_TARIFAS / ARCHIVO_TIPO_MEDIDOR


def _escribir_filas_medidores(filas: list[dict[str, str]], fieldnames: list[str]) -> None:
    _escribir_csv(ruta_medidores_csv(), tuple(fieldnames), filas)
    _invalidar_caches_catalogo()


def marcar_medidores_validados(
    nombres: list[str],
    cuando: datetime | None = None,
) -> list[str]:
    """Escribe fecha Validado en el catálogo SQLite para los nombres indicados."""
    from bess.data.catalog_db import marcar_medidores_validados_bd

    marcados = marcar_medidores_validados_bd(nombres, cuando=cuando)
    if marcados:
        _invalidar_caches_catalogo()
    return marcados


def marcar_medidor_validado(nombre: str, cuando: datetime | None = None) -> bool:
    return nombre in marcar_medidores_validados([nombre], cuando=cuando)


def marcar_grupo_generacion_validado(grupo: str, cuando: datetime | None = None) -> list[str]:
    """Marca Validado en todos los medidores GeneracionMultiple del mismo Grupo_Generacion."""
    cat = cargar_catalogo()
    nombres = [m.nombre for m in cat.medidores if m.grupo_generacion == grupo]
    return marcar_medidores_validados(nombres, cuando=cuando)
