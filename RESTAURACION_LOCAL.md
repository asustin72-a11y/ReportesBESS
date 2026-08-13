# Suite IUSASOL v5.18.13 — Restauración en otra computadora

Respaldo portable para operar la **Suite** (BESS, Granja, Descargas, Análisis de
Perfil, Consultar Tarifa) **sin depender de GitHub**.

## Requisitos

- **Windows 10/11** (probado en planta y oficina)
- **Python 3.10+** ([python.org](https://www.python.org/downloads/)) — marcar *Add Python to PATH*
- Acceso de red local al medidor ION (solo si vas a sincronizar por Modbus)
- Chromium para Playwright (tarifas CFE / sync API según uso)

## 1. Descomprimir

Extrae el ZIP en una carpeta sin espacios problemáticos, por ejemplo:

```
C:\IUSASOL\
```

La estructura debe quedar con `streamlit_app.py`, `bess/`, `granja/`, `suite/`, etc. en la raíz.

## 2. Entorno virtual (recomendado)

```powershell
cd C:\IUSASOL
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

## 3. Credenciales y secretos

Este respaldo **incluye** `.streamlit\secrets.toml` (y `.env` si existía al generarlo),
salvo que se haya creado con `-SinSecretos`.

```powershell
dir .streamlit\secrets.toml
dir .env
```

Si faltan:

```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# o desde deploy\secrets.toml.example
```

**Advertencia:** el ZIP puede contener contraseñas y claves API. No lo subas a GitHub ni lo envíes por correo.

## 4. Datos incluidos

| Carpeta / archivo | Contenido |
|-------------------|-----------|
| `data/ArchivosProcesados/` | Perfiles filtrados (si había al respaldar) |
| `data/ArchivosReporte/` | Combinados / energía / acumulados |
| `data/Tarifas/` | Tarifas CFE (DIST/GDMTH/T1/PDBT…) |
| `data/ReportesTarifasCFE/` | CSV por periodo (consulta tarifas) |
| `data/bess_perfiles.db` | SQLite BESS + Granja (si existía) |
| `data/ArchivosFuente/` | Vacía o parcial — se llena al sincronizar |

## 5. Ejecutar la Suite

```powershell
cd C:\IUSASOL
.\.venv\Scripts\Activate.ps1
streamlit run streamlit_app.py
```

URL típica: `http://localhost:8501` — selector de módulos tras el login.

Entradas directas (opcional):

| App | Comando |
|-----|---------|
| Solo BESS | `streamlit run streamlit_bess.py` |
| Granja | `streamlit run streamlit_granja.py` |
| Descargas | `streamlit run streamlit_descargas.py` |
| Análisis de Perfil | `streamlit run streamlit_analisis_perfil.py` |
| Consultar Tarifa | `streamlit run streamlit_tarifas_cfe.py` |

## 6. Sincronizar datos

```powershell
python scripts\sincronizar_perfiles.py --quiet --procesar
python scripts\sincronizar_perfiles.py --sin-ion --quiet --procesar
python scripts\sincronizar_granja_megas.py
```

## 7. Actualizar desde GitHub (opcional)

Tag de este respaldo: **`v5.18.13`**.

```powershell
git clone https://github.com/asustin72-a11y/ReportesBESS.git
cd ReportesBESS
git checkout v5.18.13
```

Conserva `data/` y `secrets.toml` al actualizar código.

## 8. Generar un nuevo respaldo

Desde la raíz del repo (con datos y secretos locales):

```powershell
.\scripts\crear_respaldo.ps1
# sin secretos:
.\scripts\crear_respaldo.ps1 -SinSecretos
```

## Versión

- **Suite / BESS:** 5.18.13
- **Entry Suite:** `streamlit_app.py` → `suite/ui/app.py`
