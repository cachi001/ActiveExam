"""Generación del codigo_matriculacion de una comisión (C-70, modelo enrolment-key).

Formato: ``{materia.codigo}-{sufijo}`` donde el sufijo es aleatorio corto de un
alfabeto SIN caracteres ambiguos (sin O/0, I/1, L). El alfabeto no-ambiguo aplica
SOLO al sufijo GENERADO; un código provisto manualmente por el docente se guarda
EXACTAMENTE como se tipeó (solo strip externo) — ver ``normalizar_codigo``.

La unicidad la garantiza la DB (uq_comision_codigo_matriculacion). Ante colisión
(23505 → CodigoMatriculacionDuplicadoError) la generación reintenta con otro
sufijo hasta ``intentos`` veces. Reutilizable por el alta y por la rotación.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.domain.exam_content.errors import CodigoMatriculacionDuplicadoError

# Alfabeto sin caracteres ambiguos (sin O/0, I/1, L) — SOLO para el sufijo generado.
_ALFABETO_SUFIJO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LARGO_SUFIJO = 4
MAX_INTENTOS = 10

_T = TypeVar("_T")


def generar_sufijo() -> str:
    """Sufijo aleatorio de ``LARGO_SUFIJO`` chars del alfabeto no-ambiguo."""
    return "".join(secrets.choice(_ALFABETO_SUFIJO) for _ in range(LARGO_SUFIJO))


def componer_codigo(materia_codigo: str, sufijo: str | None = None) -> str:
    """Compone ``{materia_codigo}-{sufijo}`` (genera el sufijo si no se pasa)."""
    return f"{materia_codigo.strip()}-{sufijo if sufijo is not None else generar_sufijo()}"


def normalizar_codigo(codigo: str) -> str:
    """Normaliza un código provisto por el docente: SOLO strip externo.

    Decisión del owner (C-70): el código se guarda EXACTAMENTE como se tipeó — no
    se pasa a mayúsculas/minúsculas ni se normaliza. La unicidad es case-sensitive.
    """
    return codigo.strip()


async def generar_codigo_libre(
    persistir_con_codigo: Callable[[str], Awaitable[_T]],
    materia_codigo: str,
    *,
    intentos: int = MAX_INTENTOS,
) -> _T:
    """Genera un codigo_matriculacion libre y lo aplica vía ``persistir_con_codigo``.

    ``persistir_con_codigo`` recibe el código candidato e intenta aplicarlo
    (persistir un alta o rotar el de una comisión), elevando
    ``CodigoMatriculacionDuplicadoError`` si colisiona con otro existente (23505).
    Ante colisión se reintenta con otro sufijo. Devuelve lo que devuelva
    ``persistir_con_codigo`` en el primer intento libre.

    Raises:
        CodigoMatriculacionDuplicadoError: se agotaron los ``intentos`` sin lograr
            un código libre (colisión persistente — extremadamente improbable).
    """
    ultimo_error: CodigoMatriculacionDuplicadoError | None = None
    for _ in range(max(1, intentos)):
        candidato = componer_codigo(materia_codigo)
        try:
            return await persistir_con_codigo(candidato)
        except CodigoMatriculacionDuplicadoError as exc:
            ultimo_error = exc
            continue
    assert ultimo_error is not None  # el loop corre >= 1 vez
    raise ultimo_error
