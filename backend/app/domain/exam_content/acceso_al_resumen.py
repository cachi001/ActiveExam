"""Quién puede ver el encabezado (resumen) de un examen.

El endpoint respondía 200 a cualquier usuario autenticado: con el id del examen,
un alumno de otra materia leía título, materia, comisión, fechas y escala de
nota de una cátedra ajena. No filtraba preguntas ni notas, y el id no es
adivinable, así que el daño era acotado — pero rompía la regla que el resto del
sistema sí respeta (el listado no muestra exámenes ajenos, `/resultados`
responde 403).

La regla es una sola línea, pero vive acá y no dentro del endpoint para que se
pueda leer y probar sin levantar la aplicación.
"""

from __future__ import annotations


def puede_ver_el_resumen(
    *,
    tiene_pertenencia: bool,
    esta_inscripto: bool,
    sin_comision: bool = False,
) -> bool:
    """True si el examen es suyo: lo tiene a cargo, o lo va a rendir.

    ``sin_comision`` (D11) no habilita a nadie por sí solo: un examen suelto no
    tiene padrón contra el cual comprobar la inscripción, así que solo lo ve
    quien lo tenga a cargo.
    """
    if tiene_pertenencia:
        return True
    if sin_comision:
        return False
    return esta_inscripto
