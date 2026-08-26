"""c-78 — Crear un examen exige `crear_examenes`, no alcanza con ser tutor.

Encontrado el 26/8/2026 probando permisos contra producción: **el tutor podía
crear exámenes**. ``POST /exam-content/crear-desde-banco`` era el único endpoint
de creación sin ``require_capability`` propio, así que le alcanzaba con el guard
del router (``gestionar_academico``), que el tutor SÍ tiene.

Contradice la decisión explícita del dueño, que está escrita en la matriz de
capacidades: ``crear_examenes`` = {PROFESOR, COORDINADOR, ADMIN_SISTEMA}. El
tutor conserva ``gestionar_academico`` (leer su catálogo, inscribir, cerrar
notas) pero PIERDE la creación: armar el examen es trabajo del profesor, no de
quien lo dicta.

Y era incoherente además: el tutor no puede ver el banco (``gestionar_banco``,
403) pero podía crear un examen SACANDO preguntas de ese banco. O sea, generaba
un examen con contenido que no tiene permiso de mirar.

El alumno nunca pudo: lo frenaba el guard del router. El agujero era entre roles
de staff.
"""

from __future__ import annotations

import pytest

from app.domain.auth.capabilities import CAPABILITY_ROLES
from app.domain.auth.roles import Rol


def test_el_tutor_no_tiene_la_capacidad_de_crear_examenes():
    """La matriz es la fuente de verdad y ya decía esto: el endpoint no la respetaba."""
    assert Rol.TUTOR not in CAPABILITY_ROLES["crear_examenes"]


def test_quienes_si_pueden_crear_examenes():
    assert CAPABILITY_ROLES["crear_examenes"] == frozenset(
        {Rol.PROFESOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    )


def test_el_tutor_tampoco_gestiona_el_banco():
    """La incoherencia que delató el bug: sin acceso al banco, pero creando
    exámenes que salen del banco."""
    assert Rol.TUTOR not in CAPABILITY_ROLES["gestionar_banco"]


def test_el_tutor_conserva_lo_suyo():
    """Triangulación: el arreglo no puede pasarse de rosca.

    El tutor sigue con `gestionar_academico` — leer su catálogo, inscribir,
    cerrar notas son suyas. Sacarle la creación no le saca eso.
    """
    assert Rol.TUTOR in CAPABILITY_ROLES["gestionar_academico"]


def test_crear_desde_banco_declara_la_capacidad_correcta():
    """El endpoint tiene que EXIGIRLA, no solo que exista en la matriz.

    Se mira el código porque el bug era exactamente ese: la matriz estaba bien y
    el endpoint no la usaba. Un test sobre la matriz sola habría pasado en verde
    con el agujero abierto.
    """
    import inspect

    from app.presentation.api.v1.exam_content import catalog_router

    fuente = inspect.getsource(catalog_router)
    bloque = fuente.split('"/crear-desde-banco"')[1].split("async def")[0]
    assert 'require_capability("crear_examenes")' in bloque, (
        "crear-desde-banco no exige `crear_examenes`: le alcanza con el guard "
        "del router y el tutor entra"
    )
