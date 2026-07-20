"""Aplicación Streamlit — Consultas Usuarios (IUSASOL)."""

from __future__ import annotations

import streamlit as st

from consultas_usuarios.data_loader import (
    agrupar_por_contrato,
    cargar_contratos_vacios,
    cargar_reporte_principal,
    filtrar_reporte,
    resumen,
)
from consultas_usuarios.paths import (
    DATA_DIR,
    PROJECT_ROOT,
    REPORTE_PRINCIPAL,
    resolver_logo,
)
from consultas_usuarios.ui.styles import aplicar_estilos, html_hero, html_kpis


def _cfg_pagina() -> None:
    logo = resolver_logo()
    st.set_page_config(
        page_title='IUSASOL · Consultas Usuarios',
        page_icon=str(logo) if logo else None,
        layout='wide',
        initial_sidebar_state='collapsed',
    )


def _render_contratos(grupos: list[dict], *, expandir_todos: bool) -> None:
    if not grupos:
        st.info('Ningún contrato coincide con el filtro.')
        return

    for g in grupos:
        titulo = (
            f"{g['contrato']}  ·  {g['n_medidores']} medidor"
            f"{'es' if g['n_medidores'] != 1 else ''}"
            f"  ·  {g['con_perfil']} con perfil"
        )
        with st.expander(titulo, expanded=expandir_todos or g['n_medidores'] <= 3):
            st.dataframe(
                g['medidores'],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Serial': st.column_config.TextColumn('Serial', width='large'),
                    'Ultimo_perfil': st.column_config.TextColumn(
                        'Último perfil', width='medium',
                    ),
                    'Nota': st.column_config.TextColumn('Nota', width='medium'),
                },
            )


def main() -> None:
    _cfg_pagina()
    aplicar_estilos()

    st.markdown(html_hero(), unsafe_allow_html=True)

    st.markdown('<div id="reporte"></div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="cu-section">
  <h2>Reporte de contratos y medidores</h2>
  <p class="cu-sub">
    Cada contrato lista los medidores que le pertenecen, con la última fecha
    de perfil con energía. Módulo independiente de BESS.
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )

    df = cargar_reporte_principal()
    vacios = cargar_contratos_vacios()
    stats = resumen(df)
    st.markdown(html_kpis(stats), unsafe_allow_html=True)

    if df.empty:
        st.warning(
            f'No hay CSV en `{REPORTE_PRINCIPAL}`. '
            'Genérelo con `python scripts/reporte_contratos_medidores_iusasol.py '
            '--salida data/consultas_usuarios/reporte_principal.csv`.'
        )
        return

    c1, c2, c3, c4 = st.columns([2.0, 1.2, 1.0, 1.0])
    with c1:
        texto = st.text_input(
            'Buscar',
            placeholder='Contrato o serial…',
            label_visibility='collapsed',
        )
    with c2:
        estado = st.selectbox(
            'Estado',
            options=[
                ('todos', 'Todos'),
                ('con_perfil', 'Con último perfil'),
                ('sin_energia', 'Sin energía (ceros)'),
            ],
            format_func=lambda x: x[1],
            label_visibility='collapsed',
        )[0]
    with c3:
        ver_vacios = st.toggle('Contratos vacíos', value=False)
    with c4:
        expandir = st.toggle('Expandir todos', value=False)

    if ver_vacios:
        st.caption(f'{len(vacios)} contratos sin medidores en la API.')
        st.dataframe(vacios, use_container_width=True, hide_index=True, height=420)
    else:
        filtrado = filtrar_reporte(df, texto=texto, estado=estado)
        grupos = agrupar_por_contrato(filtrado)
        n_med = sum(g['n_medidores'] for g in grupos)
        st.caption(f'{len(grupos)} contratos · {n_med} medidores')
        _render_contratos(grupos, expandir_todos=expandir)

        csv_bytes = filtrado.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            'Descargar CSV (plano)',
            data=csv_bytes,
            file_name='consultas_usuarios_reporte.csv',
            mime='text/csv',
        )

    try:
        fuente = DATA_DIR.relative_to(PROJECT_ROOT)
    except ValueError:
        fuente = DATA_DIR
    st.caption(f'Fuente: `{fuente}`')


if __name__ == '__main__':
    main()
