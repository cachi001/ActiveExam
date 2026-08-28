"""El padrón de una comisión es de ALUMNOS.

Encontrado probando en el navegador (28/8/2026): `profesor1` figuraba inscripto
en la comisión de demo, y por eso aparecía en la tabla de notas de su propio
examen como ausente con 0 y desaprobado. Ninguno de los dos caminos de alta
—el panel del docente y la autoinscripción por código— miraba el rol.

La regla es por ROL, no por "no ser docente": un profesor que además cursa otra
materia tiene los dos roles y se puede inscribir. Lo que no se puede es inscribir
a alguien que no es alumno de nada.
"""

from __future__ import annotations

from app.domain.exam_content.padron import puede_estar_en_el_padron


def test_un_estudiante_se_inscribe():
    assert puede_estar_en_el_padron(["estudiante"]) is True


def test_un_profesor_no():
    assert puede_estar_en_el_padron(["profesor"]) is False


def test_un_tutor_no():
    assert puede_estar_en_el_padron(["tutor"]) is False


def test_un_admin_no():
    """El admin administra el padrón; no forma parte de él."""
    assert puede_estar_en_el_padron(["admin_sistema"]) is False


def test_el_docente_que_ademas_cursa_si():
    """Caso real: un profesor cursando un posgrado. Tiene los dos roles."""
    assert puede_estar_en_el_padron(["profesor", "estudiante"]) is True


def test_sin_roles_no():
    """Un usuario sin rol no es alumno de nada: no entra al padrón."""
    assert puede_estar_en_el_padron([]) is False


def test_un_rol_desconocido_no_alcanza():
    assert puede_estar_en_el_padron(["invitado"]) is False
