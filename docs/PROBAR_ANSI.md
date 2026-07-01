# Probar ANSI en ION 8650

BESS hoy sincroniza el ION por **Modbus TCP** (Ethernet, puerto 502).  
**ANSI C12.18/C12.19** usa el **puerto óptico frontal** del medidor — es un canal distinto.

---

## Diferencia Modbus vs ANSI

| | Modbus (actual BESS) | ANSI (esta prueba) |
|--|----------------------|-------------------|
| Conexión | Ethernet `172.16.x.x:502` | Sonda óptica en frente del medidor |
| Puerto medidor | COM Ethernet | **COM3** (óptico ANSI Type II) |
| Protocolo | Modbus TCP | ANSI C12.18 + tablas C12.19 |
| Cable | RJ45 | Sonda IR + USB al PC |

---

## Material necesario

1. **Sonda óptica ANSI Type II** (IEC), magnética, con cable USB o RS-232.
   - Schneider Electric u otros fabricantes (Diverse Electronics, etc.).
2. **PC en planta** con puerto USB libre.
3. Acceso al medidor para apoyar la sonda en el **puerto infrarrojo frontal**.

---

## Configurar el ION (ION Setup)

1. Conectar por Ethernet (como hoy) o con ION Setup en el PC de planta.
2. Ir a **Communications → Serial Settings → COM3** (optical port).
3. Configurar:
   - **Protocol:** ANSI C12.18 (no Modbus, no ION propietario).
   - **Baud rate:** 9600 (probar 19200 si no responde).
   - **Unit ID:** según manual (anotar si pide login).
4. Guardar y aplicar. **RTS Control** deshabilitado para COM3.

Documentación Schneider: [Serial connections — ION8650](https://product-help.schneider-electric.com/PowerLogic-ION8650/en-us/content/06-communications/serial-connections.htm)

---

## Instalar dependencias en BESS

```powershell
cd C:\BESS
pip install -r requirements-ansi.txt
```

---

## Ejecutar la prueba

### 1. Ver puerto USB de la sonda

```powershell
python scripts\probar_ansi.py --listar
```

Anotar el COM (ej. `COM4`).

### 2. Prueba básica (identificación C12.18)

Colocar la sonda en el medidor y ejecutar:

```powershell
python scripts\probar_ansi.py --puerto COM4 --prueba ident
```

Si no responde, probar varios baudios:

```powershell
python scripts\probar_ansi.py --puerto COM4 --probar-baudios --prueba ident
```

**Éxito esperado:**

```
Negociación C12.18: OK
Estándar: ANSI C12.18
Versión: x.y
Prueba IDENT: OK
```

### 3. Leer datos del medidor (tablas C12.19)

```powershell
python scripts\probar_ansi.py --puerto COM4 --prueba info
```

Si pide contraseña:

```powershell
python scripts\probar_ansi.py --puerto COM4 --prueba info --password "SU_CLAVE"
```

---

## Herramienta alternativa: Termineter

Interfaz interactiva (útil para explorar tablas):

```powershell
termineter
```

Dentro de Termineter: configurar `SERIAL_CONNECTION`, conectar, `use get_identification`, `run`.

---

## Problemas frecuentes

| Síntoma | Causa probable |
|---------|----------------|
| Sin respuesta en ningún baud | COM3 no está en ANSI; sonda mal colocada; COM incorrecto |
| Ident OK, info falla | Medidor exige contraseña ANSI |
| Funciona Modbus pero no ANSI | Normal: son puertos distintos; Ethernet no usa C12.18 |
| Puerto bloqueado en Windows | Driver USB de la sonda; probar otro puerto USB |

---

## ¿Integrar ANSI en BESS?

Hoy el pipeline diario (`sincronizar_perfiles.py`) usa **Modbus** porque:

- Es remoto por Ethernet (mismo enfoque que el servidor en planta).
- Ya lee el **Data Recorder** completo.

ANSI serviría sobre todo para:

- Verificación local en el medidor.
- Compatibilidad con herramientas tipo utility/CFE.
- Diagnóstico cuando Modbus no esté disponible.

Si la prueba ANSI funciona y quieren perfil histórico por ANSI, habría que mapear tablas C12.19 de **load profile** — es un desarrollo aparte del sync Modbus actual.
