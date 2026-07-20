"""Pruebas del cargador del reporteador Consultas Usuarios."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from consultas_usuarios.data_loader import agrupar_por_contrato, filtrar_reporte, resumen


def test_resumen_y_filtros(tmp_path: Path) -> None:
    df = pd.DataFrame([
        {'Contrato': 'BESS Norte', 'Serial': 'CS3878', 'Ultimo_perfil': '2026-07-17 22:20:00', 'Nota': ''},
        {'Contrato': 'API CABOTAJE', 'Serial': 'CYM630', 'Ultimo_perfil': '', 'Nota': 'sin energía (ceros) en 365d'},
        {'Contrato': 'IUSA Aragon', 'Serial': 'CYM773', 'Ultimo_perfil': '2026-07-17 22:20:00', 'Nota': ''},
        {'Contrato': 'IUSA Aragon', 'Serial': 'CS1980', 'Ultimo_perfil': '2026-07-17 22:15:00', 'Nota': ''},
    ])
    stats = resumen(df)
    assert stats['filas'] == 4
    assert stats['contratos'] == 3
    assert stats['con_perfil'] == 3
    assert stats['sin_energia'] == 1

    solo = filtrar_reporte(df, texto='aragon', estado='todos')
    assert len(solo) == 2

    sin_e = filtrar_reporte(df, estado='sin_energia')
    assert list(sin_e['Serial']) == ['CYM630']

    grupos = agrupar_por_contrato(df)
    por_nombre = {g['contrato']: g for g in grupos}
    assert por_nombre['IUSA Aragon']['n_medidores'] == 2
    assert list(por_nombre['IUSA Aragon']['medidores']['Serial']) == ['CS1980', 'CYM773']
    assert por_nombre['BESS Norte']['n_medidores'] == 1
