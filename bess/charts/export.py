"""Exportación de figuras Plotly a imagen."""

from __future__ import annotations

import plotly.io as pio

DEFAULT_PNG_SCALE = 2


def figura_a_png_bytes(fig, scale: float = DEFAULT_PNG_SCALE) -> bytes:
    return pio.to_image(fig, format='png', scale=scale)
