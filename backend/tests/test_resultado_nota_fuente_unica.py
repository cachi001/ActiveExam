"""El resultado académico (aprobado/desaprobado/anulada) sale del BACKEND.

Estaba escrito dos veces con `if` encadenados: `veredictoNota` en el frontend y
`_veredicto` en el export. No eran un enum, eran texto suelto en dos lenguajes,
y YA habían divergido: la copia de Python no conocía la anulación, así que una
nota anulada por fraude salía "Aprobado" en el Excel mientras la pantalla decía
"Anulada". Verificado bajando el archivo el 28/8/2026.

Acá vive el enum, su etiqueta y su color. La pantalla y el archivo lo consumen;
ninguno de los dos decide nada.
"""

from __future__ import annotations

import pytest

from app.domain.exam_content.resultado_nota import (
    ResultadoNota,
    resultado_de,
    resultados_para_ui,
)


def test_aprobado_cuando_la_nota_llega_al_minimo():
    assert resultado_de(aprobado=True, nota=8.0, retenido_por=None) is ResultadoNota.APROBADO


def test_desaprobado_cuando_no_llega():
    assert resultado_de(aprobado=False, nota=3.0, retenido_por=None) is ResultadoNota.DESAPROBADO


def test_anulada_gana_sobre_la_nota_calculada():
    # La anulación es un veredicto humano que deja la nota efectiva en 0: el
    # número calculado ya no vale. Este es el caso que el export mostraba mal.
    assert (
        resultado_de(aprobado=True, nota=78.0, retenido_por="anulada")
        is ResultadoNota.ANULADA
    )


def test_en_revision_mientras_no_haya_veredicto_humano():
    # El resultado NO es definitivo: un revisor todavía puede anularlo. Decir
    # "Aprobado" sobre algo que puede darse vuelta es afirmar de más. La nota
    # igual se muestra en su columna, así que el número no se esconde.
    assert (
        resultado_de(aprobado=True, nota=91.0, retenido_por="en_riesgo")
        is ResultadoNota.EN_REVISION
    )


def test_la_anulacion_gana_sobre_en_revision():
    """Ya hubo veredicto: dejó de estar en revisión."""
    assert (
        resultado_de(aprobado=True, nota=91.0, retenido_por="anulada")
        is ResultadoNota.ANULADA
    )


def test_sin_nota_no_es_desaprobado():
    # Meter en el mismo bolsón a quien sacó 3 y a quien no rindió infla el
    # número de desaprobados, y ese número se informa.
    assert resultado_de(aprobado=None, nota=None, retenido_por=None) is ResultadoNota.SIN_NOTA


def test_con_nota_pero_sin_criterio_no_inventa_un_veredicto():
    # El examen no define con cuánto se aprueba: decir "desaprobado" sería una
    # afirmación que nadie hizo.
    assert (
        resultado_de(aprobado=None, nota=7.0, retenido_por=None)
        is ResultadoNota.SIN_CRITERIO
    )


@pytest.mark.parametrize("r", list(ResultadoNota))
def test_todos_tienen_etiqueta_legible_y_color(r: ResultadoNota):
    assert r.etiqueta and "_" not in r.etiqueta
    assert r.etiqueta[0].isupper()
    assert r.tono in {"neutral", "primary", "success", "warning", "error", "critico"}


def test_anulada_se_ve_mas_fuerte_que_desaprobado():
    """No son lo mismo: desaprobar es un resultado académico normal; una nota
    anulada por fraude es una decisión disciplinaria y tiene que saltar."""
    assert ResultadoNota.ANULADA.tono != ResultadoNota.DESAPROBADO.tono
    assert ResultadoNota.ANULADA.tono == "critico"


def test_el_catalogo_para_la_ui_trae_los_cinco_con_valor_etiqueta_y_tono():
    catalogo = resultados_para_ui()
    assert [c["valor"] for c in catalogo] == [r.value for r in ResultadoNota]
    for c in catalogo:
        assert c["etiqueta"] and c["tono"]
