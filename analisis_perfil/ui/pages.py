"""Página principal: subir perfiles, elegir tarifa y generar reportes."""

from __future__ import annotations

import sys
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st

from analisis_perfil import NOMBRE_APP, VERSION
from analisis_perfil.paths import DIR_PAQUETE, DIR_TRABAJO
from analisis_perfil.theme import (
    COLORES,
    DIVISIONES,
    REGION_POR_TARIFA,
    SERVICIOS,
    TARIFAS,
)
from analisis_perfil.ui.styles import aplicar_estilos, render_header, render_section_title
from bess.charts.layout import sanear_figura_plotly

# Scripts del pipeline (imports estilo script + subprocess cwd).
ROOT = DIR_PAQUETE
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRABAJO = DIR_TRABAJO

_MARCAS_GENERADO = (
    "_energia_por_",
    "_consumo_tipico_",
    "_perfil_tipico_",
    "_suma.csv",
    "_bidireccional.csv",
    "_bidi_",
)


def _plotly_chart(fig, **kwargs):
    """st.plotly_chart con leyenda/hover seguros (evita cuelgues del navegador)."""
    sanear_figura_plotly(fig)
    kwargs.setdefault("use_container_width", True)
    return st.plotly_chart(fig, **kwargs)


def _job_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = TRABAJO / stamp
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _nombre_unico(destino: Path, nombre: str, usados: dict[str, int]) -> str:
    stem = Path(nombre).stem
    suf = Path(nombre).suffix
    clave = nombre.lower()
    n = usados.get(clave, 0) + 1
    usados[clave] = n
    if n > 1:
        return f"{stem}_{n}{suf}"
    return nombre


def _es_csv_en_zip(ruta_interna: str) -> bool:
    """CSV de perfil dentro del ZIP (ignora carpetas basura y reportes derivados)."""
    n = ruta_interna.replace("\\", "/").lower()
    base = Path(n).name
    if not base.endswith(".csv") or base.startswith("."):
        return False
    if "__macosx" in n or n.startswith("."):
        return False
    # No re-importar salidas del propio analisis
    if any(
        x in base
        for x in (
            "_energia_por_",
            "_consumo_tipico_",
            "_perfil_tipico_",
            "_suma.csv",
            "_bidireccional.csv",
        )
    ):
        return False
    return True


def _extraer_csv_de_zip(contenido: bytes, destino: Path, usados: dict[str, int]) -> list[Path]:
    """Extrae CSV de un ZIP (p. ej. perfiles_descarga.zip de la suite)."""
    import zipfile
    from io import BytesIO

    rutas: list[Path] = []
    with zipfile.ZipFile(BytesIO(contenido)) as zf:
        for info in zf.infolist():
            if info.is_dir() or not _es_csv_en_zip(info.filename):
                continue
            nombre = _nombre_unico(destino, Path(info.filename).name, usados)
            path = destino / nombre
            path.write_bytes(zf.read(info))
            rutas.append(path)
    if not rutas:
        raise ValueError(
            "El ZIP no contiene CSV de perfil utilizables "
            "(se esperan archivos como los de la descarga de la suite)."
        )
    return rutas


def _guardar_uploads(uploaded, destino: Path) -> list[Path]:
    """Guarda CSV o extrae CSV desde ZIP. Nombres repetidos → sufijo _2, _3, …"""
    rutas, _, _ = _guardar_uploads_con_opciones(uploaded, destino, None, None)
    return rutas


def _guardar_uploads_con_opciones(
    uploaded,
    destino: Path,
    factores: list[float] | None,
    invertir: list[bool] | None,
) -> tuple[list[Path], list[float], list[bool]]:
    """Guarda/extrae perfiles; aplica multiplicador e inversión REC↔ENT.

    Un ZIP usa las opciones del archivo ZIP para todos sus CSV internos.
    """
    from multiplicar_perfil import aplicar_multiplicador, invertir_canales_rec_ent

    rutas: list[Path] = []
    factores_out: list[float] = []
    invert_out: list[bool] = []
    usados: dict[str, int] = {}
    for i, uf in enumerate(uploaded):
        nombre = Path(uf.name).name
        data = uf.getvalue()
        factor = 1.0
        if factores is not None and i < len(factores):
            factor = float(factores[i])
        inv = bool(invertir[i]) if invertir is not None and i < len(invertir) else False

        def _aplicar(path: Path, *, fac: float = factor, do_inv: bool = inv) -> None:
            if do_inv:
                invertir_canales_rec_ent(path)
            aplicar_multiplicador(path, fac)

        if nombre.lower().endswith(".zip"):
            extraidos = _extraer_csv_de_zip(data, destino, usados)
            for path in extraidos:
                _aplicar(path)
                rutas.append(path)
                factores_out.append(factor)
                invert_out.append(inv)
        else:
            nombre_out = _nombre_unico(destino, nombre, usados)
            path = destino / nombre_out
            path.write_bytes(data)
            _aplicar(path)
            rutas.append(path)
            factores_out.append(factor)
            invert_out.append(inv)
    return rutas, factores_out, invert_out


def _ui_opciones_perfil(
    archivos,
    *,
    key_prefix: str,
    reset: int,
    titulo: str = "Opciones",
) -> tuple[list[float], list[bool]]:
    """Multiplicador + canales invertidos por archivo."""
    if not archivos:
        return [], []
    st.markdown(f"**{titulo}**")
    factores: list[float] = []
    invertir: list[bool] = []
    for i, uf in enumerate(archivos):
        nombre = Path(uf.name).name
        es_zip = nombre.lower().endswith(".zip")
        etiqueta = f"{nombre}" + (" (ZIP)" if es_zip else "")
        col_n, col_f, col_i = st.columns([2.4, 0.9, 1.4])
        with col_n:
            st.markdown(
                f"<div style='padding-top:0.45rem'>{etiqueta}</div>",
                unsafe_allow_html=True,
            )
        with col_f:
            fac = st.number_input(
                f"× {nombre}",
                min_value=0.0,
                value=1.0,
                step=0.1,
                format="%.4f",
                key=f"mult_{key_prefix}_{i}_{nombre}_{reset}",
                label_visibility="collapsed",
            )
        with col_i:
            inv = st.checkbox(
                "Canales invertidos",
                value=False,
                key=f"inv_{key_prefix}_{i}_{nombre}_{reset}",
                help="Intercambia KWH_REC y KWH_ENT",
            )
        factores.append(float(fac))
        invertir.append(bool(inv))
    return factores, invertir


def _listar_salidas(carpeta: Path, esquema: str) -> dict[str, list[Path]]:
    """Clasifica CSV/PNG generados en la carpeta de trabajo."""
    clave = esquema.lower()
    grupos: dict[str, list[Path]] = {
        "diario": [],
        "mensual": [],
        "tipico_semana": [],
        "por_hora": [],
        "perfil_hora": [],
        "graficas": [],
        "suma": [],
        "otros": [],
    }
    for p in sorted(carpeta.rglob("*")):
        if not p.is_file():
            continue
        n = p.name.lower()
        es_perfil_base = (
            n.endswith("_suma.csv")
            or n.endswith("_bidireccional.csv")
            or ("_bidi_" in n and n.endswith(".csv"))
        ) and not any(
            x in n for x in ("energia_por", "consumo_tipico", "perfil_tipico", "grafica")
        )
        if es_perfil_base:
            grupos["suma"].append(p)
        elif "energia_por_dia" in n and n.endswith(".csv"):
            grupos["diario"].append(p)
        elif "energia_por_mes" in n and n.endswith(".csv"):
            grupos["mensual"].append(p)
        elif "consumo_tipico_semana" in n and n.endswith(".csv"):
            grupos["tipico_semana"].append(p)
        elif f"energia_por_hora_{clave}" in n and n.endswith(".csv"):
            grupos["por_hora"].append(p)
        elif f"perfil_tipico_hora_{clave}" in n and n.endswith(".csv"):
            grupos["perfil_hora"].append(p)
        elif p.suffix.lower() == ".png":
            grupos["graficas"].append(p)
        elif p.suffix.lower() == ".csv":
            if not any(
                x in n
                for x in (
                    "energia_por",
                    "consumo_tipico",
                    "perfil_tipico",
                    "_suma",
                    "_bidi_",
                    "bidireccional",
                )
            ):
                continue
            grupos["otros"].append(p)
    return grupos


def _es_csv_generado(nombre: str) -> bool:
    n = nombre.lower()
    if not n.endswith(".csv"):
        return False
    return any(m in n for m in _MARCAS_GENERADO)


def _marcar_descargados(rutas: list[str]) -> None:
    actuales = list(st.session_state.get("archivos_descargados") or [])
    for r in rutas:
        if r not in actuales:
            actuales.append(r)
    st.session_state["archivos_descargados"] = actuales


def _borrar_csv_no_descargados() -> int:
    """Elimina CSV generados en trabajo/ que el usuario no descargó."""
    descargados = {
        str(Path(p).resolve())
        for p in (st.session_state.get("archivos_descargados") or [])
    }
    borrados = 0
    if not TRABAJO.exists():
        return 0
    for path in list(TRABAJO.rglob("*.csv")):
        if not path.is_file() or not _es_csv_generado(path.name):
            continue
        if str(path.resolve()) in descargados:
            continue
        try:
            path.unlink()
            borrados += 1
        except OSError:
            continue
    # Quitar carpetas de trabajo vacías
    if TRABAJO.exists():
        for carpeta in sorted(TRABAJO.rglob("*"), reverse=True):
            if carpeta.is_dir():
                try:
                    next(carpeta.iterdir())
                except StopIteration:
                    try:
                        carpeta.rmdir()
                    except OSError:
                        pass
    return borrados


