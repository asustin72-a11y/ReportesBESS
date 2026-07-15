"""Pruebas de bess.core.atomic_io.ruta_temporal_atomica().

Bug de producción que motivó este módulo: varios escritores del pipeline
(verify.py, clean.py, combined.py, granja.py, bess_daily.py, accumulated.py,
daily.py, export_csv.py) reescribían el CSV de salida completo vía
`open(ruta, 'w')` o `DataFrame.to_csv(ruta)` directo sobre la ruta final.
Si el proceso se interrumpía a mitad de esa escritura, el archivo quedaba
truncado permanentemente -- pasó en producción con
COMBINADO_POR_MINUTO_ION_Testigo_IUSA1_IUSA_1.csv y con los tres
*_Filtrado.csv de IUSA_ARAGON, perdiendo más de un día de datos ya
guardados cada vez.

Estas pruebas cubren que `ruta_temporal_atomica()` solo reemplaza el
archivo final si la escritura completa sin excepción, y que una escritura
interrumpida deja el archivo original intacto.
"""

from __future__ import annotations

import os

import pytest

from bess.core.atomic_io import ruta_temporal_atomica


def test_escritura_exitosa_reemplaza_el_archivo(tmp_path):
    ruta = tmp_path / 'salida.csv'
    ruta.write_text('viejo contenido\n', encoding='utf-8')

    with ruta_temporal_atomica(str(ruta)) as ruta_temp:
        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write('nuevo contenido\n')

    assert ruta.read_text(encoding='utf-8') == 'nuevo contenido\n'


def test_escritura_interrumpida_no_toca_el_archivo_original(tmp_path):
    """Si algo lanza una excepción a mitad de la escritura (simula un
    crash, un PermissionError a medio proceso, etc.), el archivo original
    debe quedar exactamente como estaba -- no truncado, no a medias."""
    ruta = tmp_path / 'salida.csv'
    ruta.write_text('dato real que no se debe perder\n', encoding='utf-8')

    with pytest.raises(RuntimeError):
        with ruta_temporal_atomica(str(ruta)) as ruta_temp:
            with open(ruta_temp, 'w', encoding='utf-8') as f:
                f.write('contenido parcial que nunca deberia quedar\n')
                raise RuntimeError('interrupcion simulada a mitad de escritura')

    assert ruta.read_text(encoding='utf-8') == 'dato real que no se debe perder\n'


def test_no_deja_archivos_temporales_tras_exito(tmp_path):
    ruta = tmp_path / 'salida.csv'

    with ruta_temporal_atomica(str(ruta)) as ruta_temp:
        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write('contenido\n')

    restantes = list(tmp_path.iterdir())
    assert restantes == [ruta]


def test_no_deja_archivos_temporales_tras_fallo(tmp_path):
    ruta = tmp_path / 'salida.csv'

    with pytest.raises(RuntimeError):
        with ruta_temporal_atomica(str(ruta)) as ruta_temp:
            with open(ruta_temp, 'w', encoding='utf-8') as f:
                f.write('contenido\n')
            raise RuntimeError('boom')

    assert list(tmp_path.iterdir()) == []


def test_funciona_si_el_archivo_destino_no_existia(tmp_path):
    ruta = tmp_path / 'nuevo' / 'salida.csv'

    with ruta_temporal_atomica(str(ruta)) as ruta_temp:
        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write('primer contenido\n')

    assert ruta.read_text(encoding='utf-8') == 'primer contenido\n'


def test_funciona_con_pandas_to_csv(tmp_path):
    pd = pytest.importorskip('pandas')
    ruta = tmp_path / 'salida.csv'
    ruta.write_text('FECHA,VALOR\n01/01/2026,1\n', encoding='utf-8')

    df = pd.DataFrame({'FECHA': ['02/01/2026'], 'VALOR': [2]})
    with ruta_temporal_atomica(str(ruta)) as ruta_temp:
        df.to_csv(ruta_temp, index=False)

    contenido = ruta.read_text(encoding='utf-8')
    assert '02/01/2026,2' in contenido
    assert '01/01/2026' not in contenido


def test_temporal_se_crea_en_el_mismo_directorio(tmp_path):
    """El temporal debe crearse en el mismo directorio que el destino para
    que os.replace() sea atómico (mismo filesystem)."""
    ruta = tmp_path / 'salida.csv'
    directorio_visto = {}

    with ruta_temporal_atomica(str(ruta)) as ruta_temp:
        directorio_visto['temp'] = os.path.dirname(ruta_temp)
        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write('x\n')

    assert directorio_visto['temp'] == str(tmp_path)
