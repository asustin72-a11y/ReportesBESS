"""Escritura atómica de archivos de salida del pipeline.

Bug de producción que motivó este módulo: varios pasos del pipeline
(verify.py, clean.py/filter.py, combined.py y los agregados en
bess/data/aggregates/) reescriben un CSV existente completo -- las filas
anteriores a una ventana incremental se preservan crudas y se concatenan
con la ventana recién recalculada, todo escrito de nuevo sobre la ruta
final vía `open(ruta, 'w')` o `DataFrame.to_csv(ruta)`.

Si el proceso se interrumpe a mitad de esa escritura (crash, excepción no
prevista, `PermissionError` porque el archivo está abierto en Excel,
cierre forzado de la app), el archivo queda truncado en el punto exacto
donde se interrumpió -- y como el corte cae en un límite de fila válido,
no hay forma de detectarlo por inspección superficial. Esto pasó en
producción: `COMBINADO_POR_MINUTO_ION_Testigo_IUSA1_IUSA_1.csv` y los tres
`*_Filtrado.csv` de IUSA_ARAGON perdieron más de un día de datos ya
guardados cuando una corrida se interrumpió a medio escribir.

`ruta_temporal_atomica()` evita esta clase de bug: se escribe primero en
un archivo temporal en el mismo directorio (mismo filesystem, para que el
reemplazo final sea atómico) y solo si el bloque `with` completa sin
excepción se reemplaza la ruta final vía `os.replace()`. Si algo falla a
mitad de la escritura, el archivo original (si existía) queda intacto y
el temporal se descarta.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def ruta_temporal_atomica(ruta_destino: "os.PathLike[str] | str") -> Iterator[str]:
    """Context manager: entrega una ruta temporal para escribir; al salir
    del bloque `with` sin excepción, reemplaza `ruta_destino` con lo
    escrito (atómico vía `os.replace`, mismo filesystem). Si el bloque
    lanza una excepción, `ruta_destino` no se toca y el temporal se borra.

    Uso:
        with ruta_temporal_atomica(ruta_salida) as ruta_temp:
            df.to_csv(ruta_temp, index=False)

        with ruta_temporal_atomica(ruta_salida) as ruta_temp:
            with open(ruta_temp, 'w', encoding='utf-8-sig') as f:
                ...
    """
    ruta_destino = os.fspath(ruta_destino)
    directorio = os.path.dirname(ruta_destino) or "."
    os.makedirs(directorio, exist_ok=True)
    fd, ruta_temporal = tempfile.mkstemp(
        dir=directorio,
        prefix=f".tmp_{os.path.basename(ruta_destino)}_",
        suffix=".part",
    )
    os.close(fd)
    try:
        yield ruta_temporal
    except BaseException:
        _borrar_silencioso(ruta_temporal)
        raise
    else:
        os.replace(ruta_temporal, ruta_destino)


def _borrar_silencioso(ruta: str) -> None:
    try:
        os.remove(ruta)
    except OSError:
        pass
