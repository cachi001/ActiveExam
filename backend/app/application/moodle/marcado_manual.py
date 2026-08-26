"""Cuando se puede afirmar a mano que una nota ya se cargo en el campus (c-78).

`PATCH /{examen_id}/resultados/{session_id}/marcar-cargada` existe para el campus
sin API: la nota se carga a mano y alguien afirma que ya la cargo, para que la
fila deje de decir "pendiente" para siempre.

El hueco que cierra este modulo: esa accion no miraba la RETENCION. El
sincronizado automatico si la respeta —`_motivos_retencion` marca `en_riesgo` y
`anulada`, y apretar "Sincronizar" no las manda—, asi que se podia marcar a mano
exactamente lo que el sistema se niega a mandar solo.

Eso rompe la regla dura #5 por la puerta de atras: el sistema retiene la nota
esperando una decision humana sobre la integridad, y la accion la daba por
entregada sin que esa decision existiera.
"""

from __future__ import annotations

#: Motivos de retencion que BLOQUEAN el marcado manual. Son los de INTEGRIDAD: la
#: nota espera una decision humana y afirmar que se cargo la saltea.
#:
#: Se listan los que bloquean, no los que dejan pasar, a proposito. Los otros
#: motivos que existen hoy —`sin_destino`, `sin_credencial_docente`— retienen el
#: envio AUTOMATICO por falta de camino al campus, y son justamente los casos en
#: que cargar a mano es lo correcto: bloquearlos romperia la funcionalidad. Un
#: motivo nuevo suele ser de esa familia, asi que el default es dejar pasar.
MOTIVOS_QUE_BLOQUEAN_MARCADO = frozenset({"en_riesgo", "anulada"})


def puede_marcarse_cargada(retenido_por: str | None) -> bool:
    """Si la nota de esa sesion se puede marcar como cargada a mano.

    ``retenido_por`` es el motivo que ya calcula
    ``resultados_query._motivos_retencion`` — se reusa en vez de recalcular un
    criterio propio, que es como se desincronizan las reglas.
    """
    return retenido_por not in MOTIVOS_QUE_BLOQUEAN_MARCADO
