"""El resumen del examen tiene que decir de qué materia es, con el id.

Encontrado al conectar la edición del sorteo: la pantalla necesita el
`materia_id` para armar contra el banco de esa materia, y el resumen devolvía el
NOMBRE y el CÓDIGO pero no el id. El front lo mapeaba a null y la sección de
edición no se mostraba, sin ningún error visible.

Es el mismo patrón que ya mordió antes en este proyecto: un campo que el
front necesita y la respuesta no trae.
"""

from __future__ import annotations

from app.domain.exam_content.entities import ExamenContenidoResumen
from app.presentation.api.v1.exam_content._shared import _resumen_to_response


def test_el_resumen_expone_el_id_de_la_materia():
    resumen = ExamenContenidoResumen(
        id="ex-1",
        titulo="Parcial",
        cantidad_preguntas=10,
        comision_id="com-1",
        comision_nombre="Comisión 1",
        materia_id="mat-1",
        materia_nombre="Análisis Matemático I",
    )

    respuesta = _resumen_to_response(resumen)

    assert respuesta.materia_id == "mat-1"


def test_un_examen_sin_comision_no_tiene_materia():
    """D11: sin comisión no hay materia que derivar, y eso es válido."""
    resumen = ExamenContenidoResumen(id="ex-2", titulo="Suelto", cantidad_preguntas=0)

    respuesta = _resumen_to_response(resumen)

    assert respuesta.materia_id is None
