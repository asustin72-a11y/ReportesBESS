# Reemplazar KWH — BESS IUSA ARAGON

## Mapeo

| Origen `BESS_ARAGON.csv` | Destino `BESS_IUSA_ARAGON_Filtrado.csv` |
|--------------------------|----------------------------------------|
| **Carga (kWh)** | **KWH_REC** (columna 2) |
| **Descarga (kWh)** | **KWH_ENT** (columna 3) |

- Fila 1 origen -> fila 1 filtrado (por posicion).
- **Fecha** del filtrado no se modifica.
- El origen se lee **con encabezado** (`Día`, `Hora`, `Minuto`, `Mes`, ...).

## Uso

```bash
cd scripts/reemplazar_bess_aragon
python reemplazar_kwh.py --diagnostico
python reemplazar_kwh.py --dry-run
python reemplazar_kwh.py
```

Si origen y filtrado tienen distinto numero de filas, se copian las filas que alcancen y se avisa.

## Defaults

Los CSV deben estar **en la misma carpeta que el script**:

- `scripts/reemplazar_bess_aragon/BESS_ARAGON.csv`
- `scripts/reemplazar_bess_aragon/BESS_IUSA_ARAGON_Filtrado.csv`

Rutas distintas:

```bash
python reemplazar_kwh.py --origen "ruta\BESS_ARAGON.csv" --filtrado "ruta\BESS_IUSA_ARAGON_Filtrado.csv"
```
