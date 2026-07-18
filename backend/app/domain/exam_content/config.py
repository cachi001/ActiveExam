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


# C-72 §6 + §18 — Candado DIRECCIONAL post-rendición (reemplaza el binario de arriba).
# Grupos según qué le hace el cambio a quienes YA rindieron:
#   - CONGELADO DURO: reescribe retroactivamente la nota o la equidad → cualquier
#     cambio se bloquea.
#   - DIRECCIONAL: aflojar ayuda al alumno, apretar lo perjudica → se bloquea solo
#     al apretar. `cierre` solo EXTENDER; `intentos_permitidos` solo AUMENTAR;
#     `revision_habilitada` solo HABILITAR (true, no quitar); `mostrar_nota` solo
#     MOSTRAR ANTES (al_cerrar→inmediata, no ocultar la nota que se iba a ver).
#   - LIBRE: sin campos (§18 movió los de publicación a direccionales: cambiar lo
#     que ve quien ya entregó, en la dirección que perjudica, altera las reglas del
#     juego a posteriori).
CONGELADO_DURO: frozenset[str] = frozenset(
    {
        "nota_maxima",
        "nota_aprobacion",
        "tiempo_limite_min",
        "mezclar_preguntas",
        "apertura",
    }
)
CAMPOS_DIRECCIONALES: frozenset[str] = frozenset(
    {"cierre", "intentos_permitidos", "revision_habilitada", "mostrar_nota"}
)
# Subconjunto de los direccionales que solo se pueden AMPLIAR (extender la ventana /
# aumentar los intentos). Los otros direccionales (publicación) solo se AFLOJAN — no
# son "ampliables" en el mismo sentido, por eso el GET /config los distingue: este set
# es lo que la UI muestra como "solo se puede ampliar".
CAMPOS_SOLO_AMPLIABLES: frozenset[str] = frozenset({"cierre", "intentos_permitidos"})
CAMPOS_LIBRES: frozenset[str] = frozenset()


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
        elif campo == "revision_habilitada":
            # solo HABILITAR (false→true) es generoso; quitar la revisión que el
            # alumno iba a ver (true→false) lo perjudica → bloqueado (§18)
            if vigente["revision_habilitada"] is True and nuevo is False:
                bloqueados.add(campo)
        elif campo == "mostrar_nota":
            # solo MOSTRAR ANTES (al_cerrar→inmediata) es generoso; ocultar la nota
            # que se iba a ver ya (inmediata→al_cerrar) perjudica → bloqueado (§18)
            if vigente["mostrar_nota"] == "inmediata" and nuevo != "inmediata":
                bloqueados.add(campo)
        # cualquier otro campo no declarado → permitido
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
