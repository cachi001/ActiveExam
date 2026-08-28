"""Probar el examen antes de soltarlo, sin ensuciar las notas.

Un examen en borrador existe para eso, pero el docente no podía rendirlo: la
guarda de inscripción (C-71) lo frena porque nunca está inscripto como alumno de
su propia comisión. Al destrabarlo aparece el problema real: su rendición
quedaría como una más y el docente figuraría en la tabla de resultados, en las
estadísticas y en el write-back a Moodle.

La marca la pone el servidor a partir del rol (regla dura #6: el cliente es un
sensor no confiable — si viniera del body, un alumno pediría que su rendición no
cuente).

Decisión del dueño (28/8/2026): el TUTOR también puede probar, aunque no pueda
crear exámenes. Por eso el corte es `gestionar_academico` y no `crear_examenes`.

Acá se fija la parte del ROL, con el examen ya dado por propio. Que además tenga
que ser SU examen lo cubre `test_prueba_solo_del_examen_propio`.
"""

from __future__ import annotations

from app.application.proctoring.prueba_de_staff import (
    ROLES_QUE_PUEDEN_PROBAR,
    es_rendicion_de_prueba,
)


def test_el_profesor_que_arma_el_examen_puede_probarlo():
    assert es_rendicion_de_prueba(["profesor"], es_examen_propio=True) is True


def test_el_tutor_tambien(  ):
    """No crea exámenes, pero acompaña la comisión y necesita ver qué se toma."""
    assert es_rendicion_de_prueba(["tutor"], es_examen_propio=True) is True


def test_el_coordinador_y_el_admin_tambien():
    assert es_rendicion_de_prueba(["coordinador"], es_examen_propio=True) is True
    assert es_rendicion_de_prueba(["admin_sistema"], es_examen_propio=True) is True


def test_el_alumno_rinde_de_verdad():
    """Lo que decide que una rendición NO cuente no puede ser pedible por el alumno."""
    assert es_rendicion_de_prueba(["estudiante"], es_examen_propio=True) is False


def test_sin_roles_rinde_de_verdad():
    assert es_rendicion_de_prueba([], es_examen_propio=True) is False


def test_un_rol_desconocido_no_habilita_la_prueba():
    """Ante un rol que no existe, la opción segura es contar la rendición."""
    assert es_rendicion_de_prueba(["rol_inventado"], es_examen_propio=True) is False


def test_alcanza_con_uno_de_sus_roles():
    assert es_rendicion_de_prueba(["estudiante", "tutor"], es_examen_propio=True) is True


def test_el_revisor_no_prueba_examenes():
    """Quien juzga el fraude no arma ni ensaya el examen (separación de roles)."""
    assert "revisor" not in ROLES_QUE_PUEDEN_PROBAR
