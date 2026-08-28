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


def puede_marcarse_cargada(retenido_por: str | list[str] | None) -> bool:
    """Si la nota de esa sesion se puede marcar como cargada a mano.

    ``retenido_por`` es el motivo que ya calcula
    ``resultados_query._motivos_retencion`` — se reusa en vez de recalcular un
    criterio propio, que es como se desincronizan las reglas.
    """
    # Acepta la lista completa de motivos (`_motivos_retencion` devuelve todos
    # los que aplican) o uno solo, por los llamadores viejos. Basta con que UNO
    # bloquee para que no se pueda marcar.
    motivos = (
        retenido_por
        if isinstance(retenido_por, list)
        else [retenido_por]
        if retenido_por
        else []
    )
    return not any(m in MOTIVOS_QUE_BLOQUEAN_MARCADO for m in motivos)


#: Los únicos estados que una persona puede DESHACER. Sólo `manual`, porque es
#: el único que puso una persona: marcar a mano es una afirmación ("ya la cargué
#: en el campus") y las personas se equivocan de fila.
#:
#: `enviado` NO está y es el punto de todo esto: lo puso el campus al confirmar.
#: Si se pudiera escribir o borrar a mano, dejaría de haber forma de saber qué
#: notas llegaron de verdad. `pendiente` y `fallido` los pone el envío según lo
#: que pasó — no hay nada que deshacer ahí, y tampoco se fijan a dedo.
ESTADOS_QUE_SE_PUEDEN_DESMARCAR = frozenset({"manual"})


def puede_desmarcarse(estado: str | None) -> bool:
    """¿Se puede volver atrás este estado? Corregir sí, inventar no."""
    return estado in ESTADOS_QUE_SE_PUEDEN_DESMARCAR
