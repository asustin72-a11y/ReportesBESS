"""
Genera GUIA_ADMINISTRADOR.pdf (pipeline, catálogo y Mantenimiento DB).

Uso:
  python docs/generar_guia_admin_pdf.py
  BESS_SKIP_CAPTURE=1 python docs/generar_guia_admin_pdf.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Spacer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bess import __version__ as VERSION
from docs.pdf_shared import (
    build_pdf,
    cover_page,
    img_block,
    p,
    section,
    table,
    toc_box,
)

DOCS = ROOT / "docs"
CAPTURAS = DOCS / "capturas"
PDF_OUT = DOCS / "GUIA_ADMINISTRADOR.pdf"
LOGO = ROOT / "data" / "Logo IUSASOL.png"
APP_URL = os.environ.get("BESS_APP_URL", "http://localhost:8501")


def _wait(page, ms=2500):
    page.wait_for_timeout(ms)


def capturar_sidebar_admin():
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        _wait(page, 3000)
        try:
            page.get_by_placeholder("Ingresa tu usuario").fill("admin")
            page.get_by_placeholder("Ingresa tu contraseña").fill("admin123")
            page.get_by_role("button", name="Iniciar Sesión").click()
            _wait(page, 5000)
        except PlaywrightTimeout as exc:
            browser.close()
            raise RuntimeError("No se pudo iniciar sesión como admin.") from exc
        page.screenshot(path=str(CAPTURAS / "08-admin-sidebar.png"), full_page=True)
        browser.close()
    print(f"Captura admin: {CAPTURAS / '08-admin-sidebar.png'}")


def _build_story() -> list:
    s: list = []
    s.extend(
        cover_page(
            LOGO,
            "Guía del administrador — Sistema BESS",
            "Pipeline de datos · Catálogo SQLite · Roles admin y superadmin",
            VERSION,
        )
    )
    s.append(PageBreak())
    s.extend(
        toc_box(
            [
                "1. Responsabilidades",
                "2. Roles y acceso",
                "3. Barra lateral",
                "4. Mantenimiento DB (superadmin)",
                "5. Subestaciones",
                "6. Reglas de negocio",
                "7. Solución de problemas",
                "8. Rutas y scripts",
            ]
        )
    )
    s.append(PageBreak())

    s.extend(section("1", "Responsabilidades"))
    s.append(
        p(
            "El administrador mantiene el pipeline: <b>1)</b> Sincronizar perfiles "
            "(ION Modbus + API BESS/generación), <b>2)</b> Verificar CSV en fuente, "
            "<b>3)</b> Filtrar intersección temporal, <b>4)</b> Generar reportes CSV "
            "para el reporteador.",
            "body",
        )
    )

    s.extend(section("2", "Roles y acceso"))
    s.append(
        table(
            [
                ["Rol", "Sidebar", "Catálogo / BD"],
                ["user", "Oculta", "No"],
                ["admin", "Pipeline completo", "No"],
                ["superadmin", "Pipeline + Catálogo + Mant. DB", "Sí"],
            ],
            [1.2 * inch, 2.5 * inch, 2.8 * inch],
        )
    )

    s.extend(section("3", "Barra lateral"))
    s.extend(img_block(CAPTURAS, "08-admin-sidebar.png", "Panel admin: Ayuda, Procesar todo, pasos", 1))
    s.append(
        table(
            [
                ["Elemento", "Función"],
                ["Ayuda", "Flujo de trabajo en 4 pasos (solo referencia)."],
                ["⚡ Procesar todo", "Verificar + Filtrar + Generar reportes en un clic."],
                ["🔧 Paso a paso", "Sync, Verificar, Filtrar y Generar por separado."],
                ["📂 Cargar archivos", "Subida manual de CSV a ArchivosFuente."],
                ["💲 Consulta — Tarifas", "Lectura del mes actual."],
                ["🏭 Catálogo", "Superadmin: subestaciones, medidores, tarifas, usuarios."],
                ["🗄️ Mantenimiento DB", "Superadmin: cursores, import/export, reconciliar, rebuild y purga."],
            ],
            [1.8 * inch, 4.7 * inch],
        )
    )
    s.append(Spacer(1, 6))
    s.append(
        p(
            "Tras sync o procesamiento exitoso aparecen <b>banners</b> en sidebar. "
            "Si no hay reportes CSV, el reporteador muestra estado vacío con CTA al pipeline.",
            "body",
        )
    )
    s.append(
        p(
            "<b>Procesar todo</b> requiere medidores validados. Si hay pendientes, "
            "ejecute <b>Sincronizar ahora</b> primero.",
            "body",
        )
    )
    s.append(
        p(
            "<b>Catálogo (superadmin):</b> Subestaciones, Tipos medidor, Medidores, "
            "Tarifas, Cliente recibo, Usuarios y Validación. Debe conservarse al "
            "menos un superadmin activo.",
            "body",
        )
    )

    s.append(PageBreak())
    s.extend(section("4", "Mantenimiento DB (solo superadmin)"))
    s.append(
        p(
            "Administra <b>data/bess_perfiles.db</b> y la cadena CSV derivada. "
            "El rol admin no tiene acceso. Antes de borrar datos, respalde la BD.",
            "body",
        )
    )
    s.append(
        table(
            [
                ["Vista", "Función"],
                ["Resumen", "Perfiles, sync_log ION/API/Granja y divergencia de cursores."],
                ["Importar", "CSV→SQLite (fuente=csv), alinea cursores; Rebuild opcional."],
                ["Exportar", "Medidor/rango o exportación masiva a ArchivosFuente."],
                ["Reconciliar", "SUM kWh/día SQLite vs Fuente; solo lectura."],
                ["Rebuild CSV", "Reexporta desde BD y regenera derivados; no toca SQLite."],
                ["Purgar", "Rango o desde fecha; vista previa y confirmación."],
                ["Avanzado", "Inicializar, migrar IDs y vaciar perfiles."],
            ],
            [1.35 * inch, 5.15 * inch],
        )
    )
    s.append(Spacer(1, 8))
    s.append(p("4.1 Importar con protección", "h2"))
    s.append(
        p(
            "Seleccione medidor, opción de faltantes y el CSV. "
            "Las filas quedan con <b>fuente=csv</b>; el sync API no pisa filas CSV "
            "con energía real aunque reciba días completos. Las filas CSV en cero "
            "sí pueden corregirse. Tras import OK se alinean sync_state y "
            "Ultima_Sincronizacion.",
            "body",
        )
    )
    s.append(p("4.2 Cursores y trazabilidad", "h2"))
    s.append(
        p(
            "Evaluar cursores compara sync_state con data/Tarifas/"
            "Ultima_Sincronizacion.csv. Alinear a BD usa MAX(fecha). sync_log "
            "registra estado, rango y conteos de ION, API ISOL y Granja.",
            "body",
        )
    )
    s.append(p("4.3 Reconciliar y Rebuild", "h2"))
    s.append(
        p(
            "Reconciliar compara por día SUM(kWh) y filas en SQLite vs Fuente "
            "(tolerancia 0.05 kWh). Si la BD está bien y Fuente/Filtrado/COMBINADO "
            "quedaron congelados, abra Rebuild desde el primer día afectado. "
            "Rebuild solo lee SQLite; reexporta Fuente, elimina CSV derivados y, "
            "opcionalmente, ejecuta Verificar → Filtrar → Reportes.",
            "body",
        )
    )
    s.append(p("4.4 Purgar y Avanzado", "h2"))
    s.append(
        p(
            "Purgar requiere vista previa y confirmación. Vaciar perfiles elimina "
            "perfil_carga y sync_state y exige escribir VACIAR; no borra catálogo, "
            "usuarios o tarifas. No existe rollback global.",
            "body",
        )
    )

    s.extend(section("5", "Subestaciones"))
    s.append(
        table(
            [
                ["Subestación", "Facturación", "BESS", "Generación"],
                ["IUSA 1", "ION + Banco 1", "BESS_NORTE", "Generación"],
                ["IUSA 2", "ION testigo", "BESS_SUR", "Granja solar"],
                ["IUSA ARAGON", "Consumo Aragón", "BESS Aragón", "Generación Aragón"],
            ],
            [1.1 * inch, 1.5 * inch, 1.3 * inch, 2.6 * inch],
        )
    )
    s.append(Spacer(1, 6))
    s.append(p("Catálogo en SQLite (`bess_catalog.db`); CSV en data/Tarifas migra si tablas vacías.", "body"))

    s.extend(section("6", "Reglas de negocio"))
    s.append(
        p(
            "<b>Shapley:</b> atribución generación vs BESS solo en sección Participación. "
            "No propagar ahorros de generación a Capacidad CFE, sidebar ni PDF global "
            "(salvo reporte acumulado: solo parte BESS).",
            "body",
        )
    )
    s.append(
        p(
            "<b>IUSA 1 Banco:</b> intercambio REC/ENT solo en Banco_1_Filtrado.csv. "
            "<b>Consumo:</b> KWH_REC (IUSA 1), KWH_NETO (IUSA 2).",
            "body",
        )
    )
    s.append(p("Autorefresh del reporteador: cada 15 minutos (no sustituye el pipeline).", "body"))

    s.extend(section("7", "Solución de problemas"))
    s.append(
        table(
            [
                ["Síntoma", "Acción"],
                ["Medidores sin validar", "Sincronizar ahora; revisar ION/API."],
                ["Faltan filtrados", "Ejecutar Filtrar antes de reportes."],
                ["Error al escribir CSV", "Cerrar Excel en ArchivosReporte."],
                ["Timeout generación", "run_reporte_bess.py en consola."],
                ["Reporte desactualizado", "Procesar todo; luego Reconciliar/Rebuild."],
                ["BD bien, gráfica en cero", "Reconciliar y Rebuild desde primer día."],
                ["Cursores distintos", "Resumen → Evaluar → Alinear a BD."],
            ],
            [2.2 * inch, 4.3 * inch],
        )
    )

    s.extend(section("8", "Rutas y scripts"))
    s.append(
        table(
            [
                ["Ruta / script", "Uso"],
                ["data/ArchivosFuente/{Sub}/", "CSV crudos (sync o carga)."],
                ["data/ArchivosProcesados/{Sub}/", "Verificados y *_Filtrado.csv."],
                ["data/ArchivosReporte/{Sub}/", "Combinados y energía diaria."],
                ["data/bess_perfiles.db", "Perfiles, sync_state y sync_log."],
                ["data/Tarifas/Ultima_Sincronizacion.csv", "Cursor de petición."],
                ["scripts/sincronizar_perfiles.py", "Sincronización ION + API."],
                ["scripts/run_reporte_bess.py", "Generación masiva de reportes."],
            ],
            [2.6 * inch, 3.9 * inch],
        )
    )
    s.append(Spacer(1, 12))
    s.append(p("Guía para administradores del sistema BESS — IUSASOL.", "footer"))
    return s


def main():
    if not os.environ.get("BESS_SKIP_CAPTURE"):
        try:
            capturar_sidebar_admin()
        except Exception as exc:
            print(f"Advertencia captura admin: {exc}", file=sys.stderr)
    build_pdf(_build_story(), PDF_OUT, f"Guía administrador BESS · v{VERSION}")
    print(f"PDF generado: {PDF_OUT}")


if __name__ == "__main__":
    main()
