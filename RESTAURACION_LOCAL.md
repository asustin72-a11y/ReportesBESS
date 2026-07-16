# BESS v5.13.0 — Restauración en otra computadora

Respaldo portable para ejecutar la aplicación **sin depender de GitHub ni de Streamlit Cloud**.

## Requisitos

- **Windows 10/11** (probado en planta y oficina)
- **Python 3.10+** ([python.org](https://www.python.org/downloads/)) — marcar *Add Python to PATH*
- Acceso de red local al medidor ION (solo si vas a sincronizar por Modbus desde esa PC)

## 1. Descomprimir

Extrae el ZIP en una carpeta sin espacios problemáticos, por ejemplo:

```
C:\BESS\
```

La estructura debe quedar con `streamlit_app.py` y la carpeta `bess/` en la raíz.

## 2. Entorno virtual (recomendado)

```powershell
cd C:\BESS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

## 3. Credenciales y secretos

Este respaldo **incluye** `.streamlit\secrets.toml` (y `.env` si existía al generarlo).

Tras descomprimir, verifica que estén presentes:

```powershell
dir .streamlit\secrets.toml
dir .env
```

Si faltan, copia desde los ejemplos:

```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
copy .env.example .env
```

| Archivo | Uso |
|---------|-----|
| `.streamlit\secrets.toml` | Usuarios de login, API IUSASOL (BESS/BANCO) |
| `.env` | Alternativa a secrets (misma info en una línea JSON) |

**Advertencia:** el ZIP contiene contraseñas y claves API. Trasládalo solo por medios seguros (USB propio, red interna) y no lo subas a GitHub ni lo envíes por correo.

## 4. Datos incluidos en este respaldo

| Carpeta / archivo | Contenido |
|-------------------|-----------|
| `data/ArchivosProcesados/` | Perfiles ION, BESS, Banco filtrados |
| `data/ArchivosReporte/` | Reportes agregados (energía, acumulados, combinados) |
| `data/Tarifas/` | Tarifas CFE 2026 |
| `data/bess_perfiles.db` | SQLite con histórico API/ION (si existía al respaldar) |
| `data/modbus_map_default.csv` | Mapa Modbus ION |
| `data/ArchivosFuente/` | Vacía — se llena al sincronizar o subir CSV (admin) |

## 5. Ejecutar la aplicación

```powershell
cd C:\BESS
.\.venv\Scripts\Activate.ps1
streamlit run streamlit_app.py
```

Abre el navegador en la URL que muestra Streamlit (normalmente `http://localhost:8501`).

## 6. Sincronizar datos (planta / red local)

Desde la **sidebar** (botón Sincronizar) o por consola:

```powershell
# Completo: ION Modbus + API + export CSV + procesar reportes
python scripts\sincronizar_perfiles.py --quiet --procesar

# Solo API (sin ION — útil sin acceso al medidor)
python scripts\sincronizar_perfiles.py --sin-ion --quiet --procesar

# Solo descarga ION a CSV
python scripts\descargar_ion.py 172.16.111.209 2026-06-01
```

**ION Modbus** requiere estar en la misma red que el medidor (`172.16.x.x`). En Cloud no funciona; en PC de planta sí.

Variables opcionales en `.env` / secrets para ION:

```toml
[iusasol]
# ... credenciales API ...

# En .env:
# ION_HOST=172.16.111.209
# ION_PORT=502
```

## 7. Actualizar desde GitHub (opcional)

Este respaldo corresponde a la rama **`main`** (tag `v5.13.0`).

```powershell
git clone https://github.com/asustin72-a11y/ReportesBESS.git
cd ReportesBESS
git checkout v5.13.0
```

Conserva tu carpeta `data/` y tus `secrets.toml` al actualizar código.

## 8. Solución de problemas

| Problema | Acción |
|----------|--------|
| `ModuleNotFoundError: bess` | Ejecuta desde la raíz del proyecto (`C:\BESS`) |
| Gráficas sin botón PNG | Verifica `kaleido`: `pip install kaleido>=0.2.1` |
| Recibo PDF vacío en tarifas MEM | Confirma `data/Tarifas/Tarifas_2026.csv` |
| ION no conecta | Ping al host, firewall, puerto 502, ejecutar en red planta |
| API sin datos | Revisa `client_id` / `client_secret` en secrets |

## Versión

- **BESS:** 5.13.0
- **Entry point:** `streamlit_app.py` → `bess/ui/app.py`
