# Descargar perfil ION — `descargar_ion.exe`

> **PDF:** [DESCARGAR_ION.pdf](DESCARGAR_ION.pdf) — manual listo para imprimir o distribuir.  
> Regenerar: `python docs/generar_descargar_ion_pdf.py`

Herramienta de línea de comandos para descargar el **perfil de carga** de un medidor Schneider **ION 8650** por **Modbus TCP**, desde una fecha de inicio hasta el **último registro** almacenado en el medidor.

No requiere Python instalado: solo el ejecutable y acceso de red al medidor (puerto **502**).

---

## Requisitos

| Requisito | Detalle |
|-----------|---------|
| Sistema | Windows 10/11 (64 bits) |
| Red | PC en la misma red que el medidor; firewall permite salida TCP al puerto 502 |
| Medidor | ION 8650 con Data Recorder configurado (módulo **1**, **6 canales** por defecto) |
| Permisos | Escritura en la carpeta desde la que se ejecuta el programa |

---

## Parámetros

| # | Parámetro | Obligatorio | Descripción |
|---|-----------|-------------|-------------|
| 1 | **IP** | Sí | Dirección IP del medidor (ej. `172.16.111.209`) |
| 2 | **Fecha inicio** | Sí | `YYYY-MM-DD` o `YYYY-MM-DD HH:MM:SS` (hora local México) |
| 3 | **Archivo salida** | No | Ruta del CSV; si se omite, se genera automáticamente en la carpeta actual |

**Comportamiento fijo:** la descarga siempre llega hasta el **último registro** disponible en el medidor (no hay parámetro de fecha fin).

### Opciones avanzadas (script Python / desarrollo)

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--puerto` | `502` | Puerto Modbus TCP |
| `--modulo-dr` | `1` | Número de módulo Data Recorder en ION Setup |
| `--sources` | `6` | Cantidad de canales de energía |
| `--int32` | — | Decodificar valores como int32 (default: float32) |

---

## Uso con el ejecutable

1. Copie `descargar_ion.exe` a la carpeta donde quiera guardar el CSV (o ábrala en PowerShell).
2. Ejecute:

```powershell
cd C:\MisDescargas
.\descargar_ion.exe 172.16.111.209 2026-05-01
```

Con nombre de archivo explícito:

```powershell
.\descargar_ion.exe 172.16.111.209 2026-05-01 perfil_mayo.csv
```

### Nombre del archivo generado (automático)

Si no indica ruta de salida, el CSV se guarda en **la carpeta desde la que ejecutó el programa**:

```
<IP_con_guiones>_<YYYYMMDD>_<HHMMSS>.csv
```

Ejemplo para IP `172.16.111.209` ejecutado el 25/06/2026 a las 14:30:52:

```
172_16_111_209_20260625_143052.csv
```

---

## Aviso cuando la fecha es muy antigua

Si la fecha solicitada es **anterior al primer registro** del medidor, el programa muestra un aviso y **continúa** descargando **todos** los datos disponibles:

```
AVISO: La fecha solicitada es anterior al primer registro disponible.
  Solicitada:  2026-05-01 00:00:00
  Disponible desde: 2026-06-25 22:20:00
  Se descargaran todos los datos disponibles en el medidor.
```

---

## Formato del CSV

Codificación **UTF-8 con BOM**, separador coma, fin de línea **CRLF** (compatible con Excel en Windows).

| Columna | Descripción |
|---------|-------------|
| `Fecha` | Timestamp `YYYY-MM-DD HH:MM:SS` (America/Mexico_City) |
| `KWH_REC` | Energía activa recibida |
| `KWH_ENT` | Energía activa entregada |
| `KVARH_Q1` … `KVARH_Q4` | Energía reactiva por cuadrante |

Intervalo típico del Data Recorder: **5 minutos**.

---

## Salida en consola (ejemplo)

```
Medidor: 172.16.111.209:502  (Data Recorder modulo 1)
Fecha solicitada: 2026-05-01 00:00:00
Rango efectivo: 2026-05-01 00:05:00 -> 2026-06-26 14:55:00
Registros a descargar: 1234 (#1 .. #1234)
  Progreso: 100/1234 registros...
  ...
Descargados 1234 registros -> C:\MisDescargas\172_16_111_209_20260625_143052.csv
  Rango temporal: 2026-05-01 00:05:00  a  2026-06-26 14:55:00
```

Código de salida: **0** = éxito, **1** = error (conexión, sin datos, etc.).

---

## Errores frecuentes

| Mensaje | Causa probable | Acción |
|---------|----------------|--------|
| `No se pudo conectar a ...:502` | IP incorrecta, medidor apagado o red/firewall | Verificar IP, ping y puerto 502 |
| `No hay registros desde ...` | Fecha inicio posterior al último registro | Usar una fecha anterior o vaciar buffer del medidor |
| `No se descargaron registros` | Rango vacío o fallos de lectura Modbus | Revisar módulo DR y número de sources |

---

## Uso alternativo (desde el proyecto BESS, con Python)

```powershell
cd C:\BESS
python scripts\descargar_ion.py 172.16.111.209 2026-05-01
```

O con el wrapper PowerShell:

```powershell
.\scripts\descargar_ion.ps1 -Ip 172.16.111.209 -Desde 2026-05-01
```

---

## Generar / actualizar el ejecutable

Desde la raíz del proyecto, con Python 3.10+ instalado:

```powershell
cd C:\BESS
.\scripts\build_descargar_ion.ps1
```

El archivo queda en:

```
C:\BESS\dist\descargar_ion.exe
```

Distribuya solo ese `.exe`; no necesita copiar carpetas `data` ni `bess`.

---

## Integración con BESS

El CSV descargado puede importarse al pipeline BESS:

```powershell
python scripts\import_perfil_csv.py --medidor ION ruta\al\archivo.csv
```

O usar la sincronización automática diaria (`scripts\sincronizar_perfiles.py`) cuando el medidor esté en la red del servidor BESS.
