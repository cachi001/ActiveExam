"""c-78 — Una respuesta cloze mal formada se rechaza, no tumba la entrega.

Encontrado el 26/8/2026 probando la devolución de notas contra producción. Al
guardar las respuestas de un cloze, el valor de cada blank tiene que ser el **id
de la opción elegida**. Si en vez del id llega otra cosa (el TEXTO de la opción,
por ejemplo), el valor viaja hasta una comparación contra una columna ``uuid`` de
Postgres y revienta.

El síntoma era peor que el error: ``POST /respuestas`` devolvía **201** — como si
hubiera guardado bien — y la explosión aparecía después, al **entregar**. O sea
que el alumno terminaba el examen, apretaba entregar, y no podía. Su sesión
quedaba ``no_finalizada`` y sin nota.

Que el cliente propio nunca mande el texto no alcanza: un reintento con datos
viejos, una extensión del navegador o un buffer que se drena tarde pueden
mandarlo, y el momento en que rompe es el peor posible.

Se valida al ENTRAR: si el valor de un blank de opción múltiple no es un id,
se rechaza con 422 ahí mismo y la sesión sigue entera.
"""

from __future__ import annotations

import pytest

from app.presentation.api.v1.proctoring.sessions.schemas import (
    RespuestaItem,
    valor_de_blank_es_id,
)


def test_un_uuid_es_un_valor_valido():
    assert valor_de_blank_es_id("a404cfc3-35af-4459-8c29-b64d603e2c19") is True


def test_el_texto_de_la_opcion_no_es_un_valor_valido():
    """El caso real: llegó `int(texto)` donde iba el id de la opción."""
    assert valor_de_blank_es_id("int(texto)") is False


def test_vacio_es_valido_porque_significa_sin_responder():
    """Un blank sin contestar es legítimo: el alumno puede dejarlo en blanco."""
    assert valor_de_blank_es_id("") is True
    assert valor_de_blank_es_id(None) is True


def test_una_respuesta_escrita_libre_no_se_rechaza():
    """Los blanks de respuesta ESCRITA guardan texto, no ids: si se los tratara
    como uuid, se rompería el otro tipo de pregunta."""
    item = RespuestaItem(
        pregunta_id="11111111-1111-1111-1111-111111111111",
        respuesta_cloze={"22222222-2222-2222-2222-222222222222": "commit"},
        blanks_de_texto=["22222222-2222-2222-2222-222222222222"],
    )
    assert item.respuesta_cloze is not None


def test_un_id_de_blank_que_no_es_uuid_tambien_se_rechaza():
    """La CLAVE del dict también viaja a una columna uuid."""
    with pytest.raises(ValueError):
        RespuestaItem(
            pregunta_id="11111111-1111-1111-1111-111111111111",
            respuesta_cloze={"no-es-un-blank": "a404cfc3-35af-4459-8c29-b64d603e2c19"},
        )


def test_el_texto_como_valor_se_rechaza_al_construir_la_respuesta():
    """La barrera que faltaba: esto devolvía 201 y explotaba recién al entregar."""
    with pytest.raises(ValueError):
        RespuestaItem(
            pregunta_id="11111111-1111-1111-1111-111111111111",
            respuesta_cloze={
                "22222222-2222-2222-2222-222222222222": "int(texto)",
            },
        )


def test_una_respuesta_normal_de_opcion_unica_sigue_funcionando():
    item = RespuestaItem(
        pregunta_id="11111111-1111-1111-1111-111111111111",
        opcion_elegida_id="33333333-3333-3333-3333-333333333333",
    )
    assert item.opcion_elegida_id is not None