def _limpiar_todo() -> None:
    """Resetea opciones de UI y borra CSV generados no descargados."""
    n = _borrar_csv_no_descargados()
    for clave in (
        "ultimo_job",
        "ultimo_esquema",
        "ultimo_servicio",
        "ultimo_resumen",
        "ultimo_perfil",
        "_pdf_cache_key",
        "_pdf_cache_bytes",
        "detalle_perfil_dia",
        "_perfil_dia_ignore",
        "energia_drill_rev",
        "archivos_descargados",
        "api_perfiles",
        "api_perfiles_consumo",
        "api_perfiles_generacion",
        "_rango_fuentes_cache",
        "analisis_paso",
        "_ap_cfg",
    ):
        st.session_state.pop(clave, None)
    st.session_state["ui_reset"] = int(st.session_state.get("ui_reset") or 0) + 1
    st.session_state["analisis_paso"] = "Preparar"
    st.session_state["limpiar_flash"] = (
        f"Sesión reiniciada. Se eliminaron {n} CSV generado(s) sin descargar."
    )


def _fuentes_para_rango(
    servicio_sel: str,
    *,
    uploaded=None,
    uploaded_consumo=None,
    uploaded_generacion=None,
    api_files=None,
    api_consumo=None,
    api_generacion=None,
):
    """Lista de archivos (upload/API) para detectar rango de fechas."""
    if servicio_sel == "bidireccional":
        return list(uploaded_consumo or api_consumo or []) + list(
            uploaded_generacion or api_generacion or []
        )
    return list(uploaded or api_files or [])


def _rango_detectado_fuentes(fuentes) -> tuple | None:
    if not fuentes:
        return None
    firmas = tuple(
        (Path(getattr(f, "name", "")).name, len(f.getvalue())) for f in fuentes
    )
    cache = st.session_state.get("_rango_fuentes_cache")
    if cache and cache.get("firmas") == firmas:
        return cache.get("rango")
    from calidad_perfil import rango_fechas_desde_fuentes

    rango = rango_fechas_desde_fuentes(fuentes)
    st.session_state["_rango_fuentes_cache"] = {"firmas": firmas, "rango": rango}
    return rango


