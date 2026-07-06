"""Administración del catálogo: subestaciones, tipos y medidores (superadmin)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bess.config.catalog import DESCARGAS_VALIDAS, GENERACION_GRUPO, GENERACION_INDIVIDUAL, GENERACION_NINGUNA
from bess.ui.catalog_admin import service
from bess.ui.styles import aplicar_estilos


def _requiere_superadmin() -> None:
    from bess.config.users import rol_es_superadmin

    if not rol_es_superadmin(st.session_state.get("rol")):
        st.error("Solo superadministradores pueden administrar el catálogo.")
        st.stop()


def _init_estado() -> None:
    if st.session_state.get("catalog_admin_cargado"):
        return
    df_tipos, df_subs, df_meds = service.cargar_dataframes()
    st.session_state.catalog_df_tipos = df_tipos
    st.session_state.catalog_df_subs = df_subs
    st.session_state.catalog_df_meds = df_meds
    st.session_state.catalog_admin_cargado = True


def _recargar_desde_disco() -> None:
    df_tipos, df_subs, df_meds = service.cargar_dataframes()
    st.session_state.catalog_df_tipos = df_tipos
    st.session_state.catalog_df_subs = df_subs
    st.session_state.catalog_df_meds = df_meds


def _cabecera() -> None:
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#1a5276 0%,#2e86c1 100%);
                    border-radius:12px;padding:20px 24px;margin-bottom:16px;color:#fff;">
            <div style="display:flex;align-items:center;gap:12px;">
                <span style="font-size:1.8rem;">🏭</span>
                <div>
                    <h2 style="margin:0;font-size:1.4rem;font-weight:700;color:#fff;">
                        Catálogo, tarifas y usuarios
                    </h2>
                    <p style="margin:4px 0 0;font-size:0.85rem;opacity:0.9;">
                        Subestaciones, medidores, tarifas CFE y cuentas de acceso en la base de datos
                        (<code style="background:rgba(255,255,255,0.15);padding:1px 6px;border-radius:3px;color:#fff;">catalog_*</code>)
                        con validación de reglas de operación.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"Base de datos: `{service.ruta_almacenamiento()}` · "
        "Tablas `catalog_*`, `catalog_tarifas` y `catalog_usuarios`."
    )


def _barra_acciones() -> None:
    col_v, col_g, col_r, _ = st.columns([1, 1, 1, 2])
    with col_v:
        if st.button("Validar catálogo", use_container_width=True, key="cat_btn_validar"):
            errores = service.validar_dataframes(
                st.session_state.catalog_df_tipos,
                st.session_state.catalog_df_subs,
                st.session_state.catalog_df_meds,
            )
            if errores:
                st.session_state.catalog_ultimos_errores = errores
                st.error(f"El catálogo tiene {len(errores)} error(es). Vea la pestaña Validación.")
            else:
                st.session_state.catalog_ultimos_errores = []
                st.success("Catálogo válido. Puede guardar los cambios.")
    with col_g:
        if st.button("Guardar en disco", type="primary", use_container_width=True, key="cat_btn_guardar"):
            try:
                service.guardar_dataframes(
                    st.session_state.catalog_df_tipos,
                    st.session_state.catalog_df_subs,
                    st.session_state.catalog_df_meds,
                )
                st.session_state.catalog_ultimos_errores = []
                st.success(
                    "Catálogo guardado en la base de datos. "
                    "Los medidores de sync se actualizaron automáticamente."
                )
            except ValueError as exc:
                st.session_state.catalog_ultimos_errores = str(exc).splitlines()
                st.error("No se guardó: hay errores de validación.")
    with col_r:
        if st.button("Descartar cambios", use_container_width=True, key="cat_btn_descartar"):
            _recargar_desde_disco()
            st.session_state.catalog_ultimos_errores = []
            st.toast("Cambios descartados; se recargó desde la base de datos.")
            st.rerun()


def _tab_subestaciones() -> None:
    st.markdown("##### Subestaciones")
    st.caption(
        "`Generacion`: 0 = sin generación · 1 = grupo solar (tipo 4) · "
        "2 = generación individual (tipo 5, cogeneración u otro)."
    )
    opciones_gen = {
        service.ETIQUETAS_GENERACION[GENERACION_NINGUNA]: str(GENERACION_NINGUNA),
        service.ETIQUETAS_GENERACION[GENERACION_GRUPO]: str(GENERACION_GRUPO),
        service.ETIQUETAS_GENERACION[GENERACION_INDIVIDUAL]: str(GENERACION_INDIVIDUAL),
    }
    inv_gen = {v: k for k, v in opciones_gen.items()}
    df = st.session_state.catalog_df_subs.copy()
    df["Generacion"] = df["Generacion"].astype(str).map(lambda x: inv_gen.get(x, x))
    editado = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="cat_editor_subs",
        column_config={
            "Numero": st.column_config.NumberColumn("Número", min_value=1, step=1, required=True),
            "Nombre": st.column_config.TextColumn("Nombre", required=True, width="medium"),
            "Generacion": st.column_config.SelectboxColumn(
                "Generación",
                options=list(opciones_gen.keys()),
                required=True,
                width="large",
            ),
        },
    )
    out = editado.copy()
    out["Generacion"] = out["Generacion"].map(opciones_gen).fillna("0")
    out["Numero"] = out["Numero"].apply(
        lambda x: str(int(x)) if str(x).strip() and str(x) != "nan" else ""
    )
    st.session_state.catalog_df_subs = out.astype(str)


def _tab_tipos() -> None:
    st.markdown("##### Tipos de medidor")
    st.caption(
        "Define reglas de neteo, inversión REC/ENT y tratamiento de reactivos "
        "para cada tipo numérico."
    )
    st.session_state.catalog_df_tipos = st.data_editor(
        st.session_state.catalog_df_tipos,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="cat_editor_tipos",
        column_config={
            "Tipo": st.column_config.NumberColumn("Tipo", min_value=1, step=1, required=True),
            "Descripcion": st.column_config.TextColumn("Descripción", required=True),
            "Neteo": st.column_config.SelectboxColumn("Neteo", options=["0", "1"]),
            "Invertir": st.column_config.SelectboxColumn("Invertir", options=["0", "1"]),
            "Reactivos": st.column_config.SelectboxColumn(
                "Reactivos", options=["0", "1", "2"]
            ),
        },
    ).astype(str)


def _tab_medidores() -> None:
    st.markdown("##### Medidores")
    subs_nums = sorted(
        {
            str(x).strip()
            for x in st.session_state.catalog_df_subs["Numero"].tolist()
            if str(x).strip()
        },
        key=lambda x: int(x) if x.isdigit() else 0,
    )
    filtro = st.selectbox(
        "Filtrar por subestación",
        options=["Todas"] + subs_nums,
        key="cat_filtro_sub_med",
    )
    df = st.session_state.catalog_df_meds.copy()
    if filtro != "Todas":
        df = df[df["Subestacion"].astype(str) == filtro]

    st.caption(
        "ION: IP del medidor testigo · API: número de serie ISOL · "
        "Tipo 4: `Grupo_Generacion` obligatorio en subestaciones con Generacion=1."
    )
    editado = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"cat_editor_meds_{filtro}",
        column_config={
            "Nombre": st.column_config.TextColumn("Nombre", required=True),
            "Numero_Serie": st.column_config.TextColumn("Número serie"),
            "Subestacion": st.column_config.SelectboxColumn(
                "Subestación", options=subs_nums if subs_nums else [""]
            ),
            "Tipo_Medidor": st.column_config.NumberColumn("Tipo", min_value=1, max_value=9, step=1),
            "Descarga": st.column_config.SelectboxColumn(
                "Descarga", options=sorted(DESCARGAS_VALIDAS)
            ),
            "IP": st.column_config.TextColumn("IP"),
            "Puerto": st.column_config.NumberColumn("Puerto", min_value=0, step=1),
            "Grupo_Generacion": st.column_config.TextColumn("Grupo generación"),
            "Validado": st.column_config.TextColumn(
                "Validado", help="dd/mm/aaaa HH:MM o vacío"
            ),
        },
    )

    if filtro == "Todas":
        st.session_state.catalog_df_meds = editado.astype(str)
    else:
        completo = st.session_state.catalog_df_meds.copy()
        otros = completo[completo["Subestacion"].astype(str) != filtro]
        st.session_state.catalog_df_meds = pd.concat(
            [otros, editado.astype(str)], ignore_index=True
        )


def _tab_validacion() -> None:
    st.markdown("##### Validación de reglas")
    with st.expander("Reglas de negocio", expanded=False):
        st.markdown(service.REGLAS_RESUMEN)

    errores = st.session_state.get("catalog_ultimos_errores")
    if errores is None:
        errores = service.validar_dataframes(
            st.session_state.catalog_df_tipos,
            st.session_state.catalog_df_subs,
            st.session_state.catalog_df_meds,
        )
    if errores:
        st.error(f"Se encontraron {len(errores)} problema(s):")
        st.dataframe(
            pd.DataFrame({"Error": errores}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("El catálogo actual cumple todas las reglas definidas.")

    st.markdown("##### Vista consolidada")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Subestaciones")
        st.dataframe(st.session_state.catalog_df_subs, hide_index=True, use_container_width=True)
    with c2:
        st.caption("Tipos de medidor")
        st.dataframe(st.session_state.catalog_df_tipos, hide_index=True, use_container_width=True)
    with c3:
        st.caption(f"Medidores ({len(st.session_state.catalog_df_meds)})")
        st.dataframe(
            st.session_state.catalog_df_meds,
            hide_index=True,
            use_container_width=True,
            height=320,
        )


def _tab_tarifas() -> None:
    from bess.tariffs.store import column_config_tarifas, guardar_df_tarifas, leer_df_tarifas

    st.markdown("##### Tarifas mensuales")
    st.caption("Valores en MXN por tipo y mes (energía, capacidad, MEM, etc.). Se guardan en `catalog_tarifas`.")
    df_base = leer_df_tarifas()
    df_editado = st.data_editor(
        df_base,
        column_config=column_config_tarifas(),
        hide_index=True,
        num_rows="fixed",
        use_container_width=True,
        key="cat_editor_tarifas",
    )
    col_guardar, col_recargar = st.columns(2)
    with col_guardar:
        if st.button("Guardar tarifas", use_container_width=True, type="primary", key="cat_btn_guardar_tarifas"):
            ok, msg = guardar_df_tarifas(df_editado)
            if ok:
                st.success(f"Tarifas guardadas en {msg}.")
                st.session_state.pop("cat_editor_tarifas", None)
                st.rerun()
            else:
                st.error(msg)
    with col_recargar:
        if st.button("Descartar cambios", use_container_width=True, key="cat_btn_descartar_tarifas"):
            st.session_state.pop("cat_editor_tarifas", None)
            st.rerun()


def _tab_usuarios() -> None:
    from bess.ui.catalog_admin import users_store

    st.markdown("##### Usuarios de la aplicación")
    st.caption("Cuentas de acceso, roles y contraseñas. Tabla `catalog_usuarios` en la base de datos.")
    with st.expander("Reglas de usuarios", expanded=False):
        st.markdown(users_store.REGLAS_USUARIOS)

    df_base = users_store.cargar_dataframe_usuarios()
    df_editado = st.data_editor(
        df_base,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="cat_editor_usuarios",
        column_config={
            "Usuario": st.column_config.TextColumn("Usuario", required=True),
            "Nombre": st.column_config.TextColumn("Nombre visible", required=True),
            "Rol": st.column_config.SelectboxColumn(
                "Rol",
                options=users_store.opciones_rol(),
                required=True,
            ),
            "Activo": st.column_config.SelectboxColumn("Activo", options=["1", "0"]),
            "Nueva_contraseña": st.column_config.TextColumn(
                "Nueva contraseña",
                help="Obligatoria para usuarios nuevos. Vacía = sin cambio.",
            ),
        },
    )

    usuario_sesion = st.session_state.get("usuario")
    col_v, col_g, col_r = st.columns(3)
    with col_v:
        if st.button("Validar usuarios", use_container_width=True, key="cat_btn_validar_usuarios"):
            errores = users_store.validar_dataframe_usuarios(df_editado, usuario_sesion)
            if errores:
                st.error("\n".join(f"- {e}" for e in errores))
            else:
                st.success("Usuarios válidos.")
    with col_g:
        if st.button("Guardar usuarios", type="primary", use_container_width=True, key="cat_btn_guardar_usuarios"):
            try:
                users_store.guardar_dataframe_usuarios(df_editado, usuario_sesion)
                st.success("Usuarios guardados en la base de datos.")
                st.session_state.pop("cat_editor_usuarios", None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    with col_r:
        if st.button("Descartar cambios", use_container_width=True, key="cat_btn_descartar_usuarios"):
            st.session_state.pop("cat_editor_usuarios", None)
            st.rerun()

    if not df_base.empty:
        st.markdown("##### Resumen de roles")
        resumen = df_editado.copy()
        resumen["Rol"] = resumen["Rol"].map(users_store.etiqueta_rol)
        st.dataframe(
            resumen[["Usuario", "Nombre", "Rol", "Activo"]],
            hide_index=True,
            use_container_width=True,
        )


def main() -> None:
    _requiere_superadmin()
    aplicar_estilos()
    _init_estado()
    _cabecera()
    _barra_acciones()

    tab_subs, tab_tipos, tab_meds, tab_tar, tab_usr, tab_val = st.tabs(
        ["🏭 Subestaciones", "📋 Tipos medidor", "⚡ Medidores", "💲 Tarifas", "👤 Usuarios", "✅ Validación"]
    )
    with tab_subs:
        _tab_subestaciones()
    with tab_tipos:
        _tab_tipos()
    with tab_meds:
        _tab_medidores()
    with tab_tar:
        _tab_tarifas()
    with tab_usr:
        _tab_usuarios()
    with tab_val:
        _tab_validacion()
