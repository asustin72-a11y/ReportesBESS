"""
Genera docs/MANUAL_CATALOGO.pdf a partir de docs/MANUAL_CATALOGO.md.

Uso:
  python docs/generar_manual_catalogo_pdf.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.platypus import PageBreak, Spacer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bess import __version__ as VERSION
from docs.generar_manual_suite_pdf import _parse_md
from docs.pdf_shared import build_pdf, cover_page, p, toc_box

DOCS = ROOT / "docs"
MD_IN = DOCS / "MANUAL_CATALOGO.md"
PDF_OUT = DOCS / "MANUAL_CATALOGO.pdf"
LOGO = ROOT / "data" / "Logo IUSASOL.png"
if not LOGO.exists():
    LOGO = ROOT / "data" / "LogoIUSASOL.jpeg"


def main() -> int:
    if not MD_IN.exists():
        print(f"No existe {MD_IN}", file=sys.stderr)
        return 1

    md = MD_IN.read_text(encoding="utf-8")
    body, toc = _parse_md(md)

    story: list = []
    story.extend(
        cover_page(
            LOGO,
            "Manual de catálogo — Alta de medidores y subestaciones",
            "Reglas de negocio y procedimiento (superadministrador)",
            VERSION,
        )
    )
    story.append(PageBreak())
    story.extend(toc_box(toc))
    story.extend(body)
    story.append(Spacer(1, 16))
    story.append(p(f"Suite IUSASOL v{VERSION} — Manual de catálogo", "footer"))

    build_pdf(story, PDF_OUT, "Manual de catálogo — Alta medidores / subestaciones")
    print(f"PDF generado: {PDF_OUT} ({PDF_OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
