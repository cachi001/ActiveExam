"""Calculo de score de riesgo para sesiones de proctoring slim.

Motor SIMPLE: suma directa de pesos por tipo de evento. Lo usa el endpoint del
detalle de sesion (vista del proctor) — devuelve el score on-the-fly sin
persistir. L2.5: el score solo PRIORIZA la cola de revision humana — el backend
NUNCA sanciona ni emite veredicto disciplinario.

COEXISTENCIA INTENCIONAL con ``app.domain.scoring.risk_score`` (motor del cierre,
``score_correlacionado``): ambos leen de la MISMA fuente de pesos
(``evento_score_config`` via ConfigService.scoring_weights). La diferencia es la
forma de combinar: el motor de cierre suma + correlacion + bono por persistencia
(el "score final" persistido); este suma directa (el "score on-the-fly" del
proctor). Coinciden en el peso base; difieren en bonos.

Fallback por severidad: red de seguridad si la config no esta disponible. Las
severidades canonicas (alineadas con ``evento_score_config`` y el dominio) son
``baja``, ``media``, ``alta``, ``critica`` — la severidad ``baseline`` NO suma
(es el piso 0 del score, no un evento). Los pesos de fallback estan en el centro
de los rangos institucionales por severidad (``SEVERITY_RANGES``).
"""

from __future__ import annotations

# Fallback por severidad (RN-GLB-03 — solo si la config persistida no esta). Los
# valores son el centro del rango institucional definido en
# ``app/domain/scoring/risk_score.SEVERITY_RANGES``:
#   baja    [1-10]   -> 5
#   media   [11-30]  -> 20
#   alta    [31-60]  -> 45
#   critica [61-100] -> 80
# baseline no es un evento (no suma al score).
PESOS_SEVERIDAD: dict[str, int] = {
    "baja": 5,
    "media": 20,
    "alta": 45,
    "critica": 80,
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
