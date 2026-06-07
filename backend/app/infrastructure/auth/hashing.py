"""Hashing de passwords con bcrypt 12 rounds (C-55, D8).

Usa passlib[bcrypt] (decisión resuelta antes de implementar: bcrypt 12 rounds).
bcrypt es suficiente para MVP; argon2 es la alternativa recomendada modernamente
y queda como opcion de upgrade documentada (misma interfaz, distinto backend).

JAMÁS importar este modulo desde el dominio — solo desde infraestructura/presentacion.
Los secretos (hashes) nunca se loguean.
"""

from __future__ import annotations

from passlib.context import CryptContext

# CryptContext con bcrypt, 12 rounds (equilibrio seguridad/latencia para MVP).
# deprecated="auto" hace que passlib rehashee silenciosamente si el schema cambia.
_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hashear_password(plain: str) -> str:
    """Retorna el hash bcrypt del password en texto plano.

    El hash incluye salt aleatorio (passlib lo genera internamente).
    El resultado es seguro para almacenar en ``usuario.password_hash``.
    """
    return _ctx.hash(plain)


def verificar_password(plain: str, hashed: str) -> bool:
    """Verifica un password en texto plano contra su hash bcrypt.

    Retorna ``True`` si coinciden, ``False`` si no. Timing constante
    (bcrypt ya es timing-safe por diseño — usa compare_digest internamente).
    """
    return _ctx.verify(plain, hashed)
