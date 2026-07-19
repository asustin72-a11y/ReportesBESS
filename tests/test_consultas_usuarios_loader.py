"""Pruebas del cargador del reporteador Consultas Usuarios."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from consultas_usuarios.data_loader import filtrar_reporte, resumen


def test_resumen_y_filtros(tmp_path: Path) -> None:
    df = pd.DataFrame([
        {'Contrato': 'BESS Norte', 'Serial': 'CS3878', 'Ultimo_perfil': '2026-07-17 22:20:00', 'Nota': ''},
        {'Contrato': 'API CABOTAJE', 'Serial': 'CYM630', 'Ultimo_perfil': '', 'Nota': 'sin energía (ceros) en 365d'},
        {'Contrato': 'IUSA Aragon', 'Serial': 'CYM773', 'Ultimo_perfil': '2026-07-17 22:20:00', 'Nota': ''},
    ])
    stats = resumen(df)
    assert stats['filas'] == 3
    assert stats['contratos'] == 3
    assert stats['con_perfil'] == 2
    assert stats['sin_energia'] == 1

    solo = filtrar_reporte(df, texto='aragon', estado='todos')
    assert len(solo) == 1 and solo.iloc[0]['Serial'] == 'CYM773'

    sin_e = filtrar_reporte(df, estado='sin_energia')
    assert list(sin_e['Serial']) == ['CYM630']