def _mostrar_calidad(perfil: Path, servicio: str) -> None:
    from calidad_perfil import analizar_calidad_perfil

    if servicio == "bidireccional":
        cols = ("KWH_REC", "KWH_ENT", "KWH_GEN")
    elif servicio == "neteo":
        cols = ("KWH_REC", "KWH_ENT")
    elif servicio == "generacion":
        cols = ("KWH_ENT",)
    else:
        cols = ("KWH_REC",)
    try:
        qa = analizar_calidad_perfil(perfil, columnas=cols)
    except Exception as exc:
        st.warning(f"No se pudo evaluar calidad del perfil: {exc}")
        return
    with st.container(border=True):
        st.markdown(
            '<p class="section-title" style="border:none;padding:0;margin:0 0 8px 0;">'
            "Calidad de datos</p>",
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Filas", f"{qa.get('n_filas', 0):,}")
        c2.metric("Días", f"{qa.get('n_dias', 0)}")
        c3.metric("Cobertura", f"{qa.get('cobertura_pct', 0):.1f}%")
        c4.metric("Huecos", f"{qa.get('n_huecos', 0)}")
        st.caption(
            f"Frecuencia ≈ {qa.get('frecuencia_min', 5)} min · "
            f"Periodo {qa.get('fecha_min')} → {qa.get('fecha_max')}"
            + (
                f" · {qa.get('minutos_faltantes', 0):.0f} min faltantes"
                if qa.get("minutos_faltantes")
                else ""
            )
        )
        alertas = qa.get("alertas") or []
        if alertas:
            st.warning(" · ".join(alertas))
        else:
            st.success("Sin alertas de cobertura ni huecos relevantes.")
        huecos = qa.get("huecos") or []
        if huecos:
            with st.expander("Detalle de huecos (muestra)"):
                st.dataframe(huecos, hide_index=True, use_container_width=True)


def _mostrar_demanda_pico(perfil: Path, servicio: str) -> None:
    from demanda_pico import demanda_pico_consumo_real, demanda_pico_perfil

    col = "KWH_ENT" if servicio == "generacion" else "KWH_REC"
    try:
        pico = demanda_pico_perfil(perfil, col)
        pico_real = (
            demanda_pico_consumo_real(perfil)
            if servicio == "bidireccional"
            else None
        )
    except Exception as exc:
        st.caption(f"Demanda pico no disponible: {exc}")
        return
    if not pico and not pico_real:
        return

    with st.container(border=True):
        st.markdown(
            '<p class="section-title" style="border:none;padding:0;margin:0 0 8px 0;">'
            "Demanda máxima</p>",
            unsafe_allow_html=True,
        )
        st.caption(
            "kW = kWh del intervalo × (60 / minutos). "
            "Clic en «Ver perfil del día» abre el cincominutal."
        )
        cols = st.columns(2 if pico_real else 1)
        items = [("Canal " + col, pico, col)]
        if pico_real:
            items.append(("Consumo real", pico_real, "CONSUMO_REAL"))
        for i, (titulo, p, col_drill) in enumerate(items):
            if not p:
                continue
            with cols[i if pico_real else 0]:
                st.markdown(
                    f"**{titulo}:** **{p['kw']:,.2f} kW** · "
                    f"{p['timestamp']} · día operativo {p['dia']}"
                )
                st.caption(
                    f"Intervalo {p['frecuencia_min']} min · "
                    f"{p['kwh_intervalo']:.4f} kWh"
                )
                if st.button(
                    f"Ver perfil del día ({p['dia']})",
                    key=f"pico_dia_{p['columna']}_{p['dia']}",
                ):
                    st.session_state["detalle_perfil_dia"] = {
                        "dia": p["dia"],
                        "columna": col_drill,
                        "color": COLORES["danger"],
                    }
                    st.rerun()


def _zip_bytes(archivos: list[Path], base: Path) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in archivos:
            try:
                arc = p.relative_to(base)
            except ValueError:
                arc = p.name
            zf.write(p, arcname=str(arc))
    return buf.getvalue()


def _botones_descarga(archivos: list[Path]) -> None:
    if not archivos:
        st.caption("Sin archivos en esta categoría.")
        return
    cols = st.columns(min(3, len(archivos)))
    for i, path in enumerate(archivos):
        with cols[i % 3]:
            ruta = str(path.resolve())
            st.download_button(
                label=path.name,
                data=path.read_bytes(),
                file_name=path.name,
                mime="text/csv" if path.suffix.lower() == ".csv" else "application/octet-stream",
                key=f"dl_{path.name}_{i}_{st.session_state.get('ui_reset', 0)}",
                use_container_width=True,
                on_click=_marcar_descargados,
                args=([ruta],),
            )


def _ejecutar_pipeline(
    archivos: list[Path],
    codigo_tarifa: str,
    servicio: str,
    archivos_generacion: list[Path] | None = None,
    *,
    region: str | None = None,
    fecha_desde=None,
    fecha_hasta=None,
) -> tuple[Path, dict, Path]:
    from aportaciones_medidores import aportaciones_medidores
    from procesar_perfil_completo import (
        TARIFA_MAP,
        preparar_perfil,
        preparar_perfil_bidireccional,
        procesar_perfil,
    )

    esquema = TARIFA_MAP[codigo_tarifa]
    aportaciones: dict = {}
    if servicio == "bidireccional":
        if not archivos_generacion:
            raise ValueError("Bidireccional requiere perfiles de generación.")
        if len(archivos) >= 2:
            aportaciones["consumo"] = {
                "titulo": "Consumo (KWH_REC → Energía Entregada)",
                "columna": "KWH_REC",
                "medidores": aportaciones_medidores(
                    archivos,
                    "KWH_REC",
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                ),
            }
        if len(archivos_generacion) >= 2:
            aportaciones["generacion"] = {
                "titulo": "Generación (KWH_ENT → Energía Generada)",
                "columna": "KWH_ENT",
                "medidores": aportaciones_medidores(
                    archivos_generacion,
                    "KWH_ENT",
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                ),
            }
        perfil = preparar_perfil_bidireccional(archivos, archivos_generacion)
    else:
        col = "KWH_ENT" if servicio == "generacion" else "KWH_REC"
        if len(archivos) >= 2:
            etiqueta = {
                "consumo": "Consumo (KWH_REC)",
                "generacion": "Generación (KWH_ENT)",
                "neteo": "Neteo (KWH_REC)",
            }.get(servicio, servicio)
            aportaciones[servicio] = {
                "titulo": etiqueta,
                "columna": col,
                "medidores": aportaciones_medidores(
                    archivos,
                    col,
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                ),
            }
        perfil = preparar_perfil(servicio, archivos)
    resumen = procesar_perfil(
        perfil,
        esquema,
        servicio,
        region=region,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    if aportaciones:
        resumen["aportaciones"] = aportaciones
    # Si hubo filtro de fechas, el cincominutal efectivo es *_rango.csv
    perfil_efectivo = perfil
    rango = perfil.with_name(f"{perfil.stem}_rango.csv")
    if rango.is_file():
        perfil_efectivo = rango
    return perfil.parent, resumen, perfil_efectivo


def _html_periodos(valores: dict, horaria: bool) -> str:
    if not horaria or not valores.get("por_periodo"):
        return ""
    from servicio_config import PERIODOS

    filas = []
    for periodo in PERIODOS:
        val = valores["por_periodo"].get(periodo, 0.0)
        filas.append(
            f"<div><span>{periodo}</span><strong>{val:,.1f} kWh</strong></div>"
        )
    return f'<div class="periodos">{"".join(filas)}</div>'


def _html_metric_card(etiqueta: str, valores: dict, color: str, horaria: bool, sub: str = "") -> str:
    return f"""
    <div class="metric-card" style="border-top:3px solid {color};">
        <div class="label">{etiqueta} (kWh)</div>
        <div class="value">{valores['total']:,.1f}</div>
        {_html_periodos(valores, horaria)}
    </div>
    """


def _html_escalones(
    escalones: dict | None,
    etiquetas: tuple[tuple[str, str], ...] | None = None,
) -> str:
    if not escalones:
        return ""
    pares = etiquetas or (
        ("basico", "Básico"),
        ("intermedio", "Intermedio"),
        ("excedente", "Excedente"),
    )
    filas = []
    for clave, nombre in pares:
        esc = escalones.get(clave) or {}
        kwh = float(esc.get("kwh", 0.0))
        importe = float(esc.get("importe", 0.0))
        filas.append(
            f"<div><span>{nombre}</span>"
            f"<strong>{kwh:,.1f} kWh · ${importe:,.2f}</strong></div>"
        )
    return f'<div class="periodos">{"".join(filas)}</div>'


def _html_money_card(
    etiqueta: str,
    importe: float,
    color: str,
    detalle: str = "",
    escalones: dict | None = None,
    etiquetas_escalones: tuple[tuple[str, str], ...] | None = None,
) -> str:
    det = ""
    if detalle:
        det = f'<div class="periodos"><div><span>{detalle}</span></div></div>'
    return f"""
    <div class="metric-card" style="border-top:3px solid {color};">
        <div class="label">{etiqueta} (MXN)</div>
        <div class="value">${importe:,.2f}</div>
        {det}
        {_html_escalones(escalones, etiquetas_escalones)}
    </div>
    """


def _caption_tarifa_t01(bloque: dict) -> None:
    """Vigencia / precios / bloques; nota de prorrateo si aplica."""
    precios = bloque["precios"]
    titulo = bloque.get("titulo_tarifa") or bloque.get("esquema") or "Tarifa"
    etiq = tuple(bloque.get("etiquetas_escalones") or ())
    pares_precio = etiq if etiq else tuple((k, k.capitalize()) for k in precios)
    precios_html = " · ".join(
        f'{nombre} <strong>${precios[clave]:.4f}</strong>'
        for clave, nombre in pares_precio
        if clave in precios
    )
    extra = ""
    bloques = bloque.get("bloques_kwh")
    if bloques:
        extra = (
            f' (bloques {bloques["basico"]:.0f}/'
            f'{bloques["intermedio"]:.0f}/resto)'
        )
    metodo = bloque.get("metodo") or ""
    if metodo == "promedio_meses_cfe":
        nota = (
            " · Precio = promedio simple de los meses del periodo; "
            "bloques sobre el kWh total (método recibo CFE)"
        )
    else:
        nota = ""
    st.markdown(
        f'<div class="fecha-resumen">'
        f'{titulo}: <strong>{bloque["fecha_tarifa"]}</strong> · '
        f"{precios_html} /kWh{extra}{nota}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _mostrar_dac(bloque: dict) -> None:
    dac = bloque.get("dac") or {}
    if not dac:
        return
    prom = float(dac.get("promedio_mensual_kwh") or 0)
    lim = float(dac.get("limite_kwh_mes") or 250)
    if dac.get("supera_dac"):
        st.warning(
            f"Promedio mensual equivalente ≈ **{prom:,.1f} kWh/mes** "
            f"(límite DAC {lim:.0f} kWh/mes). Riesgo de reclasificación a "
            "Tarifa Doméstica de Alto Consumo."
        )
    else:
        st.caption(
            f"Promedio mensual equivalente ≈ {prom:,.1f} kWh/mes "
            f"(límite DAC {lim:.0f} kWh/mes)."
        )


def _mostrar_meses_promedio(filas: list[dict]) -> None:
    if not filas or len(filas) < 2:
        return
    st.markdown("**Precios mensuales promediados**")
    st.dataframe(
        [
            {
                "Mes": r["mes"],
                "Tarifa": r.get("fecha_tarifa", ""),
                "Básico $/kWh": r.get("precios", {}).get("basico"),
                "Intermedio $/kWh": r.get("precios", {}).get("intermedio"),
                "Excedente $/kWh": r.get("precios", {}).get("excedente"),
            }
            for r in filas
        ],
        hide_index=True,
        use_container_width=True,
    )


def _mostrar_ahorro(ahorro: dict) -> None:
    with st.container(border=True):
        st.markdown(
            '<p class="section-title" style="border:none;padding:0;margin:0 0 8px 0;">'
            "Ahorro de Energía</p>",
            unsafe_allow_html=True,
        )
        etiq = tuple(ahorro.get("etiquetas_escalones") or ())
        _caption_tarifa_t01(ahorro)
        _mostrar_dac(ahorro)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                _html_money_card(
                    "Costo Neteo",
                    ahorro["neteo"]["importe"],
                    COLORES["warning"],
                    f'{ahorro["neteo"]["kwh"]:,.1f} kWh',
                    ahorro["neteo"].get("escalones"),
                    etiq or None,
                ),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                _html_money_card(
                    ahorro.get("etiqueta_ahorro") or "Ahorro (Real − Neteo)",
                    ahorro["ahorro"],
                    COLORES["success"],
                ),
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                _html_money_card(
                    ahorro.get("etiqueta_real") or "Costo Consumo Real",
                    ahorro["real"]["importe"],
                    COLORES["danger"],
                    f'{ahorro["real"]["kwh"]:,.1f} kWh',
                    ahorro["real"].get("escalones"),
                    etiq or None,
                ),
                unsafe_allow_html=True,
            )
        _mostrar_meses_promedio(list(ahorro.get("meses_promedio") or []))


def _mostrar_costo(costo: dict) -> None:
    with st.container(border=True):
        st.markdown(
            '<p class="section-title" style="border:none;padding:0;margin:0 0 8px 0;">'
            "Costo de Energía</p>",
            unsafe_allow_html=True,
        )
        etiq = tuple(costo.get("etiquetas_escalones") or ())
        _caption_tarifa_t01(costo)
        _mostrar_dac(costo)
        cons = costo["consumo"]
        st.markdown(
            _html_money_card(
                "Costo Consumo",
                cons["importe"],
                COLORES["primary"],
                f'{cons["kwh"]:,.1f} kWh',
                cons.get("escalones"),
                etiq or None,
            ),
            unsafe_allow_html=True,
        )
        _mostrar_meses_promedio(list(costo.get("meses_promedio") or []))


def _series_energia_diaria(servicio: str) -> list[tuple[str, str, str]]:
    """(columna CSV, título, color) según servicio."""
    if servicio == "generacion":
        return [("TOTAL_REC", "Energía Recibida (KWH_ENT)", COLORES["success"])]
    if servicio == "bidireccional":
        return [
            ("TOTAL_REC", "Energía Entregada (KWH_REC)", COLORES["primary"]),
            ("TOTAL_ENT", "Energía Recibida (KWH_ENT)", COLORES["secondary"]),
            ("TOTAL_GEN", "Energía Generada (KWH_GEN)", COLORES["success"]),
        ]
    if servicio == "neteo":
        return [
            ("TOTAL_REC", "Energía Entregada (KWH_REC)", COLORES["primary"]),
            ("TOTAL_ENT", "Energía Recibida (KWH_ENT)", COLORES["secondary"]),
            ("CONSUMO_REAL", "Neteo (REC − ENT)", COLORES["warning"]),
        ]
    return [("TOTAL_REC", "Energía Consumo (KWH_REC)", COLORES["primary"])]


def _columna_drilldown_perfil(servicio: str, titulo: str) -> str | None:
    """Columna cincominutal para clic en barra, o None si la gráfica no lo soporta."""
    t = titulo.lower()
    if servicio == "consumo":
        return "KWH_REC"
    if servicio in ("bidireccional", "neteo"):
        if "entregada" in t:
            return "KWH_REC"
        if "recibida" in t and "generada" not in t:
            return "KWH_ENT"
        if "generada" in t:
            return "KWH_GEN"
        if "neteo" in t:
            return "CONSUMO_REAL"
        return None
    if servicio == "generacion" and "recibida" in t:
        return "KWH_ENT"
    return None


def _leer_diario_csv(diario: Path) -> list[dict]:
    import csv

    with diario.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        filas = []
        for row in reader:
            item = {"FECHA": row[campos["FECHA"]].strip()[:10]}
            for clave, col in campos.items():
                if clave == "FECHA":
                    continue
                try:
                    item[clave] = float(row[col] or 0)
                except ValueError:
                    item[clave] = 0.0
            filas.append(item)
        return filas


def _nombre_dia_semana(dia: str) -> str:
    """YYYY-MM-DD → Lunes…Domingo."""
    from datetime import date

    nombres = (
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    )
    try:
        return nombres[date.fromisoformat(dia[:10]).weekday()]
    except ValueError:
        return ""


def _figura_perfil_cincominutal(
    horas: list[str],
    valores: list[float],
    *,
    dia: str,
    color: str,
    columna: str = "KWH_REC",
):
    import plotly.graph_objects as go

    total = sum(valores)
    dia_sem = _nombre_dia_semana(dia)
    titulo_dia = f"{dia_sem} {dia}" if dia_sem else dia
    fig = go.Figure(
        data=[
            go.Scatter(
                x=horas,
                y=valores,
                mode="lines",
                line=dict(color=color, width=2),
                fill="tozeroy",
                fillcolor="rgba(26,82,118,0.12)",
                hovertemplate=(
                    f"<b>%{{x}}</b><br>{columna}: <b>%{{y:,.4f}} kWh</b>"
                    "<extra></extra>"
                ),
                name=columna,
            )
        ]
    )
    fig.update_layout(
        title=dict(
            text=(
                f"Perfil cincominutal · {titulo_dia} · "
                f"{len(valores)} int. · {total:,.2f} kWh"
            ),
            font=dict(size=16, color=COLORES["text"]),
        ),
        xaxis_title="Hora",
        yaxis_title="kWh / intervalo",
        margin=dict(l=48, r=24, t=56, b=48),
        height=480,
        showlegend=False,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#e2e8f0", zeroline=False),
        hoverlabel=dict(bgcolor="white", font_size=13),
    )
    return fig


def _cerrar_perfil_dia_modal() -> None:
    """Limpia el modal y remonta la gráfica diaria sin barra seleccionada."""
    st.session_state.pop("detalle_perfil_dia", None)
    st.session_state.pop("_perfil_dia_ignore", None)
    st.session_state["energia_drill_rev"] = (
        int(st.session_state.get("energia_drill_rev") or 0) + 1
    )


@st.dialog(
    "Perfil cincominutal",
    width="large",
    on_dismiss=_cerrar_perfil_dia_modal,
)
def _dialog_perfil_dia(
    dia: str,
    horas: list[str],
    valores: list[float],
    color: str,
    columna: str = "KWH_REC",
) -> None:
    """Ventana modal del día; Cerrar (o la X) regresa al reporteador."""
    dia_sem = _nombre_dia_semana(dia)
    etiqueta = f"**{dia_sem}** · **{dia}**" if dia_sem else f"**{dia}**"
    st.markdown(
        f"Día operativo {etiqueta} · {len(valores)} intervalos cincominutales · "
        f"columna **{columna}**"
    )
    _plotly_chart(
        _figura_perfil_cincominutal(
            horas, valores, dia=dia, color=color, columna=columna
        ),
        config={"displayModeBar": True},
    )
    if st.button("Cerrar", type="primary", use_container_width=True, key="cerrar_perfil_dia"):
        _cerrar_perfil_dia_modal()
        st.rerun()


def _dia_desde_seleccion_plotly(event) -> str | None:
    """Extrae YYYY-MM-DD del primer punto seleccionado en st.plotly_chart."""
    if event is None:
        return None
    try:
        points = event.selection.points
    except Exception:
        try:
            points = event["selection"]["points"]
        except Exception:
            return None
    if not points:
        return None
    p0 = points[0]
    if isinstance(p0, dict):
        x = p0.get("x")
    else:
        x = getattr(p0, "x", None)
        if x is None and hasattr(p0, "get"):
            x = p0.get("x")
    if x is None:
        return None
    return str(x).strip()[:10]


def _chart_energia_drilldown(
    *,
    fechas: list[str],
    valores: list[float],
    titulo: str,
    color: str,
    chart_key: str,
    col_perfil: str,
    height: int = 380,
) -> None:
    """Barras diarias: clic en un día abre el perfil cincominutal (modal)."""
    import plotly.graph_objects as go

    fig = go.Figure(
        data=[
            go.Bar(
                x=fechas,
                y=valores,
                marker_color=color,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Energía: <b>%{y:,.2f} kWh</b>"
                    "<extra></extra>"
                ),
                name=titulo,
                customdata=fechas,
            )
        ]
    )
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=16, color=COLORES["text"])),
        xaxis_title="Día",
        yaxis_title="kWh",
        margin=dict(l=40, r=20, t=50, b=60),
        height=height,
        showlegend=False,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(tickangle=-45, showgrid=False, type="category"),
        yaxis=dict(showgrid=True, gridcolor="#e2e8f0", zeroline=False),
        hoverlabel=dict(bgcolor="white", font_size=13),
        clickmode="event+select",
        dragmode=False,
    )
    rev = int(st.session_state.get("energia_drill_rev") or 0)
    event = _plotly_chart(
        fig,
        on_select="rerun",
        selection_mode="points",
        key=f"energia_drill_{chart_key}_{rev}",
        config={
            "displayModeBar": True,
            "doubleClick": False,
            "modeBarButtonsToRemove": [
                "select2d",
                "lasso2d",
                "zoom2d",
                "zoomIn2d",
                "zoomOut2d",
                "pan2d",
                "autoScale2d",
            ],
        },
    )
    dia = _dia_desde_seleccion_plotly(event)
    if not dia:
        return
    st.session_state["detalle_perfil_dia"] = {
        "dia": dia,
        "columna": col_perfil,
        "color": color,
    }


