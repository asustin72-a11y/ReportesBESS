# BESS 5.18.4 — Suite IUSASOL

## Resumen

El preflight de reloj **verifica y, si puede, auto-repara** zona horaria y NTP
antes del sync automático. Así se evita el bloqueo persistente cuando el reloj
queda desincronizado (p. ej. tras reinicios o desajustes en Hyper-V).

## Cambios

- `scripts/preflight_reloj.py`: si hay bloqueo, intenta `set-timezone`,
  `set-ntp true` y restart de `systemd-timesyncd` / `chrony` con `sudo -n`;
  revalida y registra `reparaciones` en `data/sync_preflight.json`.
- `deploy/sudoers-bess-ntp.example`: reglas NOPASSWD para el usuario `bess`.
- `deploy/install-cron.sh` y `docs/DOCKER.md`: instrucciones de instalación.
- Sidebar: aviso breve si el reloj fue auto-reparado.
- Imagen Compose: `bess:5.18.4`.

## Migración desde 5.18.3

```bash
cd ~/ReportesBESS
git fetch --tags
git checkout -f v5.18.4
docker compose up -d --build
grep __version__ bess/__init__.py
```

**Una vez (root)** — habilitar auto-reparación NTP:

```bash
sudo cp ~/ReportesBESS/deploy/sudoers-bess-ntp.example /etc/sudoers.d/bess-ntp
sudo chmod 440 /etc/sudoers.d/bess-ntp
sudo visudo -cf /etc/sudoers.d/bess-ntp
sudo -n timedatectl set-ntp true && echo OK
```

Probar preflight:

```bash
python3 ~/ReportesBESS/scripts/preflight_reloj.py ~/ReportesBESS/data/sync_preflight.json
```

## Versión anterior

- [5.18.3](RELEASE_NOTES_5.18.3.md)
