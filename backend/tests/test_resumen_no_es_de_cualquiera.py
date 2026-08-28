"""El resumen de un examen es de quien tiene algo que ver con ese examen.

Encontrado revisando permisos: `GET /{examen_id}/resumen` respondía 200 a
CUALQUIER usuario autenticado. Un alumno de otra materia, con el id del examen,
leía título, materia, comisión, fechas y escala de nota de una cátedra ajena.

No filtra preguntas ni notas, y el id no es adivinable, así que el daño es
acotado — pero rompe la misma regla de pertenencia que respeta todo el resto:
el listado no muestra exámenes ajenos y `/resultados` responde 403.

La regla, en una función pura: lo ve el staff con pertenencia sobre el examen, o
el alumno inscripto en su comisión. Un examen sin comisión (D11) no tiene a
quién acotarlo, así que queda visible para el staff.
"""

from __future__ import annotations

from app.domain.exam_content.acceso_al_resumen import puede_ver_el_resumen


def test_el_staff_a_cargo_lo_ve():
    assert puede_ver_el_resumen(tiene_pertenencia=True, esta_inscripto=False) is True


def test_el_alumno_inscripto_lo_ve():
    """Es el encabezado de SU examen: sin esto no puede ni entrar a rendir."""
    assert puede_ver_el_resumen(tiene_pertenencia=False, esta_inscripto=True) is True


def test_un_alumno_de_otra_materia_no():
    assert puede_ver_el_resumen(tiene_pertenencia=False, esta_inscripto=False) is False


def test_un_docente_de_otra_catedra_tampoco():
    """Mismo caso: sin pertenencia y sin inscripción, no hay nada que mostrarle."""
    assert puede_ver_el_resumen(tiene_pertenencia=False, esta_inscripto=False) is False


def test_el_examen_sin_comision_lo_ve_el_staff():
    """D11: un examen suelto no tiene comisión a la que acotar la vista."""
    assert (
        puede_ver_el_resumen(
            tiene_pertenencia=True, esta_inscripto=False, sin_comision=True
        )
        is True
    )


def test_el_examen_sin_comision_no_se_lo_mostramos_a_un_alumno():
    assert (
        puede_ver_el_resumen(
            tiene_pertenencia=False, esta_inscripto=False, sin_comision=True
        )
        is False
    )
