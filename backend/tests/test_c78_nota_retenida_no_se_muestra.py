"""Una nota retenida por riesgo NO se le muestra al alumno (c-78).

## Lo que pidió el dueño

Que la nota venga oculta por defecto, que el profesor pueda publicarla, **y que
esa publicación no alcance si la nota está retenida por riesgo**.

## Lo que pasaba

`nota_visible()` solo miraba `mostrar_nota` y el cierre. Publicar hacía visible
la nota de TODOS, incluidos los alumnos cuya sesión superó el umbral y todavía
espera decisión humana. La pantalla la mostraba marcada "(preliminar)" con un
aviso.

Mostrar un número que puede anularse después es peor que no mostrar nada: el
alumno lo lee como su nota, y si el revisor la anula, el sistema le sacó algo que
ya le había dado. La regla dura #5 dice que la decisión es humana; hasta que
ocurra, no hay nota que mostrar.

## Lo que NO cambia

Con la nota ya revisada —aprobada o anulada— la retención desaparece y manda la
decisión: aprobada se ve, anulada se informa como anulada. Esto solo tapa la
ventana en la que nadie decidió todavía.

Y es server-side a propósito (regla dura #6): que la pantalla no lo dibuje no
alcanza, el número no tiene que salir del backend.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.exam_content.visibilidad import nota_visible, nota_visible_para_alumno

_AHORA = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
_CERRADO = _AHORA - timedelta(hours=1)


def test_publicada_y_sin_retencion_se_ve() -> None:
    assert (
        nota_visible_para_alumno(
            mostrar_nota="inmediata", cierre=None, ahora=_AHORA, retenido_por=None
        )
        is True
    )


def test_publicada_pero_EN_RIESGO_no_se_ve() -> None:
    """El caso que motivó el cambio: publicar no alcanza si nadie revisó."""
    assert (
        nota_visible_para_alumno(
            mostrar_nota="inmediata", cierre=None, ahora=_AHORA, retenido_por="en_riesgo"
        )
        is False
    )


def test_publicada_al_cerrar_pero_EN_RIESGO_tampoco() -> None:
    assert (
        nota_visible_para_alumno(
            mostrar_nota="al_cerrar",
            cierre=_CERRADO,
            ahora=_AHORA,
            retenido_por="en_riesgo",
        )
        is False
    )


def test_ANULADA_no_se_ve_como_nota() -> None:
    """Una nota anulada por fraude no se muestra como si fuera su nota. La
    pantalla informa la anulación por su propio camino (`nota_anulada`)."""
    assert (
        nota_visible_para_alumno(
            mostrar_nota="inmediata", cierre=None, ahora=_AHORA, retenido_por="anulada"
        )
        is False
    )


def test_retenida_por_falta_de_CAMINO_al_campus_si_se_ve() -> None:
    """`sin_destino` y `sin_credencial_docente` retienen el ENVÍO al campus, no
    la nota: el alumno rindió, la nota existe y está bien. Taparla porque el
    campus no tiene destino configurado sería castigarlo por un problema
    administrativo ajeno."""
    for motivo in ("sin_destino", "sin_credencial_docente"):
        assert (
            nota_visible_para_alumno(
                mostrar_nota="inmediata", cierre=None, ahora=_AHORA, retenido_por=motivo
            )
            is True
        ), motivo


def test_sin_publicar_no_se_ve_aunque_no_haya_retencion() -> None:
    """La retención SUMA al gate de publicación, no lo reemplaza."""
    assert (
        nota_visible_para_alumno(
            mostrar_nota="nunca", cierre=_CERRADO, ahora=_AHORA, retenido_por=None
        )
        is False
    )


def test_la_funcion_vieja_sigue_intacta() -> None:
    """`nota_visible` no cambia: decide la publicación del EXAMEN, que es una
    propiedad del examen y no de cada alumno. La retención es por sesión."""
    assert nota_visible(mostrar_nota="inmediata", cierre=None, ahora=_AHORA) is True
    assert nota_visible(mostrar_nota="nunca", cierre=_CERRADO, ahora=_AHORA) is False
