"""Política de contraseñas del sistema (RN-AU).

Nivel **Media** (decisión del dueño): mínimo 8 caracteres, con al menos una
mayúscula, una minúscula y un dígito. Aplica a:
  - auto-registro de estudiantes (`POST /auth/register`),
  - cambio de contraseña propio (`PUT /auth/change-password`),
  - definición de la contraseña definitiva tras el primer login (clave temporal).

Función pura, sin dependencias de DB ni framework: fácil de testear y reutilizar.
"""

from __future__ import annotations

LONGITUD_MINIMA = 8


class PasswordDebilError(ValueError):
    """La contraseña no cumple la política. El mensaje lista los requisitos faltantes."""


def _requisitos_incumplidos(password: str) -> list[str]:
    faltantes: list[str] = []
    if len(password) < LONGITUD_MINIMA:
        faltantes.append(f"al menos {LONGITUD_MINIMA} caracteres")
    if not any(c.isupper() for c in password):
        faltantes.append("una letra mayúscula")
    if not any(c.islower() for c in password):
        faltantes.append("una letra minúscula")
    if not any(c.isdigit() for c in password):
        faltantes.append("un número")
    return faltantes


def validar_password_fuerte(password: str) -> None:
    """Valida la contraseña contra la política Media. Lanza ``PasswordDebilError`` si no cumple.

    El mensaje enumera TODOS los requisitos faltantes para que el usuario los
    corrija de una sola vez.
    """
    faltantes = _requisitos_incumplidos(password)
    if faltantes:
        raise PasswordDebilError(
            "La contraseña debe tener " + ", ".join(faltantes) + "."
        )
