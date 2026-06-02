"""Calculo de score de riesgo para sesiones de proctoring slim.

El score suma pesos por severidad de los eventos, alineado con ``riskWeights``
del frontend (C-45, D5). L2.5: el score solo PRIORIZA la cola de revision
humana — el backend NUNCA sanciona ni emite veredicto disciplinario.

Pesos (alineados con riskWeights del frontend):
  bajo    ->  5
  medio   -> 20
  alto    -> 50
  critico -> 100
"""

from __future__ import annotations

# Pesos por severidad — alineados con riskWeights del frontend (D5)
PESOS_SEVERIDAD: dict[str, int] = {
    "bajo": 5,
    "medio": 20,
    "alto": 50,
    "critico": 100,
}


def calcular_score(eventos: list) -> int:
    """Calcula el score de riesgo de una sesion sumando pesos por severidad.

    Args:
        eventos: Lista de objetos con atributo ``severidad`` (str).
            Acepta ProctoringEventModel o cualquier objeto duck-typed con
            campo ``severidad``.

    Returns:
        Score entero >= 0. Score 0 si no hay eventos o severidades desconocidas.

    Note:
        L2.5: el score SOLO prioriza la revision humana. El backend nunca sanciona.
    """
    return sum(PESOS_SEVERIDAD.get(getattr(e, "severidad", ""), 0) for e in eventos)
