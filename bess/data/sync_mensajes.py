"""Mensajes de sync orientados al usuario (sidebar Streamlit)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MensajeSyncUI:
    """Texto listo para st.error / st.warning / st.info."""

    titulo: str
    explicacion: str
    accion: str = ''
    tipo: str = 'error'  # error | warning | info


def _texto_combinado(stdout: str, stderr: str) -> str:
    return f'{stdout or ""}\n{stderr or ""}'


def _es_timeout_red(texto: str) -> bool:
    t = texto.casefold()
    return any(
        marca in t
        for marca in (
            'winerror 10060',
            'timed out',
            'timeout',
            'no se pudo conectar',
            'failed to establish a new connection',
            'name or service not known',
            'getaddrinfo failed',
            'network is unreachable',
            'connection refused',
        )
    )


def _es_fallo_api(texto: str) -> bool:
    t = texto.casefold()
    return any(
        marca in t
        for marca in (
            'error api',
            'api: error',
            'oauth2/token',
            'api.iusasol.mx',
            'sync detenido:',
        )
    )


def _es_fallo_granja(texto: str) -> bool:
    t = texto.casefold()
    return any(
        marca in t
        for marca in (
            'error granja',
            'granja: error',
            'reports/farm',
        )
    )


def clasificar_fallo_sync(stdout: str, stderr: str) -> MensajeSyncUI:
    """Traduce la salida técnica del sync a un mensaje claro."""
    bruto = _texto_combinado(stdout, stderr)

    if _es_fallo_granja(bruto) and _es_timeout_red(bruto):
        return MensajeSyncUI(
            titulo='Sin conexión a la API de Granja (IUSA 2).',
            explicacion=(
                'La red no respondió a tiempo al consultar la granja. '
                'Los medidores ION de planta no se ven afectados por este fallo.'
            ),
            accion='Reintente Sincronizar cuando haya acceso a internet / API IUSASOL.',
            tipo='error',
        )

    if _es_fallo_api(bruto) and _es_timeout_red(bruto):
        return MensajeSyncUI(
            titulo='Sin conexión a la API IUSASOL.',
            explicacion=(
                'No se pudo autenticar ni descargar perfiles por internet '
                '(timeout hacia api.iusasol.mx). '
                'La red de planta (ION Modbus) puede seguir operativa.'
            ),
            accion='Reintente Sincronizar cuando se restablezca el acceso a la API. '
            'Si necesita datos ION de planta, puede sincronizar solo ION en consola '
            'con --sin-api --sin-granja.',
            tipo='error',
        )

    if _es_fallo_api(bruto):
        return MensajeSyncUI(
            titulo='La sincronización por API IUSASOL falló.',
            explicacion='El servicio respondió con error o credenciales inválidas.',
            accion='Revise el detalle técnico abajo y las credenciales [iusasol] en secrets.',
            tipo='error',
        )

    if _es_fallo_granja(bruto):
        return MensajeSyncUI(
            titulo='La sincronización de Granja IUSA 2 falló.',
            explicacion='No se pudieron obtener perfiles de la granja.',
            accion='Revise el detalle técnico y el acceso a la API Farm.',
            tipo='error',
        )

    if _es_timeout_red(bruto):
        return MensajeSyncUI(
            titulo='Problema de red durante la sincronización.',
            explicacion='Algún origen no respondió a tiempo (timeout de conexión).',
            accion='Verifique conectividad y reintente. '
            'Diagnóstico: python scripts/diagnosticar_conectividad_sync.py',
            tipo='error',
        )

    return MensajeSyncUI(
        titulo='La sincronización falló.',
        explicacion='El proceso terminó con error. Consulte el detalle técnico.',
        accion='Si el problema continúa, ejecute '
        'python scripts/diagnosticar_conectividad_sync.py',
        tipo='error',
    )


def mensaje_ion_parcial(stdout: str) -> MensajeSyncUI | None:
    """Warning cuando el sync terminó OK pero ION no estaba disponible."""
    salida = stdout or ''
    ion1 = 'Medidor ION no disponible.' in salida or 'ION: no disponible' in salida
    ion2 = (
        'Medidor ION IUSA 2 no disponible.' in salida
        or 'ION IUSA 2: no disponible' in salida
        or 'ION_IUSA2: no disponible' in salida
    )
    # El resumen quiet usa etiqueta del catálogo; detectar "no disponible" en líneas ION
    if not ion1 and not ion2:
        for ln in salida.splitlines():
            low = ln.casefold()
            if 'no disponible' in low and ('ion' in low or 'iusa' in low):
                if 'iusa 2' in low or 'iusa2' in low or 'i usa 2' in low:
                    ion2 = True
                else:
                    ion1 = True

    if not ion1 and not ion2:
        return None

    if ion1 and ion2:
        titulo = 'Medidores ION de planta no disponibles.'
        expl = (
            'No hubo respuesta Modbus en IUSA 1 ni IUSA 2. '
            'Se conservaron los datos ya guardados en la base local.'
        )
    elif ion1:
        titulo = 'Medidor ION IUSA 1 no disponible.'
        expl = (
            'No hubo respuesta Modbus en la red de planta (IUSA 1). '
            'El resto del sync (API/export) pudo completarse; ION sigue sin validar.'
        )
    else:
        titulo = 'Medidor ION IUSA 2 no disponible.'
        expl = (
            'No hubo respuesta Modbus en IUSA 2. '
            'Se usarán los datos ION IUSA 2 ya guardados en la base local.'
        )

    return MensajeSyncUI(
        titulo=titulo,
        explicacion=expl,
        accion='Verifique cableado/VPN de planta o ejecute '
        'python scripts/diagnosticar_conectividad_sync.py',
        tipo='warning',
    )
