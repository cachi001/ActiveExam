"""Tests puros del congelamiento de configuración del examen tras rendición.

Regla (pedido del owner): una vez que el examen tiene >= 1 intento FINALIZADO,
los campos que alterarían retroactivamente la NOTA o la EQUIDAD de quienes ya
rindieron quedan CONGELADOS. Los controles de PUBLICACIÓN de resultados
(mostrar_nota, revision_habilitada) NO se congelan: liberar/ocultar notas es un
acto legítimo posterior a la rendición.

TDD: RED (helper no existe) → GREEN → TRIANGULATE (rendido/no-rendido, cada
campo congelado, campos libres).
"""

from __future__ import annotations

from app.domain.exam_content.config import (
    CAMPOS_CONGELADOS_POST_RENDICION,
    campos_congelados_en_cambio,
)


def test_no_rendido_no_congela_nada() -> None:
    cambios = {"tiempo_limite_min": 30, "nota_maxima": 10}
    assert campos_congelados_en_cambio(cambios, ya_rendido=False) == frozenset()


def test_rendido_congela_campo_de_nota() -> None:
    cambios = {"nota_maxima": 20}
    assert campos_congelados_en_cambio(cambios, ya_rendido=True) == frozenset(
        {"nota_maxima"}
    )


def test_rendido_congela_tiempo_intentos_y_mezclar() -> None:
    cambios = {
        "tiempo_limite_min": 30,
        "intentos_permitidos": 3,
        "mezclar_preguntas": True,
    }
    assert campos_congelados_en_cambio(cambios, ya_rendido=True) == frozenset(
        {"tiempo_limite_min", "intentos_permitidos", "mezclar_preguntas"}
    )


def test_rendido_no_congela_publicacion_de_resultados() -> None:
    # mostrar_nota y revision_habilitada quedan editables aun tras la rendición.
    cambios = {"mostrar_nota": "al_cerrar", "revision_habilitada": True}
    assert campos_congelados_en_cambio(cambios, ya_rendido=True) == frozenset()


def test_rendido_cambio_mixto_devuelve_solo_los_congelados() -> None:
    cambios = {"nota_aprobacion": 6, "mostrar_nota": "inmediatamente"}
    assert campos_congelados_en_cambio(cambios, ya_rendido=True) == frozenset(
        {"nota_aprobacion"}
    )


def test_ventana_apertura_cierre_se_congela() -> None:
    cambios = {"apertura": "x", "cierre": "y"}
    assert campos_congelados_en_cambio(cambios, ya_rendido=True) == frozenset(
        {"apertura", "cierre"}
    )


def test_conjunto_congelado_no_incluye_controles_de_publicacion() -> None:
    assert "mostrar_nota" not in CAMPOS_CONGELADOS_POST_RENDICION
    assert "revision_habilitada" not in CAMPOS_CONGELADOS_POST_RENDICION
    assert "tiempo_limite_min" in CAMPOS_CONGELADOS_POST_RENDICION
