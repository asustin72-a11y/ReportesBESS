"""Administración de usuarios para la UI de superadmin."""

from __future__ import annotations

import pandas as pd

from bess.config.users import ETIQUETA_ROL, ROLES_VALIDOS
from bess.data.users_db import (
    guardar_filas_usuarios,
    invalidar_cache_usuarios,
    leer_filas_usuarios,
)

CAMPOS_USUARIO = ("Usuario", "Nombre", "Rol", "Activo", "Nueva_contraseña")

REGLAS_USUARIOS = """
**Reglas**
- Debe existir al menos **un superadministrador activo**.
- No puede eliminarse ni desactivarse a sí mismo si es el único superadmin.
- Usuario **nuevo**: obligatorio **Nueva_contraseña** (la columna se vacía al recargar).
- Para **cambiar contraseña**, escriba la nueva en esa columna del usuario existente.
- Roles: **user** (visualizador), **admin** (operador), **superadmin** (configuración).
"""


def _filas_a_df(filas: list[dict[str, str]]) -> pd.DataFrame:
    if not filas:
        return pd.DataFrame(columns=list(CAMPOS_USUARIO))
    df = pd.DataFrame(filas)
    for col in CAMPOS_USUARIO:
        if col not in df.columns:
            df[col] = ""
    return df[list(CAMPOS_USUARIO)].astype(str)


def _df_a_filas(df: pd.DataFrame) -> list[dict[str, str]]:
    filas: list[dict[str, str]] = []
    for _, row in df.iterrows():
        fila = {}
        for col in CAMPOS_USUARIO:
            valor = row.get(col, "")
            fila[col] = "" if pd.isna(valor) else str(valor).strip()
        filas.append(fila)
    return filas


def _es_activo(valor: str) -> bool:
    return str(valor).strip() in ("1", "true", "True", "SI", "si")


def cargar_dataframe_usuarios() -> pd.DataFrame:
    return _filas_a_df(leer_filas_usuarios())


def validar_dataframe_usuarios(
    df: pd.DataFrame,
    usuario_sesion: str | None,
) -> list[str]:
    errores: list[str] = []
    if df is None or df.empty:
        return ["Debe haber al menos un usuario."]

    existentes = {f["Usuario"] for f in leer_filas_usuarios()}
    usernames: list[str] = []
    superadmins_activos: list[str] = []

    for _, row in df.iterrows():
        user = str(row.get("Usuario", "")).strip()
        if not user:
            errores.append("Hay filas sin nombre de usuario.")
            continue
        if user in usernames:
            errores.append(f'Usuario duplicado: "{user}".')
        usernames.append(user)

        rol = str(row.get("Rol", "")).strip()
        if rol not in ROLES_VALIDOS:
            errores.append(f'Usuario "{user}": rol inválido ({rol}).')

        activo = _es_activo(str(row.get("Activo", "1")))
        pwd = str(row.get("Nueva_contraseña", "")).strip()
        if user not in existentes and not pwd:
            errores.append(f'Usuario nuevo "{user}": indique Nueva_contraseña.')

        if rol == "superadmin" and activo:
            superadmins_activos.append(user)

    if not superadmins_activos:
        errores.append("Debe quedar al menos un superadministrador activo.")

    sesion = (usuario_sesion or "").strip()
    if sesion and sesion not in usernames:
        errores.append(
            f"No puede eliminar su usuario ({sesion}) mientras tiene la sesión abierta."
        )
    elif sesion and sesion in usernames:
        fila = df[df["Usuario"].astype(str).str.strip() == sesion].iloc[0]
        rol = str(fila.get("Rol", "")).strip()
        activo = _es_activo(str(fila.get("Activo", "1")))
        if rol != "superadmin" or not activo:
            otros = [u for u in superadmins_activos if u != sesion]
            if not otros:
                errores.append(
                    "No puede desactivarse ni cambiar de rol sin otro superadmin activo."
                )

    return errores


def guardar_dataframe_usuarios(
    df: pd.DataFrame,
    usuario_sesion: str | None,
) -> None:
    errores = validar_dataframe_usuarios(df, usuario_sesion)
    if errores:
        raise ValueError("\n".join(errores))
    guardar_filas_usuarios(_df_a_filas(df))
    invalidar_cache_usuarios()


def opciones_rol() -> list[str]:
    return sorted(ROLES_VALIDOS)


def etiqueta_rol(rol: str) -> str:
    return ETIQUETA_ROL.get(rol, rol)
