"""C-74 post-cierre: aislamiento por comisión/materia entre docentes.

Dos bugs reales encontrados en vivo (sin tests previos, cero cobertura):

1. ``docente_de_materia()`` + comparación de identidad devolvía un docente
   ARBITRARIO (``.limit(1)``) de cualquier comisión de la materia y comparaba
   ESE contra el principal — un docente real de una comisión distinta a la que
   la query devolvía primero era rechazado con falso negativo (403 sobre su
   propio banco de preguntas).

2. ``crear-desde-banco`` solo validaba pertenencia a la MATERIA, nunca que el
   ``comision_id`` del body fuera una comisión que el docente realmente dicta
   — un docente de la Comisión 2 podía crear un examen apuntando a la
   Comisión 1 de otro docente, con solo compartir materia (y por lo tanto
   banco de preguntas).

Estos tests son puros de dominio (sin DB) — prueban las funciones de
autorización directamente con el booleano/id ya resuelto, tal como las
resuelve el repositorio real."""

from __future__ import annotations

import pytest

from app.domain.auth.authorization import (
    autorizar_docente_sobre_comision,
    autorizar_docente_sobre_materia,
)
from app.domain.auth.errors import ForbiddenError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol


def _principal(roles: tuple[Rol, ...], subject: str | None = "u1") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        username="DOC-1", email="doc@uni.edu", roles=roles, subject=subject
    )


# ---------------------------------------------------------------------------
# autorizar_docente_sobre_materia — bug 1 (falso negativo por docente arbitrario)
# ---------------------------------------------------------------------------


def test_docente_miembro_de_la_materia_pasa():
    """GREEN: si el repo resolvió que SÍ dicta alguna comisión de la materia, pasa."""
    autorizar_docente_sobre_materia(
        _principal((Rol.TUTOR,)), es_docente_de_alguna_comision_de_la_materia=True
    )


def test_docente_no_miembro_de_la_materia_es_rechazado():
    """RED→GREEN: si no dicta NINGUNA comisión de esa materia, 403 — esto es lo que
    fallaba antes: la comparación contra un docente arbitrario podía rechazar a un
    docente real por casualidad de qué comisión devolvía la query primero."""
    with pytest.raises(ForbiddenError):
        autorizar_docente_sobre_materia(
            _principal((Rol.TUTOR,)), es_docente_de_alguna_comision_de_la_materia=False
        )


def test_admin_no_esta_limitado_por_pertenencia_de_materia():
    """TRIANGULATE: alcance institucional no depende del booleano de membresía."""
    autorizar_docente_sobre_materia(
        _principal((Rol.ADMIN_SISTEMA,)), es_docente_de_alguna_comision_de_la_materia=False
    )


def test_sin_rol_tutor_ni_institucional_es_rechazado():
    with pytest.raises(ForbiddenError):
        autorizar_docente_sobre_materia(
            _principal((Rol.ESTUDIANTE,)), es_docente_de_alguna_comision_de_la_materia=True
        )


# ---------------------------------------------------------------------------
# autorizar_docente_sobre_comision — bug 2 (crear examen en comisión ajena)
# ---------------------------------------------------------------------------


def test_docente_dueno_de_la_comision_pasa():
    autorizar_docente_sobre_comision(
        _principal((Rol.TUTOR,), subject="doc-2"), docente_id_de_la_comision="doc-2"
    )


def test_docente_de_otra_comision_es_rechazado():
    """RED→GREEN: docente de la Comisión 2 no puede crear un examen que apunte a
    la Comisión 1 de otro docente, aunque compartan materia/banco."""
    with pytest.raises(ForbiddenError):
        autorizar_docente_sobre_comision(
            _principal((Rol.TUTOR,), subject="doc-2-comision-2"),
            docente_id_de_la_comision="doc-1-comision-1",
        )


def test_comision_sin_docente_no_la_reclama_un_docente():
    with pytest.raises(ForbiddenError):
        autorizar_docente_sobre_comision(
            _principal((Rol.TUTOR,), subject="cualquiera"),
            docente_id_de_la_comision=None,
        )


def test_admin_no_esta_limitado_por_pertenencia_de_comision():
    autorizar_docente_sobre_comision(
        _principal((Rol.ADMIN_SISTEMA,)), docente_id_de_la_comision="cualquier-docente"
    )