def _mostrar_graficas_energia_diaria(
    diario: Path,
    servicio: str,
    *,
    perfil: Path | None = None,
) -> None:
    """Barras interactivas (Plotly) con tooltip al pasar el cursor.

    Clic en un día → perfil cincominutal (modal con Cerrar):
      - consumo: Energía Consumo (KWH_REC)
      - bidireccional: Energía Entregada (KWH_REC)
      - generación: Energía Recibida (KWH_ENT)
    """
    import plotly.graph_objects as go

    if not diario.exists():
        return
    filas = _leer_diario_csv(diario)
    if not filas:
        return
    fechas = [r["FECHA"] for r in filas]
    series = _series_energia_diaria(servicio)

    perfil_path = perfil
    if perfil_path is None or not Path(perfil_path).is_file():
        from analisis_perfil.ui.perfil_dia_popup import inferir_perfil_cincominutal

        perfil_path = inferir_perfil_cincominutal(diario, diario.parent)

    def _layout(titulo: str, showlegend: bool = False) -> dict:
        return dict(
            title=dict(text=titulo, font=dict(size=16, color=COLORES["text"])),
            xaxis_title="Día",
            yaxis_title="kWh",
            margin=dict(l=40, r=20, t=50, b=130 if showlegend else 60),
            height=460 if showlegend else 380,
            showlegend=showlegend,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.42,
                xanchor="center",
                x=0.5,
                itemclick=False,
                itemdoubleclick=False,
            ),
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            xaxis=dict(tickangle=-45, showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#e2e8f0", zeroline=False),
            hoverlabel=dict(bgcolor="white", font_size=13),
            barmode="overlay",
        )

    with st.container(border=True):
        st.markdown(
            '<p class="section-title" style="border:none;padding:0;margin:0 0 8px 0;">'
            "Energía por día</p>",
            unsafe_allow_html=True,
        )
        if fechas:
            st.caption(
                f"Periodo: {fechas[0]} → {fechas[-1]} ({len(fechas)} días)"
            )
        for col, titulo, color in series:
            if col not in filas[0]:
                continue
            valores = [r.get(col, 0.0) for r in filas]
            col_perfil = _columna_drilldown_perfil(servicio, titulo)
            if col_perfil and perfil_path and Path(perfil_path).is_file():
                _chart_energia_drilldown(
                    fechas=fechas,
                    valores=valores,
                    titulo=titulo,
                    color=color,
                    chart_key=f"{servicio}_{col_perfil}_{col}",
                    col_perfil=col_perfil,
                )
                continue

            fig = go.Figure(
                data=[
                    go.Bar(
                        x=fechas,
                        y=valores,
                        marker_color=color,
                        hovertemplate=(
                            "<b>%{x}</b><br>"
                            "Energía: <b>%{y:,.2f} kWh</b>"
                            "<extra></extra>"
                        ),
                        name=titulo,
                    )
                ]
            )
            fig.update_layout(**_layout(titulo))
            _plotly_chart(fig)

        # Cuarta gráfica (bidireccional): Consumo Real = Neteo + resto (apiladas)
        if servicio == "bidireccional" and all(
            c in filas[0] for c in ("TOTAL_REC", "TOTAL_ENT", "TOTAL_GEN")
        ):
            if "CONSUMO_REAL" in filas[0]:
                consumo_real = [r["CONSUMO_REAL"] for r in filas]
            else:
                consumo_real = [
                    r["TOTAL_REC"] + r["TOTAL_GEN"] - r["TOTAL_ENT"] for r in filas
                ]
            neteo = [r["TOTAL_REC"] - r["TOTAL_ENT"] for r in filas]
            resto = [cr - n for cr, n in zip(consumo_real, neteo)]

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=fechas,
                    y=neteo,
                    name="Neteo",
                    marker_color=COLORES["warning"],
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "Neteo: <b>%{y:,.2f} kWh</b><br>"
                        "<extra></extra>"
                    ),
                )
            )
            fig.add_trace(
                go.Bar(
                    x=fechas,
                    y=resto,
                    name="Generación",
                    marker_color=COLORES["danger"],
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "Generación: <b>%{y:,.2f} kWh</b><br>"
                        "Consumo Real: <b>%{customdata:,.2f} kWh</b>"
                        "<extra></extra>"
                    ),
                    customdata=consumo_real,
                )
            )
            layout = _layout("Consumo Real = Neteo + Generación", showlegend=True)
            layout["barmode"] = "relative"
            layout["bargap"] = 0.15
            fig.update_layout(**layout)
            fig.update_xaxes(type="category")
            _plotly_chart(fig)


