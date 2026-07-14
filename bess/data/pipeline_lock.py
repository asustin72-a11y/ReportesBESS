"""Lock de archivo compartido para el pipeline de datos.

Varias vías pueden disparar el pipeline (sincronizar/verificar/filtrar/
generar reportes) sobre los mismos CSV en data/ArchivosProcesados y
data/ArchivosReporte:

- El cron automático (scripts/cron_sincronizar.sh, cada 15 min) llama a
  scripts/sincronizar_perfiles.py --procesar como subproceso.
- El botón "Procesar todo" de la UI llama al mismo script como subproceso.
- Los botones "Verificar" / "Filtrar" del modo paso a paso llaman
  bess.data.pipeline.verify.verificar_datos_fuente() /
  bess.data.pipeline.filter.filtrar_datos() directamente en el proceso
  de Streamlit (sin subproceso).
- El botón "Generar reportes" llama scripts/run_reporte_bess.py como
  subproceso.

El flock de cron_sincronizar.sh solo protege contra que el cron se
solape consigo mismo; no sabe nada de la UI. Este módulo agrega un lock
de archivo (funciona entre procesos y threads, cualquiera sea el
disparador) alrededor de cada una de las tres funciones que
efectivamente escriben esos CSV, para que nunca corran dos al mismo
tiempo sin importar quién las llamó.
"""

from __future__ import annotations

from filelock import FileLock, Timeout

from bess.config.paths import DIRECTORIO_BASE

RUTA_LOCK = DIRECTORIO_BASE / ".pipeline.lock"

# Verificar/filtrar suelen tardar segundos a pocos minutos; generar
# reportes puede tardar más (ver GUIA_ADMINISTRADOR.md, hasta ~15 min
# en subestaciones con historiales largos). 3 minutos de espera es
# suficiente para no chocar con una ejecución normal sin bloquear la
# UI indefinidamente si algo quedó colgado.
TIMEOUT_LOCK_SEGUNDOS = 180

MENSAJE_PIPELINE_OCUPADO = (
    "Otra ejecución del pipeline (sincronizar, verificar, filtrar o "
    "generar reportes) sigue en curso. Intente de nuevo en unos minutos."
)


def lock_pipeline(timeout: float = TIMEOUT_LOCK_SEGUNDOS) -> FileLock:
    """Crea (sin adquirir todavía) el lock exclusivo del pipeline.

    Uso típico, envolviendo una función que hoy retorna (bool, str):

        def mi_etapa():
            lock = lock_pipeline()
            try:
                lock.acquire()
            except Timeout:
                return False, MENSAJE_PIPELINE_OCUPADO
            try:
                return _mi_etapa_impl()
            finally:
                lock.release()
    """
    RUTA_LOCK.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(RUTA_LOCK), timeout=timeout)
