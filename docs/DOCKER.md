# BESS en servidor Linux con Docker

## Requisitos en el VPS

- Linux (Ubuntu 22.04+ recomendado)
- Docker Engine + Docker Compose plugin
- Puertos: `8501` (app) o `80/443` si usa proxy inverso
- Acceso de red a API IUSASOL y, si aplica, a medidores ION (Modbus TCP en VLAN planta)

## 1. Clonar el release

```bash
sudo apt-get update
sudo apt-get install -y git docker.io docker-compose-plugin
sudo usermod -aG docker $USER
# Cerrar sesión y volver a entrar para usar docker sin sudo

git clone https://github.com/asustin72-a11y/ReportesBESS.git
cd ReportesBESS
git checkout v5.6.3
```

## 2. Secretos y datos

```bash
cp deploy/secrets.toml.example deploy/secrets.toml
nano deploy/secrets.toml   # contraseñas admin/user y API IUSASOL
chmod 600 deploy/secrets.toml
```

**Datos persistentes** (`data/`):

- Opción A — copiar desde el equipo Windows (recomendado si ya tiene BD y reportes):

  ```bash
  # Desde su PC (PowerShell), ejemplo con scp:
  scp -r C:\Proyectos_IUSASOL\BESS\data usuario@IP_SERVIDOR:~/ReportesBESS/
  ```

  Incluya al menos: `data/Tarifas/`, `data/bess_perfiles.db`, `data/ArchivosReporte/`, logos en `data/`.

- Opción B — arrancar vacío y ejecutar sync desde la app (requiere API/granja accesibles desde el servidor).

## 3. Construir y levantar

```bash
docker compose build
docker compose up -d
docker compose logs -f bess
```

Abrir: `http://IP_DEL_SERVIDOR:8501`

## 4. Comandos útiles

```bash
docker compose ps
docker compose restart bess
docker compose down
docker compose pull && docker compose up -d --build   # tras git pull / nuevo tag
```

## 5. HTTPS con Nginx (opcional)

Ejemplo mínimo en el host (`/etc/nginx/sites-available/bess`):

```nginx
server {
    listen 80;
    server_name bess.tu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

Luego: `sudo certbot --nginx -d bess.tu-dominio.com`

## 6. Modbus ION en red de planta

Si el sync Modbus no alcanza IPs `172.16.x.x` desde la red Docker bridge:

1. En `docker-compose.yml`, descomente `network_mode: host` y comente `ports:`.
2. La app quedará en `http://IP_SERVIDOR:8501` directamente en el host.

O configure rutas/VPN en el VPS hacia la VLAN de medidores.

## 7. Respaldo

Respaldar periódicamente en el servidor:

```bash
tar czf bess-data-$(date +%Y%m%d).tar.gz data/ deploy/secrets.toml
```

## Variables de entorno (alternativa a secrets.toml)

En `docker-compose.yml` puede usar:

- `BESS_USERS` — JSON de usuarios (ver `bess/config/users.py`)
- `IUSASOL_CLIENT_ID`, `IUSASOL_CLIENT_SECRET`, etc.

`secrets.toml` montado en `/app/.streamlit/secrets.toml` tiene prioridad para usuarios si existe.

## 8. Sincronización automática cada 15 minutos

Para mantener la página al día sin intervención manual (sync + verificar + filtrar + reportes):

```bash
cd ~/ReportesBESS
bash deploy/install-cron.sh
```

Eso programa **cada 15 minutos** (zona `America/Mexico_City`):

```text
python scripts/sincronizar_perfiles.py --quiet --procesar
```

dentro del contenedor `bess`.

**Probar antes de esperar al cron:**

```bash
~/ReportesBESS/scripts/cron_sincronizar.sh
tail -30 ~/ReportesBESS/logs/sync-$(date +%Y%m%d).log
```

**Si no corre el cron automático**, revise en la VM:

```bash
crontab -l
docker ps --filter name=bess-app
groups    # debe incluir 'docker' para el usuario bess
bash deploy/install-cron.sh   # reinstalar tras actualizar
~/ReportesBESS/scripts/cron_sincronizar.sh
```

Errores frecuentes en el log:

| Mensaje en log | Causa | Acción |
|----------------|-------|--------|
| `docker no encontrado` | Cron sin PATH | `bash deploy/install-cron.sh` (v5.6.2+) |
| `contenedor bess-app no esta en ejecucion` | Docker caído | `docker compose up -d` |
| `ERROR (codigo N)` | Fallo sync/procesar | Ver líneas anteriores en el mismo log |
| `Omitido: otra sincronizacion en curso` | Corrida anterior aún activa | Normal si tarda >15 min |

**Ver / quitar el cron:**

```bash
crontab -l
crontab -e    # borrar las líneas con cron_sincronizar.sh
```

**Modbus ION:** si el sync a `172.16.x.x` falla desde Docker bridge, active `network_mode: host` en `docker-compose.yml` (sección 6). El cron usa el mismo contenedor que la app.

**Nota:** si una corrida tarda más de 15 minutos, la siguiente se omite hasta que termine (`flock`).
