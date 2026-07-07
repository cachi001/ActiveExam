"""Integridad de entrada del embedding de referencia (C-70 hardening, RN-BIO).

El endpoint de enrollment recibe el embedding 128-d del cliente (cliente = sensor
no confiable, regla dura de dominio #6). SIN re-inferencia server-side (fuera de
alcance de C-70 — sería un change propio del linaje C-56/C-09), esta validación
PURA rechaza los vectores inyectados triviales:
  - componentes no finitos (NaN / ±inf),
  - norma cero (todo-ceros / vector degenerado — cosine no comparable),
  - magnitudes absurdas por componente (overflow / basura),
  - el vector FAKE de desarrollo (el bypass de captura, que es solo-dev).

Lo que esta validación NO hace (y no puede, sin re-inferir): verificar IDENTIDAD.
Un descriptor real de OTRA persona sigue pasando — esa defensa es la re-inferencia
server-side, explícitamente fuera de alcance. Acá subimos el piso: la inyección
trivial (consola/curl con un vector cualquiera, ceros, o el fake de dev) se corta.

PUREZA: solo aritmética sobre secuencias de floats (stdlib ``math``); sin numpy,
sin DB, sin cripto. Testeable con cualquier pytest.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

# Cota de magnitud generosa por componente. Los descriptores ``face-api-128d``
# viven en ~[-0.3, 0.3]; los tests sintéticos existentes de enrollment usan
# valores <= 1.0. 10.0 es ~30x el máximo real observado → CERO falsos rechazos,
# mientras corta magnitudes absurdas (p. ej. overflow inyectado 1e30).
MAX_ABS_COMPONENTE = 10.0


class EmbeddingIntegridadError(ValueError):
    """El embedding no supera la validación de integridad de entrada (C-70)."""


def _es_vector_fake_dev(embedding: Sequence[float]) -> bool:
    """True si el embedding es el vector FAKE de desarrollo.

    Reproduce ``FAKE_EMBEDDING_128D`` del front (``devConfig.ts``):
    ``Array.from({length:128}, (_, i) => Math.sin(i + 1))``. Comparación con
    tolerancia de floats. Ese vector NUNCA debe poder enrolarse en producción
    (el flag de bypass de captura es solo-dev; ``import.meta.env.DEV`` lo apaga
    en el build de prod, pero el backend no debe confiar en eso).
    """
    return all(
        math.isclose(x, math.sin(i + 1), abs_tol=1e-9)
        for i, x in enumerate(embedding)
    )


def validar_integridad_embedding(embedding: Sequence[float]) -> None:
    """Valida la integridad de entrada de un embedding de referencia (C-70).

    NO valida la dimensión (eso lo hace ``DimensionError`` en el service, antes)
    ni la identidad. Solo integridad estructural.

    Raises:
        EmbeddingIntegridadError: hay componentes no finitos (NaN/inf); la norma
            es cero (todo-ceros/degenerado); algún componente excede
            ``MAX_ABS_COMPONENTE``; o es el vector FAKE de desarrollo.
    """
    if any(not math.isfinite(x) for x in embedding):
        raise EmbeddingIntegridadError(
            "El embedding contiene valores no finitos (NaN/inf)."
        )
    if any(abs(x) > MAX_ABS_COMPONENTE for x in embedding):
        raise EmbeddingIntegridadError(
            "El embedding tiene componentes de magnitud implausible."
        )
    if math.sqrt(sum(x * x for x in embedding)) == 0.0:
        raise EmbeddingIntegridadError(
            "El embedding tiene norma cero (vector degenerado)."
        )
    if embedding and _es_vector_fake_dev(embedding):
        raise EmbeddingIntegridadError(
            "El embedding coincide con el vector de desarrollo (no válido)."
        )
