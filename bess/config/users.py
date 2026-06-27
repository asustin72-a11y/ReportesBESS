"""Carga y validación de usuarios (sin Streamlit)."""

from __future__ import annotations

import hashlib
import json
import os

ROLES_VALIDOS = frozenset({'admin', 'user'})


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verificar_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def _normalizar_entrada(username: str, data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f'Usuario "{username}": entrada inválida.')
    rol = str(data.get('rol', 'user')).strip()
    if rol not in ROLES_VALIDOS:
        raise ValueError(f'Usuario "{username}": rol "{rol}" no válido (admin|user).')
    nombre = str(data.get('nombre', username)).strip() or username

    if 'password_hash' in data:
        pwd_hash = str(data['password_hash']).strip()
    elif 'password' in data:
        pwd_hash = hash_password(str(data['password']))
    else:
        raise ValueError(f'Usuario "{username}": falta "password" o "password_hash".')

    return {'password': pwd_hash, 'rol': rol, 'nombre': nombre}


def parse_usuarios_json(raw: str) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict) or not data:
        raise ValueError('BESS_USERS debe ser un objeto JSON con al menos un usuario.')
    return {str(k): _normalizar_entrada(str(k), v) for k, v in data.items()}


def parse_usuarios_mapping(data: dict) -> dict:
    if not data:
        raise ValueError('La configuración de usuarios está vacía.')
    return {str(k): _normalizar_entrada(str(k), dict(v)) for k, v in data.items()}


def cargar_usuarios_desde_env() -> dict | None:
    raw = os.environ.get('BESS_USERS')
    if not raw:
        return None
    return parse_usuarios_json(raw.strip())
