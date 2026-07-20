"""Estilos del reporteador Consultas Usuarios (marca IUSASOL)."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from consultas_usuarios.paths import resolver_logo

# Paleta derivada del anillo del logo IUSASOL (cyan / verde / naranja)
# sobre atmósfera clara — no dark mode.
CSS_VARS = """
:root {
  --cu-ink: #1b2430;
  --cu-muted: #5c6b7a;
  --cu-paper: #f3f6f8;
  --cu-line: rgba(27, 36, 48, 0.12);
  --cu-cyan: #00aeef;
  --cu-green: #39b54a;
  --cu-orange: #f7941e;
  --cu-surface: rgba(255, 255, 255, 0.72);
  --cu-shadow: 0 18px 50px rgba(27, 36, 48, 0.08);
}
"""


def _logo_data_uri() -> str | None:
    ruta = resolver_logo()
    if ruta is None:
        return None
    mime = 'image/png' if ruta.suffix.lower() == '.png' else 'image/jpeg'
    b64 = base64.b64encode(ruta.read_bytes()).decode('ascii')
    return f'data:{mime};base64,{b64}'


def aplicar_estilos() -> None:
    logo = _logo_data_uri()
    logo_rule = (
        f'.cu-brand-mark {{ background-image: url("{logo}"); }}'
        if logo
        else '.cu-brand-mark { background: linear-gradient(135deg, var(--cu-cyan), var(--cu-green), var(--cu-orange)); }'
    )
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap');

{CSS_VARS}

html, body, [class*="css"] {{
  font-family: 'Figtree', sans-serif;
}}

.stApp {{
  background:
    radial-gradient(1200px 600px at 8% -10%, rgba(0, 174, 239, 0.16), transparent 55%),
    radial-gradient(900px 500px at 92% 0%, rgba(57, 181, 74, 0.14), transparent 50%),
    radial-gradient(800px 480px at 70% 100%, rgba(247, 148, 30, 0.10), transparent 55%),
    linear-gradient(180deg, #eef3f6 0%, var(--cu-paper) 42%, #e8eef2 100%);
  color: var(--cu-ink);
}}

[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"] {{ display: none; }}
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}

.block-container {{
  padding-top: 1.25rem;
  padding-bottom: 3rem;
  max-width: 1120px;
}}

.cu-hero {{
  min-height: calc(100vh - 2.5rem);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1.1rem;
  padding: 1.5rem 0 2.5rem;
  animation: cu-rise 0.9s ease-out both;
}}

.cu-brand-row {{
  display: flex;
  align-items: center;
  gap: 1rem;
}}

.cu-brand-mark {{
  width: 72px;
  height: 72px;
  border-radius: 18px;
  background-size: cover;
  background-position: center;
  box-shadow: var(--cu-shadow);
  flex: 0 0 auto;
}}

.cu-brand-name {{
  font-family: 'Syne', sans-serif;
  font-weight: 800;
  font-size: clamp(2.6rem, 6vw, 4.4rem);
  letter-spacing: -0.04em;
  line-height: 0.95;
  margin: 0;
  color: var(--cu-ink);
}}

.cu-product {{
  font-family: 'Syne', sans-serif;
  font-weight: 700;
  font-size: clamp(1.35rem, 3vw, 1.85rem);
  letter-spacing: -0.02em;
  margin: 0.15rem 0 0;
  color: var(--cu-ink);
}}

.cu-product span {{
  background: linear-gradient(90deg, var(--cu-cyan), var(--cu-green) 55%, var(--cu-orange));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}}

.cu-lead {{
  max-width: 34rem;
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.55;
  color: var(--cu-muted);
}}

.cu-cta {{
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  margin-top: 0.35rem;
  padding: 0.85rem 1.25rem;
  border-radius: 999px;
  background: var(--cu-ink);
  color: #fff !important;
  text-decoration: none !important;
  font-weight: 600;
  font-size: 0.95rem;
  width: fit-content;
  transition: transform 0.25s ease, background 0.25s ease;
  animation: cu-pulse 3.2s ease-in-out infinite;
}}

.cu-cta:hover {{
  transform: translateY(-2px);
  background: #111821;
}}

.cu-ring {{
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background:
    conic-gradient(var(--cu-cyan), var(--cu-green), var(--cu-orange), var(--cu-cyan));
}}

.cu-section {{
  margin-top: 0.5rem;
  padding: 1.35rem 1.35rem 1.1rem;
  border: 1px solid var(--cu-line);
  border-radius: 22px;
  background: var(--cu-surface);
  backdrop-filter: blur(10px);
  box-shadow: var(--cu-shadow);
  animation: cu-fade 0.7s ease both;
}}

.cu-section h2 {{
  font-family: 'Syne', sans-serif;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 0.35rem;
}}

.cu-section p.cu-sub {{
  margin: 0 0 1rem;
  color: var(--cu-muted);
  font-size: 0.98rem;
}}

.cu-kpis {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}}

.cu-kpi {{
  padding: 0.85rem 0.95rem;
  border-radius: 16px;
  border: 1px solid var(--cu-line);
  background: rgba(255,255,255,0.85);
}}

.cu-kpi .n {{
  font-family: 'Syne', sans-serif;
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
}}

.cu-kpi .l {{
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: var(--cu-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}}

.cu-kpi:nth-child(1) .n {{ color: var(--cu-cyan); }}
.cu-kpi:nth-child(2) .n {{ color: var(--cu-green); }}
.cu-kpi:nth-child(3) .n {{ color: var(--cu-orange); }}

@media (max-width: 800px) {{
  .cu-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .cu-brand-name {{ font-size: 2.4rem; }}
  .cu-hero {{ min-height: auto; padding-top: 2rem; }}
}}

@keyframes cu-rise {{
  from {{ opacity: 0; transform: translateY(18px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

@keyframes cu-fade {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

@keyframes cu-pulse {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(0, 174, 239, 0.0); }}
  50% {{ box-shadow: 0 0 0 8px rgba(0, 174, 239, 0.10); }}
}}

{logo_rule}
</style>
        """,
        unsafe_allow_html=True,
    )


def html_hero() -> str:
    return """
<div class="cu-hero">
  <div class="cu-brand-row">
    <div class="cu-brand-mark" role="img" aria-label="IUSASOL"></div>
    <div>
      <p class="cu-brand-name">IUSASOL</p>
      <p class="cu-product">Consultas <span>Usuarios</span></p>
    </div>
  </div>
  <p class="cu-lead">
    Reporteador de contratos, medidores y último perfil registrado en el
    sistema de monitoreo de energía.
  </p>
  <a class="cu-cta" href="#reporte">
    <span class="cu-ring"></span>
    Ver reporte
  </a>
</div>
"""


def html_kpis(stats: dict[str, int]) -> str:
    return f"""
<div class="cu-kpis">
  <div class="cu-kpi"><div class="n">{stats['filas']}</div><div class="l">Medidores</div></div>
  <div class="cu-kpi"><div class="n">{stats['contratos']}</div><div class="l">Contratos</div></div>
  <div class="cu-kpi"><div class="n">{stats['con_perfil']}</div><div class="l">Con perfil</div></div>
  <div class="cu-kpi"><div class="n">{stats['sin_energia']}</div><div class="l">Sin energía</div></div>
</div>
"""