def _abrir_dialog_dia_si_pendiente(perfil_path: Path | None) -> None:
    detalle = st.session_state.get("detalle_perfil_dia")
    if not detalle or not perfil_path or not Path(perfil_path).is_file():
        return
    from analisis_perfil.ui.perfil_dia_popup import puntos_perfil_dia

    dia_activo = str(detalle.get("dia") or "")
    col_perfil = str(detalle.get("columna") or "KWH_REC")
    color_det = str(detalle.get("color") or COLORES["primary"])
    try:
        horas, vals = puntos_perfil_dia(
            Path(perfil_path), dia_activo, col_perfil
        )
    except Exception as exc:
        st.warning(f"No se pudo leer el perfil del día {dia_activo}: {exc}")
        st.session_state.pop("detalle_perfil_dia", None)
        return
    if not horas:
        st.warning(
            f"Sin intervalos cincominutales de {col_perfil} para {dia_activo}."
        )
        st.session_state.pop("detalle_perfil_dia", None)
        return
    _dialog_perfil_dia(dia_activo, horas, vals, color_det, col_perfil)


DIAS_SEMANA = (
    "Lunes",
    "Martes",
    "Miercoles",
    "Jueves",
    "Viernes",
    "Sabado",
    "Domingo",
)

COLORES_DIA = {
    "Lunes": "#1a5276",
    "Martes": "#2e86c1",
    "Miercoles": "#27ae60",
    "Jueves": "#8e44ad",
    "Viernes": "#3498db",
    "Sabado": "#f39c12",
    "Domingo": "#e74c3c",
}


def _leer_perfil_tipico(ruta: Path) -> list[dict]:
    import csv

    with ruta.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        campos = {c.strip().upper(): c for c in reader.fieldnames}
        filas = []
        for row in reader:
            item = {
                "DIA_SEMANA": row[campos["DIA_SEMANA"]].strip(),
                "HORA": int(float(row[campos["HORA"]])),
            }
            for clave in (
                "CONSUMO_TIPICO",
                "ENTREGA_TIPICA",
                "GENERACION_TIPICA",
                "CONSUMO_REAL_TIPICO",
            ):
                if clave in campos:
                    try:
                        item[clave] = float(row[campos[clave]] or 0)
                    except ValueError:
                        item[clave] = 0.0
            filas.append(item)
        return filas


def _valor_tipico_hora(fila: dict, servicio: str) -> float:
    if "CONSUMO_REAL_TIPICO" in fila:
        return float(fila["CONSUMO_REAL_TIPICO"])
    if servicio == "bidireccional" and all(
        k in fila for k in ("CONSUMO_TIPICO", "ENTREGA_TIPICA", "GENERACION_TIPICA")
    ):
        return (
            fila["CONSUMO_TIPICO"]
            + fila["GENERACION_TIPICA"]
            - fila["ENTREGA_TIPICA"]
        )
    return float(fila.get("CONSUMO_TIPICO", 0.0))


def _titulo_tipico(servicio: str) -> str:
    if servicio == "generacion":
        return "Generación típica (Consumo Real)"
    if servicio == "neteo":
        return "Neteo típico (REC − ENT)"
    return "Consumo Real típico"


