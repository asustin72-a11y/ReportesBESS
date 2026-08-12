"""
Genera docs/MANUAL_SUITE.pdf a partir de docs/MANUAL_SUITE.md.

Uso:
  python docs/generar_manual_suite_pdf.py
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, Spacer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bess import __version__ as VERSION
from docs.pdf_shared import (
    CONTENT_W,
    build_pdf,
    cover_page,
    p,
    styles,
    table,
    toc_box,
)

DOCS = ROOT / "docs"
MD_IN = DOCS / "MANUAL_SUITE.md"
PDF_OUT = DOCS / "MANUAL_SUITE.pdf"
LOGO = ROOT / "data" / "Logo IUSASOL.png"
if not LOGO.exists():
    LOGO = ROOT / "data" / "LogoIUSASOL.jpeg"


def _inline(text: str) -> str:
    """Markdown inline → ReportLab XML-ish markup."""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r"<font face='Courier' size='9'>\1</font>", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def _is_table_sep(line: str) -> bool:
    s = line.strip().strip("|")
    if not s:
        return False
    return bool(re.fullmatch(r"[\s\-:|]+", line.strip()))


def _split_row(line: str) -> list[str]:
    raw = line.strip()
    if raw.startswith("|"):
        raw = raw[1:]
    if raw.endswith("|"):
        raw = raw[:-1]
    return [c.strip() for c in raw.split("|")]


def _parse_md(md: str) -> tuple[list, list[str]]:
    """Devuelve (flowables del cuerpo, entradas TOC de ##)."""
    lines = md.splitlines()
    body: list = []
    toc: list[str] = []
    i = 0
    # Saltar portada markdown (# título + meta) hasta el primer ##
    while i < len(lines):
        if lines[i].startswith("## "):
            break
        i += 1

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            i += 1
            continue

        if stripped.startswith("## "):
            title = stripped[3:].strip()
            toc.append(title)
            body.append(Spacer(1, 8))
            body.append(p(_inline(title), "h1"))
            i += 1
            continue

        if stripped.startswith("### "):
            body.append(p(_inline(stripped[4:].strip()), "h2"))
            i += 1
            continue

        if stripped.startswith("#### "):
            body.append(p(f"<b>{_inline(stripped[5:].strip())}</b>", "h2"))
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            rows: list[list[str]] = [_split_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not _is_table_sep(lines[i]):
                    rows.append(_split_row(lines[i]))
                i += 1
            # Anchos proporcionales
            ncols = max(len(r) for r in rows)
            for r in rows:
                while len(r) < ncols:
                    r.append("")
            rendered = [[_inline(c) for c in row] for row in rows]
            col_w = [CONTENT_W / ncols] * ncols
            if ncols == 2:
                col_w = [CONTENT_W * 0.32, CONTENT_W * 0.68]
            elif ncols == 3:
                col_w = [CONTENT_W * 0.22, CONTENT_W * 0.28, CONTENT_W * 0.50]
            body.append(table(rendered, col_widths=col_w))
            body.append(Spacer(1, 8))
            continue

        # Listas numeradas o con viñeta
        if re.match(r"^(\d+\.\s+|[-*]\s+)", stripped):
            items: list[ListItem] = []
            ordered = bool(re.match(r"^\d+\.\s+", stripped))
            while i < len(lines):
                cur = lines[i].strip()
                m = re.match(r"^(\d+\.\s+|[-*]\s+)(.*)$", cur)
                if not m:
                    break
                items.append(
                    ListItem(
                        Paragraph(_inline(m.group(2)), styles()["body"]),
                        leftIndent=12,
                        bulletColor="#2d3748",
                    )
                )
                i += 1
            body.append(
                ListFlowable(
                    items,
                    bulletType="1" if ordered else "bullet",
                    start="1",
                    leftIndent=18,
                    bulletFontSize=9,
                    spaceBefore=2,
                    spaceAfter=6,
                )
            )
            continue

        # Párrafo (posiblemente multilínea simple)
        para_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt.startswith("#")
                or nxt.startswith("|")
                or nxt == "---"
                or re.match(r"^(\d+\.\s+|[-*]\s+)", nxt)
            ):
                break
            para_lines.append(nxt)
            i += 1
        body.append(p(_inline(" ".join(para_lines)), "body"))

    return body, toc


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
            "Manual de usuario — Suite IUSASOL",
            "BESS · Granja Solar · Descargas API · Análisis de Perfil · Consultar Tarifa",
            VERSION,
        )
    )
    story.append(PageBreak())
    story.extend(toc_box(toc))
    story.extend(body)
    story.append(Spacer(1, 16))
    story.append(p(f"Suite IUSASOL v{VERSION} — Manual de usuario", "footer"))

    build_pdf(story, PDF_OUT, "Manual de usuario — Suite IUSASOL")
    print(f"PDF generado: {PDF_OUT} ({PDF_OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
