"""Hashing de passwords con bcrypt 12 rounds (C-55, D8).

Usa passlib[bcrypt] (decisión resuelta antes de implementar: bcrypt 12 rounds).
bcrypt es suficiente para MVP; argon2 es la alternativa recomendada modernamente
y queda como opcion de upgrade documentada (misma interfaz, distinto backend).

JAMÁS importar este modulo desde el dominio — solo desde infraestructura/presentacion.
Los secretos (hashes) nunca se loguean.
"""

from __future__ import annotations

import asyncio

from passlib.context import CryptContext

# CryptContext con bcrypt, 12 rounds (equilibrio seguridad/latencia para MVP).
# deprecated="auto" hace que passlib rehashee silenciosamente si el schema cambia.
_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# Hash bcrypt PRECOMPUTADO (12 rounds) de una password fija cualquiera. Existe
# solo para gastar el mismo tiempo de cómputo que una verificación real cuando
# el usuario NO existe (pentest 2026-08-21, H-timing): antes, el login cortaba
# camino sin llamar a bcrypt cuando el username no existía, y esa rama
# respondía en ~6ms contra ~250ms de la rama con usuario real — un atacante
# podía enumerar usernames válidos midiendo el tiempo de respuesta, aunque el
# mensaje de error fuera idéntico en ambos casos.
_DUMMY_HASH = _ctx.hash("dummy-password-para-timing-constante")

# Centinela de "esta cuenta no tiene contraseña fijada" (c-78).
#
# El alta por LTI generaba una contraseña aleatoria de 32 bytes y la hasheaba con
# bcrypt (248 ms) solo para llenar la columna. Esa contraseña NUNCA se le
# comunica a nadie: el alumno entra por LTI, y si quiere entrar directo fija la
# suya desde el dashboard (el primer set de un usuario LTI ni siquiera pide la
# anterior). Eran 248 ms por alumno para hashear un secreto que nadie iba a
# verificar, y con una comisión entrando junta eso es el grueso del
# congelamiento que se midió en la avalancha LTI.
#
# Arranca con "!" a propósito: bcrypt siempre produce hashes que empiezan con
# "$2", así que ningún texto plano puede hashear a esto. Es el mismo patrón de
# "unusable password" de Django.
HASH_SIN_PASSWORD = "!sin-password"


def es_sin_password(hashed: str | None) -> bool:
    """True si la cuenta no tiene una contraseña con la que se pueda entrar.

    Cubre tanto el centinela como la columna vacía: las dos significan lo mismo
    para quien pregunta "¿puede entrar con contraseña?".
    """
    return not hashed or hashed == HASH_SIN_PASSWORD


def hashear_password(plain: str) -> str:
    """Retorna el hash bcrypt del password en texto plano.

    El hash incluye salt aleatorio (passlib lo genera internamente).
    El resultado es seguro para almacenar en ``usuario.password_hash``.
    """
    return _ctx.hash(plain)


async def hashear_password_async(plain: str) -> str:
    """Igual que ``hashear_password``, pero SIN bloquear el bucle de eventos.

    Medido el 25/8/2026 en el contenedor: bcrypt con 12 rounds tarda **248 ms**
    por alta. Es lento a proposito —esa lentitud es lo que lo hace seguro contra
    fuerza bruta— y NO se toca.

    El problema no era la lentitud sino donde corria. Llamado directo dentro de
    una corrutina (que es como estaba en el alta por LTI y en la creacion de
    usuarios), bloquea el bucle: mientras hashea, el proceso no atiende NADA.
    Con 10 altas concurrentes se midieron 2434 ms en los que cualquier otro
    request esperaba los 2434 ms completos. Con una comision entrando junta por
    LTI —el primer minuto del examen— eso es ~17 s con 70 alumnos y ~25 s con
    100, con los que YA estan rindiendo sin poder guardar respuestas.

    Correrlo en un thread no lo acelera: lo saca del camino. El bucle sigue
    atendiendo al resto mientras el hash se calcula aparte.

    La version sincronica se conserva para los llamadores que no estan en un
    contexto async (scripts, seed).
    """
    return await asyncio.to_thread(hashear_password, plain)


def verificar_password(plain: str, hashed: str | None) -> bool:
    """Verifica un password en texto plano contra su hash bcrypt.

    Retorna ``True`` si coinciden, ``False`` si no. Timing constante
    (bcrypt ya es timing-safe por diseño — usa compare_digest internamente).

    Falla CERRADO ante cualquier hash que no sea bcrypt válido: el centinela de
    "sin contraseña", la columna vacía o basura. En esos casos gasta igual el
    tiempo de una verificación real — devolver ``False`` al instante delataría
    por tiempo qué cuentas todavía no fijaron su contraseña, que es el mismo
    agujero de enumeración que tapó ``verificar_password_dummy``.
    """
    if es_sin_password(hashed):
        verificar_password_dummy(plain)
        return False
    try:
        return _ctx.verify(plain, hashed)
    except Exception:  # noqa: BLE001 — hash ilegible: no deja entrar, y no revienta
        verificar_password_dummy(plain)
        return False


def verificar_password_dummy(plain: str) -> None:
    """Ejecuta una verificación bcrypt contra un hash fijo, SIN mirar el
    resultado — solo para gastar el mismo tiempo que ``verificar_password``
    cuando no hay un ``password_hash`` real contra el que comparar (usuario
    inexistente). Llamar esto en la rama "usuario no existe" del login antes
    de responder 401, para que el tiempo de respuesta no distinga esa rama de
    la de "usuario existe, password incorrecta"."""
    _ctx.verify(plain, _DUMMY_HASH)
