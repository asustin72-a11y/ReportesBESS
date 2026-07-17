"""El título y la leyenda deben ocupar bandas separadas."""

from bess.charts.layout import (
    LEYENDA_Y_EXTERNA,
    MARGEN_SUPERIOR_CON_LEYENDA,
    _titulo_y_leyenda_externos,
)
from bess.ui.emisiones_tab import _layout_grafica_emisiones


def test_layout_compartido_separa_titulo_y_leyenda():
    titulo, leyenda, margen = _titulo_y_leyenda_externos("Prueba")

    assert titulo["y"] == 1.0
    assert leyenda is not None
    assert leyenda["y"] == LEYENDA_Y_EXTERNA
    assert titulo["y"] - leyenda["y"] >= 0.08
    assert margen == MARGEN_SUPERIOR_CON_LEYENDA
    assert margen >= 125


def test_emisiones_usa_layout_compartido():
    layout = _layout_grafica_emisiones(
        title="Emisiones por periodo",
        yaxis_title="t CO₂",
    )

    assert layout["title"]["y"] == 1.0
    assert layout["legend"]["y"] == LEYENDA_Y_EXTERNA
    assert layout["margin"]["t"] == MARGEN_SUPERIOR_CON_LEYENDA

