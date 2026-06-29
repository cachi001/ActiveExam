"""Validación de la configuración del examen POR EXAMEN (C-69, migración 0032).

Reglas de dominio (→ 422 en la capa HTTP):
- intentos_permitidos >= 1.
- nota_maxima > 0.
- 0 <= nota_aprobacion <= nota_maxima.
- si apertura y cierre están ambos seteados → apertura < cierre.
- tiempo_limite_min: null (sin límite) o > 0.

Función PURA: recibe los valores FINALES (ya mergeados en un update parcial) y
eleva ``ConfigExamenInvalidaError`` ante la primera violación.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.exam_content.errors import ConfigExamenInvalidaError


def validar_config_examen(
    *,
    tiempo_limite_min: int | None,
    intentos_permitidos: int,
    apertura: datetime | None,
    cierre: datetime | None,
    nota_maxima: float,
    nota_aprobacion: float,
) -> None:
    """Valida la config final del examen; eleva ConfigExamenInvalidaError si falla."""
    if intentos_permitidos < 1:
        raise ConfigExamenInvalidaError(
            f"intentos_permitidos debe ser >= 1; se recibió {intentos_permitidos}."
        )
    if nota_maxima <= 0:
        raise ConfigExamenInvalidaError(
            f"nota_maxima debe ser > 0; se recibió {nota_maxima}."
        )
    if nota_aprobacion < 0 or nota_aprobacion > nota_maxima:
        raise ConfigExamenInvalidaError(
            f"nota_aprobacion debe estar en [0, nota_maxima]; se recibió "
            f"{nota_aprobacion} (nota_maxima={nota_maxima})."
        )
    if tiempo_limite_min is not None and tiempo_limite_min <= 0:
        raise ConfigExamenInvalidaError(
            f"tiempo_limite_min debe ser null o > 0; se recibió {tiempo_limite_min}."
        )
    if apertura is not None and cierre is not None and not (apertura < cierre):
        raise ConfigExamenInvalidaError(
            "apertura debe ser anterior a cierre cuando ambos están seteados."
        )
