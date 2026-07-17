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

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from app.domain.exam_content.errors import ConfigExamenInvalidaError

# DEPRECADO (C-72 §6): candado BINARIO. Reemplazado por el modelo de tres grupos
# (`cambios_bloqueados` + CONGELADO_DURO/CAMPOS_DIRECCIONALES/CAMPOS_LIBRES, más
# abajo). Se conserva como shim hasta que el router de `PATCH /config` migre al
# modelo direccional (§6.10, integración). No agregar usos nuevos.
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


# C-72 §6 — Candado DIRECCIONAL post-rendición (reemplaza el binario de arriba).
# Tres grupos según qué le hace el cambio a quienes YA rindieron:
#   - CONGELADO DURO: reescribe retroactivamente la nota o la equidad → cualquier
#     cambio se bloquea.
#   - DIRECCIONAL: aflojar ayuda al alumno, apretar lo perjudica → se bloquea solo
#     al apretar (`cierre` solo se puede EXTENDER; `intentos_permitidos` solo AUMENTAR).
#   - LIBRE: publicar/ocultar resultados es un acto legítimo posterior → siempre permitido.
CONGELADO_DURO: frozenset[str] = frozenset(
    {
        "nota_maxima",
        "nota_aprobacion",
        "tiempo_limite_min",
        "mezclar_preguntas",
        "apertura",
    }
)
CAMPOS_DIRECCIONALES: frozenset[str] = frozenset({"cierre", "intentos_permitidos"})
CAMPOS_LIBRES: frozenset[str] = frozenset({"mostrar_nota", "revision_habilitada"})


def cambios_bloqueados(
    *,
    cambios: Mapping[str, Any],
    vigente: Mapping[str, Any],
    ya_rendido: bool,
) -> frozenset[str]:
    """Subconjunto de ``cambios`` (campo → nuevo valor) bloqueado por el candado.

    ``vigente`` mapea campo → valor actual (para decidir la dirección). Si el examen
    aún no fue rendido, nada se bloquea. Los campos direccionales se bloquean SOLO al
    apretar: ``cierre`` menor al vigente (acortar la ventana) o ``intentos_permitidos``
    menor al vigente (quitar intentos)."""
    if not ya_rendido:
        return frozenset()
    bloqueados: set[str] = set()
    for campo, nuevo in cambios.items():
        if campo in CONGELADO_DURO:
            bloqueados.add(campo)
        elif campo == "cierre":
            # solo se puede EXTENDER: un cierre anterior al vigente aprieta → bloqueado
            if nuevo < vigente["cierre"]:
                bloqueados.add(campo)
        elif campo == "intentos_permitidos":
            # solo se puede AUMENTAR: menos intentos que el vigente aprieta → bloqueado
            if nuevo < vigente["intentos_permitidos"]:
                bloqueados.add(campo)
        # CAMPOS_LIBRES y cualquier otro campo no declarado → permitido
    return frozenset(bloqueados)


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