def _mostrar_graficas_perfil_tipico(perfil: Path, servicio: str) -> None:
    """Una gráfica de líneas: Consumo Real típico por hora (Lunes→Domingo)."""
    import plotly.graph_objects as go

    if not perfil.exists():
        return
    filas = _leer_perfil_tipico(perfil)
    if not filas:
        return

    por_dia: dict[str, dict[int, float]] = {d: {} for d in DIAS_SEMANA}
    for fila in filas:
        dia = fila["DIA_SEMANA"]
        dia_norm = (
            dia.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
        )
        if dia_norm not in por_dia:
            continue
        por_dia[dia_norm][fila["HORA"]] = _valor_tipico_hora(fila, servicio)

    etiqueta = _titulo_tipico(servicio)
    horas = list(range(24))
    fig = go.Figure()
    for dia in DIAS_SEMANA:
        valores = [por_dia[dia].get(h, 0.0) for h in horas]
        color = COLORES_DIA.get(dia, COLORES["primary"])
        fig.add_trace(
            go.Scatter(
                x=horas,
                y=valores,
                mode="lines+markers",
                name=dia,
                line=dict(color=color, width=2.5),
                marker=dict(size=6),
                hovertemplate=(
                    f"<b>{dia}</b> · Hora %{{x}}:00<br>"
                    "Consumo Real: <b>%{y:,.3f} kWh</b>"
                    "<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title=dict(
            text=f"{etiqueta} por hora (7 días)",
            font=dict(size=16, color=COLORES["text"]),
        ),
        xaxis_title="Hora",
        yaxis_title="kWh",
        margin=dict(l=40, r=20, t=50, b=90),
        height=480,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
            itemclick=False,
            itemdoubleclick=False,
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(
            tickmode="linear",
            dtick=1,
            range=[-0.5, 23.5],
            showgrid=False,
        ),
        yaxis=dict(showgrid=True, gridcolor="#e2e8f0", zeroline=False),
        hoverlabel=dict(bgcolor="white", font_size=13),
        hovermode="x unified",
    )
    with st.container(border=True):
        st.markdown(
            '<p class="section-title" style="border:none;padding:0;margin:0 0 8px 0;">'
            f"{etiqueta} por hora</p>",
            unsafe_allow_html=True,
        )
        _plotly_chart(fig)


def _mostrar_resumen(resumen: dict, desglose: bool = True) -> None:
    # Periodos Base/Intermedio/Punta siempre visibles en tarifas horarias;
    # el desglose completo controla Neteo/Real/precios, no el detalle horario.
    horaria = bool(resumen["horaria"])
    with st.container(border=True):
        st.markdown(
            '<p class="section-title" style="border:none;padding:0;margin:0 0 8px 0;">'
            "Resumen de energía</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="fecha-resumen">'
            f'Periodo: <strong>{resumen["fecha_min"]}</strong> → '
            f'<strong>{resumen["fecha_max"]}</strong> '
            f'({resumen["n_dias"]} días) · Tarifa <strong>{resumen["esquema"]}</strong>'
            f"</div>",
            unsafe_allow_html=True,
        )

        if resumen.get("layout") == "neteo":
            renglones = resumen["columnas"]["flujos"]["renglones"]
            entregada, recibida, neteo_r = renglones
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    _html_metric_card(
                        "Energía Entregada",
                        entregada["valores"],
                        COLORES["primary"],
                        horaria,
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    _html_metric_card(
                        "Energía Recibida",
                        recibida["valores"],
                        COLORES["secondary"],
                        horaria,
                    ),
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    _html_metric_card(
                        "Neteo",
                        neteo_r["valores"],
                        COLORES["warning"],
                        horaria,
                    ),
                    unsafe_allow_html=True,
                )
            if desglose and resumen.get("ahorro_energia"):
                _mostrar_ahorro(resumen["ahorro_energia"])
        elif resumen.get("layout") == "bidireccional_3col":
            cf = resumen["columnas"]["consumo_facturado"]
            gen = resumen["columnas"]["generacion"]
            real = resumen["columnas"]["consumo_real"]
            entregada, recibida, neteo = cf["renglones"]
            generada = gen["renglones"][0]
            consumo_real = real["renglones"][0]

            if not desglose:
                # Vista simple: Entregada | Recibida | Generada (+ periodos si horaria)
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(
                        _html_metric_card(
                            "Energía Entregada",
                            entregada["valores"],
                            COLORES["primary"],
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )
                with c2:
                    st.markdown(
                        _html_metric_card(
                            "Energía Recibida",
                            recibida["valores"],
                            COLORES["secondary"],
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )
                with c3:
                    st.markdown(
                        _html_metric_card(
                            "Energía Generada",
                            generada["valores"],
                            COLORES["success"],
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )
            else:
                # Vista completa (desglose activo)
                t1, t2, t3 = st.columns(3)
                with t1:
                    st.markdown(
                        f'<div class="grupo-resumen-titulo">{cf["titulo"]}</div>',
                        unsafe_allow_html=True,
                    )
                with t2:
                    st.markdown(
                        f'<div class="grupo-resumen-titulo">{gen["titulo"]}</div>',
                        unsafe_allow_html=True,
                    )
                with t3:
                    st.markdown(
                        f'<div class="grupo-resumen-titulo">{real["titulo"]}</div>',
                        unsafe_allow_html=True,
                    )

                r1c1, r1c2, r1c3 = st.columns(3)
                with r1c1:
                    st.markdown(
                        _html_metric_card(
                            entregada["etiqueta"],
                            entregada["valores"],
                            COLORES["primary"],
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )

                r2c1, r2c2, r2c3 = st.columns(3)
                with r2c1:
                    st.markdown(
                        _html_metric_card(
                            recibida["etiqueta"],
                            recibida["valores"],
                            COLORES["secondary"],
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )
                with r2c2:
                    st.markdown(
                        _html_metric_card(
                            generada["etiqueta"],
                            generada["valores"],
                            COLORES["success"],
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )
                with r2c3:
                    st.markdown(
                        _html_metric_card(
                            consumo_real["etiqueta"],
                            consumo_real["valores"],
                            COLORES["danger"],
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )

                r3c1, r3c2, r3c3 = st.columns(3)
                with r3c1:
                    st.markdown(
                        _html_metric_card(
                            neteo["etiqueta"],
                            neteo["valores"],
                            COLORES["warning"],
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )
                if resumen.get("ahorro_energia"):
                    _mostrar_ahorro(resumen["ahorro_energia"])
        else:
            colores = {
                "REC": COLORES["primary"]
                if resumen["servicio"] != "generacion"
                else COLORES["success"]
            }
            n = len(resumen["flujos"])
            cols = st.columns(n)
            for col_ui, (clave, bloque) in zip(cols, resumen["flujos"].items()):
                with col_ui:
                    titulo = resumen["etiquetas"].get(clave, clave)
                    st.markdown(
                        _html_metric_card(
                            titulo,
                            bloque,
                            colores.get(clave, COLORES["primary"]),
                            horaria,
                        ),
                        unsafe_allow_html=True,
                    )
            if desglose and resumen.get("costo_energia"):
                _mostrar_costo(resumen["costo_energia"])

        if resumen.get("aportaciones"):
            _mostrar_aportaciones(resumen["aportaciones"])


def _mostrar_aportaciones(aportaciones: dict) -> None:
    """Detalle de aportación por medidor cuando hay varios perfiles en un lado."""
    bloques = [b for b in aportaciones.values() if b.get("medidores")]
    if not bloques:
        return
    st.markdown(
        '<p class="section-title" style="border:none;padding:12px 0 8px 0;">'
        "Aportación por medidor</p>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Participación de cada perfil en el total del periodo "
        "(tras multiplicadores / canales invertidos y filtro de fechas, si aplica)."
    )
    for bloque in bloques:
        meds = bloque["medidores"]
        total = sum(float(m["kwh"]) for m in meds)
        st.markdown(f"**{bloque['titulo']}** · total {total:,.1f} kWh")
        filas_html = []
        for m in meds:
            filas_html.append(
                "<div style='display:flex;justify-content:space-between;"
                "gap:12px;padding:4px 0;border-bottom:1px solid #e2e8f0;'>"
                f"<span>{m['nombre']}</span>"
                f"<span><strong>{m['kwh']:,.1f} kWh</strong> "
                f"({m['pct']:.1f}%)</span>"
                "</div>"
            )
        st.markdown(
            f"<div style='margin:0 0 12px 0;'>{''.join(filas_html)}</div>",
            unsafe_allow_html=True,
        )


def run_pages(*, desde_suite: bool = False) -> None:
    from bess.ui.auth import init_session, preparar_ui_login, restaurar_ui_app
    from bess.ui.styles import aplicar_estilos_login

    init_session()

    if st.session_state.pop("_logout_pendiente", False):
        from bess.ui.auth import logout

        logout()
        st.rerun()

    if not desde_suite and not st.session_state.get("autenticado"):
        preparar_ui_login()
        aplicar_estilos_login()
        _login_analisis()
        if not st.session_state.get("autenticado"):
            return
        st.rerun()
    elif desde_suite and not st.session_state.get("autenticado"):
        return

    restaurar_ui_app(restaurar_sidebar=False)
    # Evita que el script de expansión de BESS deje la guía BESS colgada.
    st.session_state.pop("sidebar_inicial_aplicada", None)
    aplicar_estilos()
    _render_sidebar_analisis()
    _render_barra_sesion()
    render_header(
        NOMBRE_APP,
        f"App hermana de la suite IUSASOL · v{VERSION}",
    )
    reset = int(st.session_state.get("ui_reset") or 0)
    msg = st.session_state.pop("limpiar_flash", None)
    if msg:
        st.success(msg)
    _run_analisis(reset)


def _render_sidebar_analisis() -> None:
    """Barra propia del módulo (sustituye restos de BESS al cambiar en la Suite)."""
    from bess.config.users import ETIQUETA_ROL
    from bess.ui.components import html_creditos_plataforma, obtener_logo_html

    with st.sidebar:
        logo_html = obtener_logo_html(220)
        logo_block = (
            f'<div style="background:white;border-radius:8px;padding:6px 10px;'
            f'display:inline-block;margin-bottom:8px;">{logo_html}</div>'
            if logo_html
            else f'<h2 style="color:white;margin:0;font-size:18px;">{NOMBRE_APP}</h2>'
        )
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,#1a5276,#2e86c1);
                        padding:16px;border-radius:12px;text-align:center;margin-bottom:8px;">
                {logo_block}
                <p style="color:rgba(255,255,255,0.9);margin:4px 0 0;font-size:12px;font-weight:500;">
                    Análisis de Perfil · Panel local
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        usuario = st.session_state.get("usuario") or "—"
        rol = st.session_state.get("rol") or ""
        st.markdown(f"**{usuario}**")
        st.caption(f"Rol: {ETIQUETA_ROL.get(rol, rol)}")
        st.divider()
        st.markdown("### Este módulo")
        st.caption(
            "Procesa perfiles CSV (consumo / generación / bidireccional / neteo) "
            "con tarifas T01, GDMTH o DIST. Controles en el área principal."
        )
        with st.expander("Flujo rápido", expanded=False):
            st.markdown(
                "1. Elija **tarifa** y **servicio**\n"
                "2. Cargue CSV/ZIP o descargue de la **API**\n"
                "3. (Opcional) filtre el intervalo de fechas\n"
                "4. Genere reportes y revise resumen / gráficas"
            )
        st.markdown(html_creditos_plataforma(variante="sidebar"), unsafe_allow_html=True)


def _render_barra_sesion() -> None:
    from bess.config.users import ETIQUETA_ROL
    from bess.ui.components import (
        boton_cerrar_sesion,
        boton_volver_suite,
        en_suite,
        marcar_barra_sesion,
    )

    usuario = st.session_state.get("usuario") or "—"
    rol = st.session_state.get("rol") or ""
    etiqueta = ETIQUETA_ROL.get(rol, rol)
    n_btn = 1 + (1 if en_suite() else 0)
    cols = st.columns([4, *[1] * n_btn])
    with cols[0]:
        marcar_barra_sesion()
        st.caption(f"Sesión: **{usuario}** · {etiqueta}")
    idx = 1
    if en_suite():
        with cols[idx]:
            boton_volver_suite(key="analisis_hdr_volver_suite")
        idx += 1
    with cols[idx]:
        boton_cerrar_sesion(key="analisis_hdr_logout")


def _login_analisis() -> None:
    """Login con branding del módulo (mismos usuarios que BESS/Granja)."""
    from bess.config.users import verificar_password
    from bess.ui.auth import get_usuarios
    from bess.ui.components import obtener_logo_html

    st.markdown('<div class="login-page-marker"></div>', unsafe_allow_html=True)
    try:
        usuarios = get_usuarios()
    except (RuntimeError, ValueError) as exc:
        _, col, _ = st.columns([3, 4, 3])
        with col:
            st.error(str(exc))
        return

    _, col, _ = st.columns([3, 4, 3])
    with col:
        logo_html = obtener_logo_html(288)
        logo_block = (
            f'<div class="login-logo-wrap">'
            f'<div style="background:white;border-radius:10px;padding:8px 14px;'
            f'box-shadow:0 1px 4px rgba(0,0,0,0.04);">{logo_html}</div></div>'
            if logo_html
            else ""
        )
        st.markdown(
            f"""
            <div class="login-brand">
                {logo_block}
                <h1 class="login-title">{NOMBRE_APP}</h1>
                <p class="login-subtitle">Perfiles · tarifas T01 / GDMTH / DIST</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            with st.form("login_analisis_perfil"):
                usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
                password = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="Ingresa tu contraseña",
                )
                enviar = st.form_submit_button(
                    "Iniciar sesión", type="primary", use_container_width=True
                )
            if enviar:
                u = (usuario or "").strip()
                if not u or not password:
                    st.error("Usuario y contraseña son obligatorios.")
                elif u not in usuarios or not verificar_password(
                    password, usuarios[u]["password"]
                ):
                    st.error("Usuario o contraseña incorrectos.")
                elif not usuarios[u].get("activo", True):
                    st.error("Usuario inactivo.")
                else:
                    st.session_state.autenticado = True
                    st.session_state.usuario = u
                    st.session_state.rol = usuarios[u].get("rol", "user")
                    st.rerun()



def _run_analisis(reset: int) -> None:
    """Flujo en 3 pasos: Preparar → Perfiles → Resultados."""
    tiene_resultados = bool(st.session_state.get("ultimo_job"))
    opciones_paso = ["Preparar", "Perfiles", "Resultados"]
    if "analisis_paso" not in st.session_state:
        st.session_state["analisis_paso"] = (
            "Resultados" if tiene_resultados else "Preparar"
        )
    if st.session_state["analisis_paso"] not in opciones_paso:
        st.session_state["analisis_paso"] = "Preparar"

    st.markdown('<div class="analisis-wizard">', unsafe_allow_html=True)
    paso = st.radio(
        "Paso",
        opciones_paso,
        horizontal=True,
        key="analisis_paso",
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if paso == "Preparar":
        tarifa_sel, servicio_sel, region_sel, desglose_sel = _ui_paso_preparar(
            reset
        )
        st.session_state["_ap_cfg"] = {
            "tarifa": tarifa_sel,
            "servicio": servicio_sel,
            "region": region_sel,
            "desglose": desglose_sel,
            "reset": reset,
        }
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button(
                "Continuar a Perfiles →",
                type="primary",
                use_container_width=True,
                key=f"btn_ir_perfiles_{reset}",
            ):
                st.session_state["analisis_paso"] = "Perfiles"
                st.rerun()
        with c2:
            if st.button(
                "Limpiar sesión",
                use_container_width=True,
                key=f"btn_limpiar_prep_{reset}",
            ):
                _limpiar_todo()
                st.rerun()
        return

    if paso == "Resultados":
        cfg = st.session_state.get("_ap_cfg") or {}
        desglose_sel = bool(cfg.get("desglose", True))
        if f"desglose_{reset}" in st.session_state:
            desglose_sel = bool(st.session_state[f"desglose_{reset}"])
        _ui_paso_resultados(reset, desglose_sel=desglose_sel)
        return

    # Perfiles
    cfg = st.session_state.get("_ap_cfg") or {}
    if cfg.get("reset") != reset or "tarifa" not in cfg:
        st.session_state["analisis_paso"] = "Preparar"
        st.info("Configure tarifa y servicio en **Preparar**.")
        if st.button("Ir a Preparar", key=f"btn_force_prep_{reset}"):
            st.rerun()
        return

    _ui_paso_perfiles(
        reset,
        tarifa_sel=cfg["tarifa"],
        servicio_sel=cfg["servicio"],
        region_sel=cfg.get("region"),
    )


def _ui_paso_preparar(reset: int) -> tuple:
    render_section_title("Preparar análisis", first=True)
    st.markdown(
        '<p class="section-desc">Tarifa, servicio y opciones de vista.</p>',
        unsafe_allow_html=True,
    )

    c_tarifa, c_servicio = st.columns(2)
    with c_tarifa:
        tarifa_sel = st.selectbox(
            "Tarifa",
            options=list(TARIFAS.keys()),
            format_func=lambda k: f"{k} — {TARIFAS[k]['etiqueta']}",
            index=0,
            key=f"tarifa_{reset}",
        )
    with c_servicio:
        servicio_sel = st.selectbox(
            "Servicio",
            options=list(SERVICIOS.keys()),
            format_func=lambda k: SERVICIOS[k]["etiqueta"],
            index=0,
            key=f"servicio_{reset}",
        )

    region_sel = None
    clave_tarifa = TARIFAS[tarifa_sel]["clave"]
    if clave_tarifa in ("DIST", "GDMTH"):
        default_reg = REGION_POR_TARIFA.get(clave_tarifa, DIVISIONES[0])
        idx = DIVISIONES.index(default_reg) if default_reg in DIVISIONES else 0
        c_reg, c_sync = st.columns([3, 1])
        with c_reg:
            region_sel = st.selectbox(
                "División / región",
                options=list(DIVISIONES),
                index=idx,
                key=f"region_{clave_tarifa}_{reset}",
            )
        with c_sync:
            st.markdown('<div class="btn-align-label"> </div>', unsafe_allow_html=True)
            if st.button(
                "Sincronizar CFE",
                use_container_width=True,
                key=f"sync_cfe_{reset}",
                help="Copia CSV DIST/GDMTH desde data/ReportesTarifasCFE",
            ):
                try:
                    from tarifas_cfe_catalog import sincronizar_desde_reporteador

                    copiados = sincronizar_desde_reporteador()
                    st.success(f"Sincronizados {len(copiados)} archivo(s).")
                except Exception as exc:
                    st.error(f"No se pudo sincronizar: {exc}")

    c_desg, c_help = st.columns([2, 2])
    with c_desg:
        desglose_sel = st.checkbox(
            "Mostrar desglose completo (periodos / precios)",
            value=True,
            key=f"desglose_{reset}",
        )
    with c_help:
        with st.expander("Ayuda", expanded=False):
            st.markdown(
                f"**Servicio:** {SERVICIOS[servicio_sel]['desc']}\n\n"
                "- **Origen**: CSV/ZIP o API.\n"
                "- **Bidireccional**: consumo y generación por separado.\n"
                "- **Neteo**: un medidor REC + ENT.\n"
                "- **Multiplicadores / canales**: en Perfiles → avanzadas.\n"
                "- **Limpiar**: reinicia opciones y borra CSV no descargados."
            )

    return tarifa_sel, servicio_sel, region_sel, desglose_sel


def _ui_paso_perfiles(
    reset: int,
    *,
    tarifa_sel: int,
    servicio_sel: str,
    region_sel: str | None,
) -> None:
    render_section_title("Perfiles", first=True)
    st.markdown(
        f'<p class="section-desc">'
        f"<strong>{TARIFAS[tarifa_sel]['etiqueta']}</strong> · "
        f"<strong>{SERVICIOS[servicio_sel]['etiqueta']}</strong>"
        + (f" · {region_sel}" if region_sel else "")
        + "</p>",
        unsafe_allow_html=True,
    )

    uploaded = None
    uploaded_consumo = None
    uploaded_generacion = None
    api_files = None
    api_consumo = None
    api_generacion = None
    listo_archivos = False

    if servicio_sel == "bidireccional":
        st.caption(
            "Cada lado: archivo o API. Con API, un solo rango y un botón para ambos."
        )
        from analisis_perfil.ui.descargas_bridge import render_descarga_bidireccional

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Consumo")
            origen_c = st.radio(
                "Origen consumo",
                ["Subir archivo", "Descargar de API"],
                horizontal=True,
                key=f"origen_c_{reset}",
                label_visibility="collapsed",
            )
            if origen_c == "Subir archivo":
                uploaded_consumo = st.file_uploader(
                    "CSV/ZIP consumo",
                    type=["csv", "zip"],
                    accept_multiple_files=True,
                    key=f"up_c_{reset}",
                )
            else:
                st.caption("API compartida abajo.")
        with c2:
            st.markdown("##### Generación")
            origen_g = st.radio(
                "Origen generación",
                ["Subir archivo", "Descargar de API"],
                horizontal=True,
                key=f"origen_g_{reset}",
                label_visibility="collapsed",
            )
            if origen_g == "Subir archivo":
                uploaded_generacion = st.file_uploader(
                    "CSV/ZIP generación",
                    type=["csv", "zip"],
                    accept_multiple_files=True,
                    key=f"up_g_{reset}",
                )
            else:
                st.caption("API compartida abajo.")

        usa_api_c = origen_c == "Descargar de API"
        usa_api_g = origen_g == "Descargar de API"
        if usa_api_c or usa_api_g:
            api_consumo, api_generacion = render_descarga_bidireccional(
                reset=reset,
                incluir_consumo=usa_api_c,
                incluir_generacion=usa_api_g,
            )
            if not usa_api_c:
                api_consumo = None
            if not usa_api_g:
                api_generacion = None

        tiene_c = bool(uploaded_consumo) or bool(api_consumo)
        tiene_g = bool(uploaded_generacion) or bool(api_generacion)
        listo_archivos = tiene_c and tiene_g
        if tiene_c or tiene_g:
            n_c = len(uploaded_consumo or api_consumo or [])
            n_g = len(uploaded_generacion or api_generacion or [])
            st.markdown(
                f'<div class="metric-chip">Consumo: <strong>{n_c}</strong> · '
                f"Generación: <strong>{n_g}</strong></div>",
                unsafe_allow_html=True,
            )
    else:
        if servicio_sel == "neteo":
            st.caption("Neteo: KWH_REC y KWH_ENT en el mismo medidor (REC − ENT).")
        else:
            col_txt = "KWH_REC" if servicio_sel == "consumo" else "KWH_ENT"
            st.caption(
                f"{SERVICIOS[servicio_sel]['etiqueta']}: columna {col_txt}. "
                "Varios medidores se suman por FECHA."
            )
        origen = st.radio(
            "Origen",
            ["Subir archivo", "Descargar de API"],
            horizontal=True,
            key=f"origen_{servicio_sel}_{reset}",
        )
        if origen == "Subir archivo":
            uploaded = st.file_uploader(
                "CSV o ZIP",
                type=["csv", "zip"],
                accept_multiple_files=True,
                key=f"up_multi_{servicio_sel}_{reset}",
            )
            listo_archivos = bool(uploaded)
            if uploaded:
                nombres = ", ".join(u.name for u in uploaded)
                st.markdown(
                    f'<div class="metric-chip"><strong>{len(uploaded)}</strong> '
                    f"archivo(s): {nombres}</div>",
                    unsafe_allow_html=True,
                )
        else:
            from analisis_perfil.ui.descargas_bridge import render_descarga_en_flujo

            api_files = render_descarga_en_flujo(
                session_key="api_perfiles",
                reset=reset,
                titulo="Descargar perfiles",
            )
            listo_archivos = bool(api_files)

    factores: list[float] = []
    factores_c: list[float] = []
    factores_g: list[float] = []
    invertir: list[bool] = []
    invertir_c: list[bool] = []
    invertir_g: list[bool] = []

    with st.expander("Opciones avanzadas (multiplicadores y canales)", expanded=False):
        if not listo_archivos:
            st.caption("Cargue perfiles para configurar factores por archivo.")
        elif servicio_sel == "bidireccional":
            fuentes_c_ui = uploaded_consumo or api_consumo or []
            fuentes_g_ui = uploaded_generacion or api_generacion or []
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                factores_c, invertir_c = _ui_opciones_perfil(
                    fuentes_c_ui,
                    key_prefix=f"bidi_c_{servicio_sel}",
                    reset=reset,
                    titulo="Consumo",
                )
            with c_m2:
                factores_g, invertir_g = _ui_opciones_perfil(
                    fuentes_g_ui,
                    key_prefix=f"bidi_g_{servicio_sel}",
                    reset=reset,
                    titulo="Generación",
                )
        else:
            fuentes_ui = uploaded or api_files or []
            factores, invertir = _ui_opciones_perfil(
                fuentes_ui,
                key_prefix=servicio_sel,
                reset=reset,
                titulo="Perfiles",
            )

    fecha_desde = fecha_hasta = None
    usar_rango = False
    with st.expander("Filtrar intervalo de fechas (opcional)", expanded=False):
        fuentes_rango = _fuentes_para_rango(
            servicio_sel,
            uploaded=uploaded,
            uploaded_consumo=uploaded_consumo,
            uploaded_generacion=uploaded_generacion,
            api_files=api_files,
            api_consumo=api_consumo,
            api_generacion=api_generacion,
        )
        rango_perfil = (
            _rango_detectado_fuentes(fuentes_rango) if listo_archivos else None
        )
        if rango_perfil:
            st.caption(f"Detectado: {rango_perfil[0]} → {rango_perfil[1]}")
        usar_rango = st.checkbox(
            "Analizar solo un subintervalo",
            value=False,
            key=f"usar_rango_{reset}",
        )
        if usar_rango:
            c_d, c_h = st.columns(2)
            kwargs_d: dict = {"format": "DD/MM/YYYY", "key": f"fecha_desde_{reset}"}
            kwargs_h: dict = {"format": "DD/MM/YYYY", "key": f"fecha_hasta_{reset}"}
            if rango_perfil:
                d0, d1 = rango_perfil
                kwargs_d["value"] = d0
                kwargs_h["value"] = d1
            with c_d:
                fecha_desde = st.date_input("Desde", **kwargs_d)
            with c_h:
                fecha_hasta = st.date_input("Hasta", **kwargs_h)
            if fecha_hasta < fecha_desde:
                st.error("La fecha fin debe ser ≥ fecha inicio.")
                return

    st.divider()
    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        lanzar = st.button(
            "Generar reportes",
            type="primary",
            use_container_width=True,
            disabled=not listo_archivos,
            key=f"btn_generar_{reset}",
        )
    with col_b:
        if st.button(
            "Limpiar",
            use_container_width=True,
            key=f"btn_limpiar_{reset}",
        ):
            _limpiar_todo()
            st.rerun()
    with col_c:
        if not listo_archivos:
            st.info("Indique origen y perfiles para continuar.")
        elif st.session_state.get("ultimo_job"):
            if st.button(
                "Ver resultados →",
                use_container_width=True,
                key=f"btn_ver_res_{reset}",
            ):
                st.session_state["analisis_paso"] = "Resultados"
                st.rerun()

    if not (lanzar and listo_archivos):
        return

    job = _job_dir()
    with st.status("Procesando perfil…", expanded=True) as status:
        st.write(f"Carpeta de trabajo: `{job.name}`")
        try:
            if servicio_sel == "bidireccional":
                fuentes_c = uploaded_consumo or api_consumo or []
                fuentes_g = uploaded_generacion or api_generacion or []
                consumos, facs_c, invs_c = _guardar_uploads_con_opciones(
                    fuentes_c, job, factores_c, invertir_c
                )
                generaciones, facs_g, invs_g = _guardar_uploads_con_opciones(
                    fuentes_g, job, factores_g, invertir_g
                )
                st.write(
                    f"Consumo: {len(consumos)} · Generación: {len(generaciones)}"
                )
                codigo = TARIFAS[tarifa_sel]["codigo"]
                _job, resumen, perfil_usado = _ejecutar_pipeline(
                    consumos,
                    codigo,
                    servicio_sel,
                    archivos_generacion=generaciones,
                    region=region_sel,
                    fecha_desde=fecha_desde if usar_rango else None,
                    fecha_hasta=fecha_hasta if usar_rango else None,
                )
            else:
                fuentes = uploaded or api_files or []
                perfiles, facs, invs = _guardar_uploads_con_opciones(
                    fuentes, job, factores, invertir
                )
                st.write(f"Perfiles listos: {len(perfiles)}")
                codigo = TARIFAS[tarifa_sel]["codigo"]
                _job, resumen, perfil_usado = _ejecutar_pipeline(
                    perfiles,
                    codigo,
                    servicio_sel,
                    region=region_sel,
                    fecha_desde=fecha_desde if usar_rango else None,
                    fecha_hasta=fecha_hasta if usar_rango else None,
                )
            status.update(label="Proceso completado", state="complete")
            st.session_state["ultimo_job"] = str(job)
            st.session_state["ultimo_esquema"] = TARIFAS[tarifa_sel]["clave"]
            st.session_state["ultimo_servicio"] = servicio_sel
            st.session_state["ultimo_resumen"] = resumen
            st.session_state["ultimo_perfil"] = str(perfil_usado)
            st.session_state["analisis_paso"] = "Resultados"
            st.rerun()
        except Exception as exc:
            status.update(label="Error en el proceso", state="error")
            st.exception(exc)


def _ui_paso_resultados(reset: int, *, desglose_sel: bool) -> None:
    job_path = st.session_state.get("ultimo_job")
    if not job_path:
        render_section_title("Resultados", first=True)
        st.info("Aún no hay reportes. Genere en el paso **Perfiles**.")
        if st.button("← Ir a Perfiles", key=f"btn_back_perf_{reset}"):
            st.session_state["analisis_paso"] = "Perfiles"
            st.rerun()
        return

    job = Path(job_path)
    if not job.exists():
        st.warning("La carpeta de trabajo ya no existe. Vuelva a generar.")
        return

    esquema = st.session_state.get("ultimo_esquema", "DIST")
    servicio = st.session_state.get("ultimo_servicio", "consumo")
    resumen = st.session_state.get("ultimo_resumen")
    grupos = _listar_salidas(job, esquema)
    todos = [p for lista in grupos.values() for p in lista]

    render_section_title("Resultados", first=True)
    st.markdown(
        f'<p class="section-desc"><code>{job.name}</code> · '
        f"<strong>{esquema}</strong> · <strong>{servicio}</strong> · "
        f"{len(todos)} archivo(s)</p>",
        unsafe_allow_html=True,
    )

    tab_res, tab_graf, tab_arch, tab_dl = st.tabs(
        ["Resumen", "Gráficas", "Archivos", "Descargas"]
    )

    perfil_ref = st.session_state.get("ultimo_perfil")
    perfil_path = Path(perfil_ref) if perfil_ref else None

    with tab_res:
        if resumen:
            _mostrar_resumen(resumen, desglose=desglose_sel)
        else:
            st.caption("Sin resumen en sesión.")
        if perfil_path and perfil_path.is_file():
            _mostrar_calidad(perfil_path, servicio)
            _mostrar_demanda_pico(perfil_path, servicio)

    with tab_graf:
        if grupos.get("diario"):
            _mostrar_graficas_energia_diaria(
                grupos["diario"][0],
                servicio,
                perfil=perfil_path,
            )
        if grupos.get("perfil_hora"):
            _mostrar_graficas_perfil_tipico(grupos["perfil_hora"][0], servicio)
        graficas = grupos.get("graficas") or []
        if graficas:
            st.markdown("##### PNG generados")
            comparativa = [p for p in graficas if "comparativa" in p.name.lower()]
            dias = [p for p in graficas if p not in comparativa]
            if comparativa:
                for p in comparativa:
                    st.image(str(p), use_container_width=True)
            if dias:
                cols = st.columns(2)
                for i, p in enumerate(dias):
                    with cols[i % 2]:
                        st.caption(p.stem.replace("perfil_", "").title())
                        st.image(str(p), use_container_width=True)
        elif not grupos.get("diario") and not grupos.get("perfil_hora"):
            st.caption("No hay gráficas en este trabajo.")

    with tab_arch:
        t1, t2, t3 = st.tabs(["Diario / Mensual", "Típicos", "Por hora"])
        with t1:
            st.markdown("**Energía por día**")
            _botones_descarga(grupos["diario"])
            st.markdown("**Energía por mes**")
            _botones_descarga(grupos["mensual"])
            if grupos["suma"]:
                st.markdown("**Perfil sumado**")
                _botones_descarga(grupos["suma"])
        with t2:
            st.markdown("**Consumo típico por día de la semana**")
            _botones_descarga(grupos["tipico_semana"])
            st.markdown("**Perfil típico día × hora**")
            _botones_descarga(grupos["perfil_hora"])
        with t3:
            st.markdown("**Energía por hora**")
            _botones_descarga(grupos["por_hora"])

    with tab_dl:
        if todos:
            rutas_zip = [
                str(p.resolve()) for p in todos if p.suffix.lower() == ".csv"
            ]
            st.download_button(
                "Descargar todo (ZIP)",
                data=_zip_bytes(todos, job),
                file_name=f"reportes_{job.name}.zip",
                mime="application/zip",
                type="primary",
                key=f"dl_zip_{job.name}_{reset}",
                on_click=_marcar_descargados,
                args=(rutas_zip,),
            )
        if resumen:
            try:
                from export_recibo_csv import generar_csv_recibo

                csv_recibo = generar_csv_recibo(resumen)
                st.download_button(
                    "CSV recibo-ready",
                    data=csv_recibo,
                    file_name=f"recibo_{job.name}.csv",
                    mime="text/csv",
                    key=f"dl_recibo_{job.name}_{reset}",
                )
            except Exception as exc:
                st.caption(f"CSV recibo no disponible: {exc}")
        if resumen and grupos.get("diario"):
            try:
                from reporte_pdf_analisis import generar_pdf_analisis

                pdf_key = (
                    f"{job.name}|{servicio}|{esquema}|{int(bool(desglose_sel))}"
                )
                if st.session_state.get("_pdf_cache_key") != pdf_key:
                    st.session_state["_pdf_cache_bytes"] = generar_pdf_analisis(
                        resumen=resumen,
                        diario=grupos["diario"][0],
                        servicio=servicio,
                        esquema=esquema,
                        graficas_tipico=grupos.get("graficas") or [],
                        desglose=desglose_sel,
                    )
                    st.session_state["_pdf_cache_key"] = pdf_key
                st.download_button(
                    "Reporte PDF",
                    data=st.session_state["_pdf_cache_bytes"],
                    file_name=f"reporte_analisis_{job.name}.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_{job.name}_{reset}",
                )
            except Exception as exc:
                st.warning(f"No se pudo armar el PDF: {exc}")

    if perfil_path and perfil_path.is_file():
        _abrir_dialog_dia_si_pendiente(perfil_path)
