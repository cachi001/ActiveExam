"""Probar el examen es un permiso sobre EL PROPIO examen, no sobre cualquiera.

Al saltearle la guarda de inscripción al staff quedó un agujero: esa guarda era
lo único que impedía que un docente creara una sesión sobre un examen de otra
materia. Sin ella, un tutor podía abrir "de prueba" el parcial de otra cátedra y
verle todas las preguntas antes de que se tome.

Y hay un caso peor, que además es real: un profesor que cursa otra materia tiene
rol de docente Y de estudiante. Si su rol alcanzara para marcar la rendición
como prueba, su parcial de verdad no contaría y no tendría nota.

Los dos se resuelven con lo mismo: la prueba solo aplica al examen propio. Sobre
uno ajeno, el staff es un alumno más y le corren todas las guardas.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

from app.application.proctoring.prueba_de_staff import es_rendicion_de_prueba


def test_el_rol_solo_no_alcanza_para_marcar_una_prueba():
    """La firma exige la pertenencia: no se puede llamar con el rol a secas.

    Es lo que evita el descuido de "tiene rol de profesor, entonces es prueba".
    """
    assert es_rendicion_de_prueba(["profesor"], es_examen_propio=True) is True
    assert es_rendicion_de_prueba(["profesor"], es_examen_propio=False) is False


def test_el_tutor_prueba_los_examenes_de_sus_comisiones():
    assert es_rendicion_de_prueba(["tutor"], es_examen_propio=True) is True


def test_el_tutor_no_prueba_el_examen_de_otra_catedra():
    """Vería las preguntas de un parcial ajeno antes de que se tome."""
    assert es_rendicion_de_prueba(["tutor"], es_examen_propio=False) is False


def test_el_profesor_que_cursa_otra_materia_rinde_de_verdad():
    """Su parcial de posgrado no es un ensayo: tiene que contar y tener nota."""
    assert (
        es_rendicion_de_prueba(["profesor", "estudiante"], es_examen_propio=False)
        is False
    )


def test_el_alumno_nunca_prueba_nada():
    assert es_rendicion_de_prueba(["estudiante"], es_examen_propio=True) is False
