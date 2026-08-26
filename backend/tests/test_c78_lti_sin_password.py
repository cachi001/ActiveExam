"""c-78 — El alta por LTI deja de hashear una contraseña que nadie va a usar.

El alta JIT generaba una contraseña **aleatoria de 32 bytes**, la hasheaba con
bcrypt (248 ms) y la guardaba. Esa contraseña **nunca se le comunica a nadie**:
el alumno entra por LTI, y si algún día quiere entrar directo fija la suya desde
el dashboard (``debe_cambiar_password=True``, y el primer set de un usuario LTI
ni siquiera pide la anterior). O sea: 248 ms por alumno para hashear un secreto
que nadie va a verificar nunca. Con 70 alumnos entrando juntos, eso es el grueso
de lo que queda del congelamiento medido en la avalancha LTI.

En su lugar se guarda un **centinela de "sin contraseña"**. Lo que hay que
sostener, y es lo que cubre este módulo:

  - contra el centinela, **ninguna** contraseña verifica (falla cerrado)
  - el centinela no es un hash bcrypt: nadie puede llegar a él hasheando algo
  - verificar contra el centinela **tarda lo mismo** que una verificación real,
    para no delatar por tiempo qué cuentas todavía no fijaron contraseña
  - el alumno puede fijar su contraseña después, y a partir de ahí entra normal
"""

from __future__ import annotations

import time

import pytest

from app.infrastructure.auth.hashing import (
    HASH_SIN_PASSWORD,
    es_sin_password,
    hashear_password,
    verificar_password,
)


def test_ninguna_password_verifica_contra_el_centinela():
    """Falla cerrado: no hay texto plano que abra una cuenta sin contraseña."""
    for intento in ["", " ", "admin", "password", HASH_SIN_PASSWORD, "!", "x" * 200]:
        assert verificar_password(intento, HASH_SIN_PASSWORD) is False, (
            f"«{intento}» abrió una cuenta que no tiene contraseña fijada"
        )


def test_el_centinela_no_es_un_hash_bcrypt():
    """Si fuera un hash válido, alguien podría llegar a él hasheando su preimagen.

    Un hash bcrypt siempre arranca con `$2`; el centinela arranca con `!` a
    propósito, que es un carácter que bcrypt nunca produce.
    """
    assert not HASH_SIN_PASSWORD.startswith("$2")
    assert HASH_SIN_PASSWORD.startswith("!")


def test_es_sin_password_distingue_el_centinela_de_un_hash_real():
    assert es_sin_password(HASH_SIN_PASSWORD) is True
    assert es_sin_password(hashear_password("una-password-real")) is False
    # Sin hash tampoco es una cuenta con contraseña utilizable.
    assert es_sin_password(None) is True
    assert es_sin_password("") is True


def test_verificar_contra_el_centinela_no_es_mas_rapido_que_una_real():
    """Si devolviera False al instante, el tiempo de respuesta del login
    delataría qué cuentas son LTI sin contraseña fijada — el mismo agujero de
    enumeración que ya se había tapado con `verificar_password_dummy`."""
    hash_real = hashear_password("comparacion-de-tiempos")

    t0 = time.perf_counter()
    verificar_password("no-es-la-password", hash_real)
    real_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    verificar_password("no-es-la-password", HASH_SIN_PASSWORD)
    centinela_ms = (time.perf_counter() - t0) * 1000

    # Cota floja a propósito: lo que se descarta es el "return False" inmediato,
    # no una diferencia de milisegundos. bcrypt a 12 rounds no baja de decenas
    # de ms en ninguna máquina.
    assert centinela_ms > real_ms / 4, (
        f"verificar contra el centinela tardo {centinela_ms:.0f} ms contra "
        f"{real_ms:.0f} ms de una real: la diferencia es medible desde afuera"
    )


def test_un_hash_ilegible_tampoco_deja_entrar():
    """Robustez: basura en la columna no puede reventar el login ni abrirlo."""
    for basura in ["", "no-es-un-hash", "$2b$roto", "!!!"]:
        assert verificar_password("lo-que-sea", basura) is False


@pytest.mark.asyncio
async def test_el_alta_lti_no_paga_bcrypt():
    """El punto de todo esto: crear la cuenta no puede costar 248 ms.

    Se mira el módulo de provisioning, que es donde estaba el costo: ya no
    hashea nada al crear el usuario.
    """
    import inspect

    from app.application.lti import jit_provisioning

    fuente = inspect.getsource(jit_provisioning)
    assert "hashear_password" not in fuente, (
        "el alta por LTI volvió a hashear una contraseña que nadie va a usar"
    )
    assert "HASH_SIN_PASSWORD" in fuente


def test_fijar_la_password_despues_reemplaza_el_centinela():
    """El centinela es un punto de partida, no un estado permanente."""
    hash_nuevo = hashear_password("la-que-eligio-el-alumno")

    assert es_sin_password(HASH_SIN_PASSWORD) is True
    assert es_sin_password(hash_nuevo) is False
    assert verificar_password("la-que-eligio-el-alumno", hash_nuevo) is True
