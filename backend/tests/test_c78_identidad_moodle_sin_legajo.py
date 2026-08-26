"""c-78 — Identificar al alumno en Moodle SIN legajo (decisión del dueño, 26/8/2026).

    "NO HAY LEGAJO, hay userid de moodle, username ES USERNAME"

El write-back buscaba al alumno por ``idnumber`` (el legajo). En este campus los
alumnos **no tienen legajo cargado**: verificado contra el campus real, el
usuario de prueba tiene ``idnumber: None``. Buscar por ahí no encuentra a nadie.

Lo que sí existe siempre:

  - el **userid de Moodle**, que el propio Moodle nos manda en cada launch LTI
    (el claim ``sub``). Es el identificador más fuerte: es la clave primaria del
    usuario del otro lado, no cambia y no se repite.
  - el **username** del campus.
  - el **email**.

Orden de resolución: userid de Moodle → username → email. El userid gana porque
es exacto; el email va último porque es el más fácil de que alguien edite o
comparta (cuentas de cátedra).

Y el ``sub`` del launch se guarda al provisionar: hoy se tiraba, y era el dato
más útil que Moodle nos daba.
"""

from __future__ import annotations

import pytest

from app.application.moodle.identidad_alumno import (
    IdentidadAlumno,
    candidatos_de_busqueda,
)


def test_el_userid_de_moodle_va_primero():
    ident = IdentidadAlumno(
        moodle_userid=968, username="alumno_prueba2", email="a@b.edu"
    )

    assert candidatos_de_busqueda(ident)[0] == ("moodle_userid", "968")


def test_sin_userid_busca_por_username():
    ident = IdentidadAlumno(moodle_userid=None, username="alumno_prueba2", email="a@b.edu")

    campos = [c for c, _ in candidatos_de_busqueda(ident)]

    assert campos[0] == "username"


def test_el_email_queda_ultimo():
    """Es el más fácil de que alguien edite o comparta (cuentas de cátedra)."""
    ident = IdentidadAlumno(moodle_userid=968, username="alumno_prueba2", email="a@b.edu")

    campos = [c for c, _ in candidatos_de_busqueda(ident)]

    assert campos[-1] == "email"


def test_no_propone_buscar_por_legajo():
    """La decisión del dueño: acá no hay legajo. Buscar por ahí es un viaje al
    vacío que se come un pedido al campus y devuelve cero."""
    ident = IdentidadAlumno(moodle_userid=968, username="u", email="a@b.edu")

    campos = [c for c, _ in candidatos_de_busqueda(ident)]

    assert "idnumber" not in campos


def test_saltea_los_datos_que_no_estan():
    ident = IdentidadAlumno(moodle_userid=None, username="", email="a@b.edu")

    assert candidatos_de_busqueda(ident) == [("email", "a@b.edu")]


def test_sin_ningun_dato_no_hay_nada_que_buscar():
    """Mejor no consultar que consultar con vacío: Moodle devolvería cualquier
    cosa o un error que después se lee como "el alumno no existe"."""
    ident = IdentidadAlumno(moodle_userid=None, username=None, email=None)

    assert candidatos_de_busqueda(ident) == []


def test_el_username_se_limpia_de_espacios():
    ident = IdentidadAlumno(moodle_userid=None, username="  alumno_prueba2  ", email=None)

    assert candidatos_de_busqueda(ident) == [("username", "alumno_prueba2")]


def test_no_confunde_el_username_sintetico_de_lti_con_uno_del_campus():
    """`lti:1:7` es la clave interna del provisioning, no un usuario de Moodle.

    Mandarla al campus garantiza cero resultados y encima deja ese valor en los
    logs del campus como si fuera un usuario real.
    """
    ident = IdentidadAlumno(moodle_userid=7, username="lti:1:7", email="a@b.edu")

    campos = [c for c, _ in candidatos_de_busqueda(ident)]

    assert "username" not in campos
    assert campos == ["moodle_userid", "email"]


@pytest.mark.parametrize("crudo, esperado", [(7, "7"), ("7", "7"), ("  7 ", "7")])
def test_el_userid_se_normaliza_a_texto(crudo, esperado):
    """El `sub` del launch llega como texto y la API lo quiere como texto."""
    ident = IdentidadAlumno(moodle_userid=crudo, username=None, email=None)

    assert candidatos_de_busqueda(ident) == [("moodle_userid", esperado)]


def test_un_userid_que_no_es_numero_se_descarta():
    """Otro Platform podría mandar un `sub` no numérico; el userid de Moodle
    siempre es un entero."""
    ident = IdentidadAlumno(moodle_userid="abc-def", username=None, email="a@b.edu")

    assert candidatos_de_busqueda(ident) == [("email", "a@b.edu")]
