"""Hashear la contraseña no puede congelar el servidor entero (c-78).

## El problema, medido

`bcrypt` con 12 rounds tarda **248 ms** por alta (medido en el contenedor el
25/8/2026). Es lento A PROPÓSITO: esa lentitud es lo que lo hace seguro contra
fuerza bruta, y no se toca.

El problema no era la lentitud sino DÓNDE corría. `hashear_password` es una
función sincrónica que se llamaba **directo dentro de corrutinas** —
`provisionar_o_recuperar_usuario` (el alta por LTI) y `crear_usuario`—, así que
bloqueaba el bucle de eventos: mientras hashea, el proceso no atiende NADA.

Medido con 10 altas concurrentes: 2434 ms, y **cualquier otro request esperaba
los 2434 ms completos**. Extrapolado al caso real —una comisión entrando por LTI
a la vez, que es el primer minuto del examen—:

    70 alumnos  -> ~17 s con el servidor congelado
    100 alumnos -> ~25 s con el servidor congelado

Y eso en hardware de desarrollo. Producción corre en 0,1 CPU compartida.

Congelado quiere decir congelado: los alumnos que YA están rindiendo no pueden
guardar respuestas ni mandar evidencia mientras el resto se da de alta.

## La corrección

`hashear_password_async` lo corre en un thread aparte (`asyncio.to_thread`). No
lo hace más rápido —sigue tardando 248 ms, y así tiene que ser— pero deja de
bloquear: el bucle sigue atendiendo al resto mientras el hash se calcula.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.infrastructure.auth.hashing import (
    hashear_password,
    hashear_password_async,
    verificar_password,
)

pytestmark = pytest.mark.asyncio


async def test_el_hash_sigue_siendo_valido() -> None:
    """Lo primero: correrlo en otro thread no puede cambiar el resultado."""
    hash_ = await hashear_password_async("Estudiante123")
    assert verificar_password("Estudiante123", hash_)
    assert not verificar_password("otra-cosa", hash_)


async def test_no_congela_el_bucle_mientras_hashea() -> None:
    """LA prueba. Mientras se hashea, el bucle tiene que seguir atendiendo.

    Se lanzan varias altas concurrentes y, en paralelo, una tarea liviana que
    solo mira el reloj. Si el hash bloquea, esa tarea no corre hasta que TODOS
    los hashes terminan, y su latencia es la suma de todos.
    """
    ALTAS = 8

    async def alta() -> None:
        await hashear_password_async("Estudiante123")

    async def tarea_liviana() -> float:
        """Espeja a un alumno rindiendo: quiere ser atendido YA."""
        inicio = time.perf_counter()
        await asyncio.sleep(0)
        return time.perf_counter() - inicio

    tareas = [asyncio.create_task(alta()) for _ in range(ALTAS)]
    liviana = asyncio.create_task(tarea_liviana())
    await asyncio.gather(*tareas, liviana)

    espera = liviana.result()
    # Con el hash bloqueando, esta espera era del orden de ALTAS * 248 ms
    # (≈2 s con 8). Sin bloquear tiene que ser de milisegundos.
    assert espera < 0.5, (
        f"el bucle quedó bloqueado {espera*1000:.0f} ms mientras hasheaba: "
        "bcrypt volvió a correr dentro de la corrutina"
    )


async def test_varias_altas_concurrentes_se_reparten_en_threads() -> None:
    """N altas concurrentes tienen que tardar MENOS que N veces una sola.

    Es la diferencia entre serializar en el bucle y repartir en el pool. No se
    exige un speedup lineal —el GIL y el pool tienen su techo— pero sí que no
    sea la suma."""
    una = time.perf_counter()
    await hashear_password_async("Estudiante123")
    costo_de_una = time.perf_counter() - una

    ALTAS = 4
    inicio = time.perf_counter()
    await asyncio.gather(*(hashear_password_async("Estudiante123") for _ in range(ALTAS)))
    costo_de_varias = time.perf_counter() - inicio

    assert costo_de_varias < costo_de_una * ALTAS * 0.9, (
        f"{ALTAS} altas tardaron {costo_de_varias:.2f}s contra "
        f"{costo_de_una:.2f}s de una sola: se están serializando"
    )


def test_la_version_sincronica_sigue_existiendo() -> None:
    """No se rompe a quien la usa fuera de un contexto async (scripts, seed)."""
    hash_ = hashear_password("Estudiante123")
    assert verificar_password("Estudiante123", hash_)
