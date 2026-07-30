# Descarga de Perfiles IUSASOL

Módulo de la Suite IUSASOL para bajar perfiles de la API a **CSV**
(sin escribir SQLite ni alimentar el pipeline de reportes).

## Suite (recomendado)

Tras el login, el selector muestra **BESS | Granja Solar | Descargas API**.

En el módulo Descargas: **Volver a la Suite** y **Cerrar sesión** en la barra
superior (igual que BESS y Granja).

```bash
streamlit run streamlit_app.py
```

## Standalone

```bash
streamlit run streamlit_descargas.py
```

(Sin login de usuarios; auth OAuth API igual que BESS.)

## Secciones

| UI | API | CSV |
|----|-----|-----|
| **Clientes** | `Reports/ISOL/Meters` + `Profiles/Gral` | `Fecha,KWH_REC,KWH_ENT,KVARH_Q1…Q4` |
| **Granja** | `Reports/Farm…` (1 request/día/medidor) | `Fecha,kwh_rec` |
| **Porteo** | `Reports/Porteo/Meters` + `Meter/Profiles` | mismo layout que Clientes |

## Uso

1. Elegir sección (Clientes / Granja / Porteo).
2. Rango de fechas + medidores.
3. **Generar descarga** → **Descargar** (CSV o ZIP).

## Notas

- Granja con rangos largos × muchos MEGAs puede tardar (aviso en UI).
- Porteo verificado en vivo (2026-07-30): 6 canales como ISOL.
