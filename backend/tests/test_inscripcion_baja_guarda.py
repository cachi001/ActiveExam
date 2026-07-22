"""Guarda de baja de inscripción: no dar de baja a un alumno que ya rindió.

Si el alumno tiene una sesión de examen en la comisión, la baja se bloquea
(huerfanaría sesión/evidencia/nota — cadena de custodia). Se prueba la lógica del
servicio con un repo fake (puerto), sin mockear la DB: la consulta real vive en el
repo y se cubre en los tests de integración.
"""

from __future__ import annotations

import pytest

from app.application.exam_content.errors import (
    InscripcionConActividadError,
    InscripcionNoEncontradaError,
)
from app.application.exam_content.inscripcion_service import InscripcionService


class _FakeInscRepo:
    def __init__(self, *, rindio: bool, existe: bool = True) -> None:
        self._rindio = rindio
        self._existe = existe
        self.eliminado = False

    async def alumno_rindio_en_comision(self, usuario_id: str, comision_id: str) -> bool:
        return self._rindio

    async def eliminar(self, usuario_id: str, comision_id: str) -> bool:
        self.eliminado = True
        return self._existe


def _svc(repo: _FakeInscRepo) -> InscripcionService:
    return InscripcionService(repo, comision_repo=None, consent_repo=None, embedding_repo=None)


@pytest.mark.asyncio
async def test_baja_bloqueada_si_el_alumno_ya_rindio():
    repo = _FakeInscRepo(rindio=True)
    with pytest.raises(InscripcionConActividadError):
        await _svc(repo).eliminar("comision-1", "usuario-1")
    assert repo.eliminado is False  # NUNCA se borró la inscripción


@pytest.mark.asyncio
async def test_baja_procede_si_no_hay_actividad():
    repo = _FakeInscRepo(rindio=False, existe=True)
    await _svc(repo).eliminar("comision-1", "usuario-1")
    assert repo.eliminado is True


@pytest.mark.asyncio
async def test_baja_sin_actividad_pero_inexistente_da_no_encontrada():
    repo = _FakeInscRepo(rindio=False, existe=False)
    with pytest.raises(InscripcionNoEncontradaError):
        await _svc(repo).eliminar("comision-1", "usuario-1")
