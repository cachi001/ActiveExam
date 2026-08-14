"""Grupo 11 — Tests de validación declarativa nota_aprobacion <= nota_maxima.

TDD Cycle: RED → GREEN → TRIANGULATE → REFACTOR
Sin mocks de DB (regla dura #4): los schemas Pydantic se testean en memoria pura,
sin sesión de base de datos — correcto porque la validación ocurre en el schema,
antes de llegar a cualquier capa de persistencia.

Scenarios del spec (validacion-nota-examen/spec.md):
  S1: Rechazo en creación cuando aprobacion > maxima
  S2: Aceptación cuando aprobacion <= maxima
  S3: PATCH parcial con un solo campo no dispara la validación cruzada
  S4: Campos no declarados siguen rechazados (extra='forbid')
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.presentation.api.v1.exam_content.schemas import (
    CrearDesdebancoRequest,
    ExamenConfigPatchRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sorteo_minimo() -> list[dict]:
    """Sorteo mínimo válido para CrearDesdebancoRequest."""
    return [{"categoria_id": "cat-001", "cantidad": 5}]


# ===========================================================================
# S1 — Rechazo en creación cuando nota_aprobacion > nota_maxima
# ===========================================================================

class TestCrearDesdebancoValidacion:

    def test_red_creacion_rechaza_aprobacion_mayor_que_maxima(self):
        """S1: aprobacion=80 > maxima=60 → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CrearDesdebancoRequest(
                titulo="Examen prueba",
                materia_id="mat-001",
                sorteo=_sorteo_minimo(),
                nota_maxima=60.0,
                nota_aprobacion=80.0,
            )
        errors = exc_info.value.errors()
        assert any("nota_aprobacion" in str(e) for e in errors)

    def test_green_creacion_acepta_aprobacion_igual_a_maxima(self):
        """S2 (caso límite): aprobacion == maxima → OK."""
        req = CrearDesdebancoRequest(
            titulo="Examen prueba",
            materia_id="mat-001",
            sorteo=_sorteo_minimo(),
            nota_maxima=60.0,
            nota_aprobacion=60.0,
        )
        assert req.nota_aprobacion == 60.0
        assert req.nota_maxima == 60.0

    def test_green_creacion_acepta_aprobacion_menor_que_maxima(self):
        """S2: aprobacion=60 < maxima=100 → OK (caso canónico)."""
        req = CrearDesdebancoRequest(
            titulo="Examen prueba",
            materia_id="mat-001",
            sorteo=_sorteo_minimo(),
            nota_maxima=100.0,
            nota_aprobacion=60.0,
        )
        assert req.nota_aprobacion == 60.0
        assert req.nota_maxima == 100.0

    # Triangulación — segunda forma del rechazo
    def test_triangulo_creacion_rechaza_aprobacion_100_maxima_90(self):
        """S1 variante: aprobacion=100 > maxima=90 → también rechazado."""
        with pytest.raises(ValidationError):
            CrearDesdebancoRequest(
                titulo="Examen prueba",
                materia_id="mat-001",
                sorteo=_sorteo_minimo(),
                nota_maxima=90.0,
                nota_aprobacion=100.0,
            )

    def test_triangulo_creacion_acepta_defaults(self):
        """S2: defaults (100/60) son coherentes → OK."""
        req = CrearDesdebancoRequest(
            titulo="Examen prueba",
            materia_id="mat-001",
            sorteo=_sorteo_minimo(),
        )
        assert req.nota_aprobacion <= req.nota_maxima

    def test_s4_campo_extra_rechazado_en_creacion(self):
        """S4: extra='forbid' → campo desconocido devuelve ValidationError."""
        with pytest.raises(ValidationError):
            CrearDesdebancoRequest(
                titulo="Examen prueba",
                materia_id="mat-001",
                sorteo=_sorteo_minimo(),
                campo_inventado="no debería pasar",
            )


# ===========================================================================
# S3 — PATCH parcial: la cruzada solo dispara con ambos campos presentes
# ===========================================================================

class TestExamenConfigPatchRequestValidacion:

    def test_red_patch_rechaza_aprobacion_mayor_que_maxima_cuando_ambos_presentes(self):
        """S1 PATCH: ambos campos → se valida y rechaza si aprobacion > maxima."""
        with pytest.raises(ValidationError) as exc_info:
            ExamenConfigPatchRequest(
                nota_maxima=50.0,
                nota_aprobacion=80.0,
            )
        errors = exc_info.value.errors()
        assert any("nota_aprobacion" in str(e) for e in errors)

    def test_green_patch_acepta_ambos_campos_coherentes(self):
        """S2 PATCH: ambos presentes y coherentes → OK."""
        req = ExamenConfigPatchRequest(
            nota_maxima=100.0,
            nota_aprobacion=60.0,
        )
        assert req.nota_aprobacion == 60.0
        assert req.nota_maxima == 100.0

    def test_s3_patch_solo_nota_maxima_no_dispara_cruzada(self):
        """S3: solo nota_maxima → sin nota_aprobacion → NO dispara validación cruzada."""
        req = ExamenConfigPatchRequest(nota_maxima=80.0)
        assert req.nota_maxima == 80.0
        assert req.nota_aprobacion is None  # no vino en el body

    def test_s3_patch_solo_nota_aprobacion_no_dispara_cruzada(self):
        """S3 variante: solo nota_aprobacion → sin nota_maxima → NO dispara."""
        req = ExamenConfigPatchRequest(nota_aprobacion=40.0)
        assert req.nota_aprobacion == 40.0
        assert req.nota_maxima is None

    def test_s3_patch_body_vacio_no_dispara_cruzada(self):
        """S3: body completamente vacío → sin ningún campo de nota → OK."""
        req = ExamenConfigPatchRequest()
        assert req.nota_aprobacion is None
        assert req.nota_maxima is None

    # Triangulación — segunda variante de rechazo en PATCH
    def test_triangulo_patch_rechaza_aprobacion_1_mayor_maxima_0_5(self):
        """S1 PATCH variante: aprobacion=1.0 > maxima=0.5 → rechazado."""
        with pytest.raises(ValidationError):
            ExamenConfigPatchRequest(
                nota_maxima=0.5,
                nota_aprobacion=1.0,
            )

    def test_s4_campo_extra_rechazado_en_patch(self):
        """S4: extra='forbid' en PATCH → campo inventado devuelve ValidationError."""
        with pytest.raises(ValidationError):
            ExamenConfigPatchRequest(campo_no_existe=True)
