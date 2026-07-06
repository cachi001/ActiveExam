"""C-69: gate de visibilidad de resultados (nota_visible / revision_visible).

Funciones PURAS (sin DB): la nota se muestra según mostrar_nota + cierre; la
revisión requiere estar habilitada Y que la nota ya sea visible.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.exam_content.visibilidad import nota_visible, revision_visible

_AHORA = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
_PASADO = _AHORA - timedelta(hours=1)
_FUTURO = _AHORA + timedelta(hours=1)


# --- nota_visible ---


def test_nota_inmediata_siempre_visible():
    assert nota_visible(mostrar_nota="inmediata", cierre=_FUTURO, ahora=_AHORA) is True
    assert nota_visible(mostrar_nota="inmediata", cierre=None, ahora=_AHORA) is True


def test_nota_al_cerrar_oculta_antes_del_cierre():
    assert nota_visible(mostrar_nota="al_cerrar", cierre=_FUTURO, ahora=_AHORA) is False


def test_nota_al_cerrar_visible_despues_del_cierre():
    assert nota_visible(mostrar_nota="al_cerrar", cierre=_PASADO, ahora=_AHORA) is True


def test_nota_al_cerrar_sin_cierre_nunca_visible():
    # Sin fecha de cierre, 'al_cerrar' no dispara → nota oculta (por eso las fechas
    # son obligatorias en la config).
    assert nota_visible(mostrar_nota="al_cerrar", cierre=None, ahora=_AHORA) is False


# --- revision_visible ---


def test_revision_requiere_habilitada():
    assert (
        revision_visible(
            revision_habilitada=False, mostrar_nota="inmediata", cierre=None, ahora=_AHORA
        )
        is False
    )


def test_revision_nunca_antes_que_la_nota():
    # Habilitada pero la nota aún no es visible (al_cerrar, antes del cierre) → False.
    assert (
        revision_visible(
            revision_habilitada=True, mostrar_nota="al_cerrar", cierre=_FUTURO, ahora=_AHORA
        )
        is False
    )


def test_revision_visible_habilitada_y_nota_visible():
    assert (
        revision_visible(
            revision_habilitada=True, mostrar_nota="al_cerrar", cierre=_PASADO, ahora=_AHORA
        )
        is True
    )


def test_revision_inmediata_habilitada_visible():
    assert (
        revision_visible(
            revision_habilitada=True, mostrar_nota="inmediata", cierre=_FUTURO, ahora=_AHORA
        )
        is True
    )
