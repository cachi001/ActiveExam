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

from collections.abc import Iterable
from datetime import datetime

from app.domain.exam_content.errors import ConfigExamenInvalidaError

# Campos de configuración que se CONGELAN una vez que el examen tiene >= 1
# intento finalizado: cambiarlos alteraría RETROACTIVAMENTE la nota o la equidad
# de quienes ya rindieron (mismo espíritu que el candado de selección de
# preguntas). Los controles de PUBLICACIÓN de resultados (mostrar_nota,
# revision_habilitada) quedan FUERA: liberar/ocultar la nota es un acto legítimo
# posterior a la rendición.
CAMPOS_CONGELADOS_POST_RENDICION: frozenset[str] = frozenset(
    {
        "tiempo_limite_min",
        "intentos_permitidos",
        "apertura",
        "cierre",
        "nota_maxima",
        "nota_aprobacion",
        "mezclar_preguntas",
    }
)


def campos_congelados_en_cambio(
    cambios: Iterable[str], *, ya_rendido: bool
) -> frozenset[str]:
    """Subconjunto de ``cambios`` que está congelado por rendición.

    Vacío si el examen aún no fue rendido (``ya_rendido=False``) o si ningún
    campo del cambio pertenece a ``CAMPOS_CONGELADOS_POST_RENDICION``."""
    if not ya_rendido:
        return frozenset()
    return frozenset(c for c in cambios if c in CAMPOS_CONGELADOS_POST_RENDICION)


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
    # C-69 (visibilidad de resultados): apertura y cierre son OBLIGATORIOS. El gate de
    # "mostrar nota/revisión al cerrar" depende de una fecha de cierre; sin ella el
    # alumno nunca vería la nota. Un examen siempre va de una fecha/hora a otra.
    if apertura is None or cierre is None:
        raise ConfigExamenInvalidaError(
            "apertura y cierre son obligatorios (el examen va de una fecha/hora a otra)."
        )
    if not (apertura < cierre):
        raise ConfigExamenInvalidaError(
            "apertura debe ser anterior a cierre."
        )
