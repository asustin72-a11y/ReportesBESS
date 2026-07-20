# Consultas Usuarios (IUSASOL)

Módulo **independiente de BESS** para reportes y consultas sobre el sistema de
monitoreo de energía de IUSASOL (API ISOL).

## Organización del producto

| Módulo | Estado | Rol |
|--------|--------|-----|
| **BESS** | En producción | Reportes y operación de sistemas BESS (ION / BANCO) |
| **Consultas Usuarios** | En diseño | Consultas y reportes de contratos / medidores / perfiles (API ISOL) |

Ambos pertenecen a IUSASOL. No comparten UI ni flujo de login; pueden compartir
credenciales de API y utilidades de bajo nivel cuando convenga.

## Alcance actual (primer corte)

Aún no está cerrado el alcance completo. Por ahora el reporteador cubre las
consultas ya hechas a la API:

1. Contratos activos (`Reports/ISOL/Contracts`)
2. Medidores por contrato (`Reports/ISOL/Contract`)
3. Último perfil con energía ≠ 0 (`Reports/ISOL/Profiles/Gral`)
4. Contratos sin medidores

No expuesto por la API v2.1: tipo de comunicación del medidor (Ethernet / GSM).

## Ubicación en Windows (oficina / desarrollo)

Ruta canónica del repo en PC local:

```text
C:\Proyectos_IUSASOL\ReporteadorIUSASOL
```

```powershell
# Primera vez
mkdir C:\Proyectos_IUSASOL -Force
git clone https://github.com/asustin72-a11y/ReportesBESS.git C:\Proyectos_IUSASOL\ReporteadorIUSASOL
cd C:\Proyectos_IUSASOL\ReporteadorIUSASOL
git checkout cursor/consultas-usuarios-reporteador-6e2a

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Consultas Usuarios
streamlit run streamlit_consultas_usuarios.py

# BESS (producción / módulo aparte)
# streamlit run streamlit_app.py
```

Si ya tenías el repo en otra carpeta (p. ej. `C:\BESS` o `ReportesBESS`):

```powershell
mkdir C:\Proyectos_IUSASOL -Force
Move-Item -Path "C:\ruta\anterior\ReportesBESS" -Destination "C:\Proyectos_IUSASOL\ReporteadorIUSASOL"
```

## Cómo ejecutar

```bash
# UI del reporteador
streamlit run streamlit_consultas_usuarios.py

# Regenerar CSV desde la API (mismas credenciales [iusasol])
python scripts/reporte_contratos_medidores_iusasol.py \
  --salida data/consultas_usuarios/reporte_principal.csv
```

Datos de trabajo: `data/consultas_usuarios/`.

## Estructura

```
consultas_usuarios/     # paquete del módulo (UI + carga de datos)
streamlit_consultas_usuarios.py
data/consultas_usuarios/
docs/CONSULTAS_USUARIOS.md
scripts/reporte_contratos_medidores_iusasol.py   # generador CSV (API)
```
