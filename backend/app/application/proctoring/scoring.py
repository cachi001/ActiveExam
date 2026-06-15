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


def calcular_score(
    eventos: list, pesos_por_tipo: dict[str, int] | None = None
) -> int:
    """Calcula el score de riesgo de una sesion sumando pesos por evento.

    Si ``pesos_por_tipo`` esta presente (pesos VIVOS de la config persistida,
    ``evento_score_config`` via ConfigService), cada evento aporta el peso de su
    ``tipo``; si el tipo no esta en el mapa vivo, cae al peso por severidad como red
    de seguridad de degradacion (RN-GLB-03). Sin ``pesos_por_tipo`` (config ausente)
    usa SOLO la red de seguridad por severidad — nunca como fuente normal.

    Args:
        eventos: Lista de objetos duck-typed con ``severidad`` (y opcionalmente
            ``tipo``). Acepta ProctoringEventModel.
        pesos_por_tipo: Mapa ``{tipo_evento: peso}`` vivo desde la config. None =
            sin config (fallback por severidad).

    Returns:
        Score entero >= 0. Score 0 si no hay eventos o el peso no se resuelve.

    Note:
        L2.5: el score SOLO prioriza la revision humana. El backend nunca sanciona.
    """
    pesos = pesos_por_tipo or {}
    total = 0
    for e in eventos:
        tipo = getattr(e, "tipo", "")
        if tipo and tipo in pesos:
            total += pesos[tipo]
        else:
            total += PESOS_SEVERIDAD.get(getattr(e, "severidad", ""), 0)
    return total
