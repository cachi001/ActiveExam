"""C-72 §1 — Deadline efectivo de una rendición (dominio puro, sin I/O).

El vencimiento de una rendición es el MÍNIMO entre el límite individual del
alumno (``creada_en + tiempo_limite_min``) y el cierre de la ventana del examen.
Se calcula siempre con hora del servidor; el cliente es sensor no confiable
(regla dura de dominio #6). La gracia es tolerancia a latencia, NO tiempo de
examen: nunca se lee del cliente.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def deadline_efectivo(
    *,
    creada_en: datetime,
    tiempo_limite_min: int | None,
    cierre: datetime,
) -> datetime:
    """Vencimiento efectivo = min(creada_en + tiempo_limite_min, cierre).

    Si ``tiempo_limite_min`` es None (examen sin límite individual) el
    vencimiento es el ``cierre`` de la ventana."""
    if tiempo_limite_min is None:
        return cierre
    limite_individual = creada_en + timedelta(minutes=tiempo_limite_min)
    return min(limite_individual, cierre)


def vencido(*, deadline: datetime, ahora: datetime, gracia_seg: int) -> bool:
    """True si ``ahora`` pasó el deadline MÁS la gracia.

    La gracia es tolerancia a latencia de red y desfasaje de reloj — NO tiempo
    de examen. Es un parámetro explícito del servidor; NUNCA se lee del cliente
    (regla dura #6). Dentro de la gracia (``deadline <= ahora <= deadline +
    gracia``) la rendición NO se considera vencida."""
    return ahora > deadline + timedelta(seconds=gracia_seg)
