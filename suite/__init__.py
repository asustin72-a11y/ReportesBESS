"""Suite IUSASOL — portal de módulos."""

from __future__ import annotations

from bess import __version__ as VERSION

NOMBRE_SUITE = "Suite IUSASOL"
SUBTITULO_SUITE = "Reporteadores de energía IUSASOL"

MODULO_BESS = "bess"
MODULO_GRANJA = "granja"
MODULO_DESCARGAS = "descargas"
MODULO_ANALISIS_PERFIL = "analisis_perfil"
MODULO_CONSULTAR_TARIFA = "consultar_tarifa"

MODULOS_VALIDOS = frozenset(
    {
        MODULO_BESS,
        MODULO_GRANJA,
        MODULO_DESCARGAS,
        MODULO_ANALISIS_PERFIL,
        MODULO_CONSULTAR_TARIFA,
    }
)
