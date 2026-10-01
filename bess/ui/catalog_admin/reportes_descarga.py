"""Listado y descarga de reportes generados (ArchivosReporte y PDF diarios).

La app lee los archivos en el servidor. No hace falta SFTP ni WinSCP.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bess.config.paths import DIRECTORIO_REPORTES, DIRECTORIO_REPORTES_DIARIOS

_EXTENSIONES = {".csv", ".pdf"}
_ORIGENES = (
    ("Reportes CSV", DIRECTORIO_REPORTES),
    ("PDF diarios", DIRECTORIO_REPORTES_DIARIOS),
)


@dataclass(frozen=True)
class ReporteDescarga:
    origen: str
    subestacion: str
    nombre: str
    ruta: Path
    tamano: int
    modificado: datetime

    @property
    def etiqueta(self) -> str:
        return f"{self.subestacion} / {self.nombre} ({fmt_tamano(self.tamano)})"


def fmt_tamano(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def _raices(
    raices: tuple[tuple[str, Path], ...] | None,
) -> tuple[tuple[str, Path], ...]:
    return raices if raices is not None else _ORIGENES


def _dentro_de_raiz(ruta: Path, raiz: Path) -> bool:
    try:
        ruta.resolve().relative_to(raiz.resolve())
    except ValueError:
        return False
    return True


def _nombre_descartado(path: Path) -> bool:
    nombre = path.name
    return (
        nombre.startswith(".")
        or nombre.endswith(".part")
        or path.suffix.lower() not in _EXTENSIONES
    )


def listar_reportes(
    raices: tuple[tuple[str, Path], ...] | None = None,
) -> list[ReporteDescarga]:
    """Archivos CSV/PDF bajo las carpetas de reportes, del más reciente al más viejo."""
    encontrados: list[ReporteDescarga] = []
    for origen, raiz in _raices(raices):
        if not raiz.is_dir():
            continue
        raiz_res = raiz.resolve()
        for path in raiz.rglob("*"):
            if not path.is_file() or _nombre_descartado(path):
                continue
            if not _dentro_de_raiz(path, raiz_res):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            rel = path.resolve().relative_to(raiz_res)
            subestacion = rel.parts[0] if len(rel.parts) > 1 else "—"
            encontrados.append(
                ReporteDescarga(
                    origen=origen,
                    subestacion=subestacion,
                    nombre=path.name,
                    ruta=path.resolve(),
                    tamano=stat.st_size,
                    modificado=datetime.fromtimestamp(stat.st_mtime),
                )
            )
    encontrados.sort(key=lambda r: r.modificado, reverse=True)
    return encontrados


def leer_reporte(
    ruta: Path,
    raices: tuple[tuple[str, Path], ...] | None = None,
) -> bytes:
    """Lee un reporte solo si queda dentro de las carpetas permitidas."""
    objetivo = ruta.resolve()
    if not objetivo.is_file() or _nombre_descartado(objetivo):
        raise ValueError("El archivo no es un reporte descargable.")
    if not any(_dentro_de_raiz(objetivo, raiz) for _, raiz in _raices(raices) if raiz.is_dir()):
        raise ValueError("La ruta queda fuera de los reportes del servidor.")
    return objetivo.read_bytes()


def mime_reporte(nombre: str) -> str:
    if nombre.lower().endswith(".pdf"):
        return "application/pdf"
    return "text/csv"


def render_tab() -> None:
    """Pestaña de Catálogo: elegir un reporte y descargarlo."""
    import pandas as pd
    import streamlit as st

    st.markdown("##### Descargar reportes")
    st.caption(
        "Los CSV y PDF se leen en el servidor (ArchivosReporte y ReportesDiarios). "
        "No hace falta otra herramienta para bajarlos."
    )

    archivos = listar_reportes()
    if not archivos:
        st.info("No hay reportes generados en el servidor.")
        return

    origenes = ["Todos", *dict.fromkeys(a.origen for a in archivos)]
    subs = ["Todas", *sorted({a.subestacion for a in archivos})]
    c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
    with c1:
        origen = st.selectbox("Carpeta", origenes, key="cat_rep_origen")
    with c2:
        sub = st.selectbox("Subestación", subs, key="cat_rep_sub")
    with c3:
        texto = st.text_input("Nombre contiene", key="cat_rep_texto")

    texto_l = texto.strip().lower()
    visibles = [
        a
        for a in archivos
        if (origen == "Todos" or a.origen == origen)
        and (sub == "Todas" or a.subestacion == sub)
        and (not texto_l or texto_l in a.nombre.lower())
    ]
    if not visibles:
        st.warning("Ningún archivo coincide con el filtro.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Carpeta": a.origen,
                    "Subestación": a.subestacion,
                    "Archivo": a.nombre,
                    "Tamaño": fmt_tamano(a.tamano),
                    "Modificado": a.modificado.strftime("%d/%m/%Y %H:%M"),
                }
                for a in visibles
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )

    etiquetas = {a.etiqueta: a for a in visibles}
    elegida = st.selectbox("Archivo", list(etiquetas), key="cat_rep_archivo")
    reporte = etiquetas[elegida]
    st.caption(str(reporte.ruta))

    if st.button("Preparar descarga", type="primary", key="cat_rep_prep"):
        try:
            datos = leer_reporte(reporte.ruta)
        except (OSError, ValueError) as exc:
            st.error(f"No se pudo leer el archivo: {exc}")
        else:
            st.session_state["cat_rep_clave"] = str(reporte.ruta)
            st.session_state["cat_rep_bytes"] = datos
            st.session_state["cat_rep_nombre"] = reporte.nombre

    if st.session_state.get("cat_rep_clave") == str(reporte.ruta):
        st.download_button(
            "Guardar archivo",
            data=st.session_state["cat_rep_bytes"],
            file_name=st.session_state["cat_rep_nombre"],
            mime=mime_reporte(st.session_state["cat_rep_nombre"]),
            key="cat_rep_dl",
        )
