"""Se puede DESHACER el marcado a mano, pero no inventar un estado.

Marcar a mano es una afirmación de una persona ("ya la cargué en el campus") y
las personas se equivocan de fila. Sin vuelta atrás, ese error quedaba fijo para
siempre y la nota figuraba como cargada sin estarlo.

Lo que NO se permite, y es el punto: poner "enviado" a mano. Ese estado
significa "el campus confirmó"; si se pudiera escribir, dejaría de haber forma
de saber qué notas llegaron de verdad. Corregir sí, engañar al sistema no.
"""

from __future__ import annotations

from app.application.moodle.marcado_manual import (
    ESTADOS_QUE_SE_PUEDEN_DESMARCAR,
    puede_desmarcarse,
)


def test_una_nota_marcada_a_mano_se_puede_desmarcar():
    assert puede_desmarcarse("manual") is True


def test_una_confirmacion_del_campus_NO_se_puede_tocar():
    """`enviado` lo puso el campus, no una persona. Deshacerlo sería borrar el
    único registro de que la nota llegó."""
    assert puede_desmarcarse("enviado") is False


def test_los_estados_del_sistema_no_se_editan_a_mano():
    # 'pendiente' y 'fallido' los pone el envío según lo que pasó. No hay nada
    # que desmarcar y tampoco se pueden fijar a dedo.
    assert puede_desmarcarse("pendiente") is False
    assert puede_desmarcarse("fallido") is False


def test_solo_manual_esta_en_la_lista():
    assert ESTADOS_QUE_SE_PUEDEN_DESMARCAR == frozenset({"manual"})
