"""Reconocer el error de "ese id no es un UUID" (c-78).

Encontrado recorriendo producción el 26/8/2026: pedir cualquier recurso con un id
que no fuera UUID devolvía **500**. Verificado sobre ``/exam-content/{id}``,
``/exam-content/{id}/preguntas``, ``/exam-content/{id}/impacto-baja`` y
``/users/{id}``. El disparador real fue ``/exam-content/banco/preguntas`` — una
ruta que no existe y que terminaba matcheando ``/{examen_id}/preguntas`` con
``examen_id="banco"``.

Un id malformado significa lo mismo que "no existe": no puede corresponder a
ninguna fila. Devolver 500 hace pensar que se rompió el servidor cuando el pedido
era inválido, y ensucia las métricas de error con ruido que no lo es.

El predicado vive acá, separado del manejador HTTP, porque el texto del error
depende de la capa que lo produce y hay **dos formas distintas**, las dos reales:

- asyncpg lo rechaza ANTES de mandarlo, al bindear el parámetro:
  ``invalid input for query argument $1: 'no-es-uuid' (invalid UUID ...)``
- Postgres lo rechaza al castear un literal en el SQL:
  ``invalid input syntax for type uuid``

La primera es la que apareció en producción; la segunda aparece con SQL crudo.
Reconocer una sola dejaba el 500 igual, que es exactamente lo que pasó en el
primer intento de arreglo.
"""

from __future__ import annotations

# Marcadores en minúscula. Se compara contra el texto completo de la excepción
# (incluido ``__cause__``), no contra un tipo: asyncpg envuelve el error y el tipo
# concreto cambia según el camino.
_MARCADORES = (
    "invalid uuid",  # asyncpg al bindear el argumento
    "invalid input syntax for type uuid",  # Postgres al castear un literal
)


def es_error_de_uuid_invalido(exc: BaseException) -> bool:
    """True si la excepción viene de un id que no es un UUID válido.

    Mira también la causa encadenada: SQLAlchemy envuelve el error de asyncpg y
    el texto útil suele quedar en ``__cause__`` / ``orig``.
    """
    vistos = 0
    actual: BaseException | None = exc
    while actual is not None and vistos < 5:
        texto = f"{actual}{getattr(actual, 'orig', '')}".lower()
        if any(m in texto for m in _MARCADORES):
            return True
        actual = actual.__cause__ or actual.__context__
        vistos += 1
    return False
