"""Reglas PURAS del consentimiento: accion afirmativa, hash y gate (C-08).

- ``validar_accion_afirmativa`` (D2, RN-CO-02): exige la marca explicita; sin ella
  levanta ``MissingAffirmativeActionError`` (-> 422). La validez NO depende del
  cliente (sensor no confiable, RN-GLB-01): se valida server-side.
- ``hash_acuse`` (D1): sella el TEXTO EXACTO consentido + la marca de acuse +
  identidad/examen/timestamp, para una prueba defendible meses despues.
- ``evaluar_gate`` (D4): habilita biometria solo con consentimiento valido o via
  alternativa elegida; si no, ``ConsentNotResolvedError`` (-> 403).

Sin framework ni infraestructura (D1) -> testeable sin DB.
"""

from __future__ import annotations

import enum
import hashlib

from app.domain.consent_flow.errors import (
    ConsentNotResolvedError,
    MissingAffirmativeActionError,
    UnknownConsentVersionError,
)
from app.domain.consent_flow.text_catalog import ConsentText, get_texto


class ResolucionConsentimiento(str, enum.Enum):
    """Como resolvio el estudiante la base legal del tratamiento biometrico."""

    CONSENTIDO = "consentido"          # acuse valido registrado
    VIA_ALTERNATIVA = "via_alternativa"  # eligio verificacion sin biometria
    NO_RESUELTO = "no_resuelto"        # ni una ni otra -> gate cerrado


def validar_accion_afirmativa(affirmative_action: bool) -> None:
    """Exige accion afirmativa explicita (D2, RN-CO-02). Sin ella -> 422."""
    if affirmative_action is not True:
        raise MissingAffirmativeActionError(
            "El consentimiento requiere una accion afirmativa explicita (RN-CO-02)."
        )


def resolver_texto(version: str | None) -> ConsentText:
    """Resuelve la version del texto; version inexistente -> 422."""
    texto = get_texto(version)
    if texto is None:
        raise UnknownConsentVersionError(f"Version de texto desconocida: {version!r}.")
    return texto


def hash_acuse(
    *,
    user_id: str,
    exam_id: str,
    texto: ConsentText,
    timestamp: str,
    affirmative_action: bool,
) -> str:
    """Hash que SELLA el texto exacto consentido + el acuse (D1).

    Incluye el hash del cuerpo del texto (no solo la etiqueta de version), de modo
    que la prueba demuestra QUE versión EXACTA se consintio y CUANDO. La marca de
    accion afirmativa entra al sello (un acuse falso no produce el mismo hash)."""
    payload = "|".join(
        [
            user_id,
            exam_id,
            texto.version,
            texto.hash_texto(),
            timestamp,
            "affirmative" if affirmative_action else "none",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluar_gate(resolucion: ResolucionConsentimiento) -> bool:
    """Gate D4: ``True`` si se puede avanzar (consentido o via alternativa).

    - CONSENTIDO -> biometria habilitada.
    - VIA_ALTERNATIVA -> no se exige biometria (se va a proctor); el avance es valido.
    - NO_RESUELTO -> ``ConsentNotResolvedError`` (-> 403): no se habilita biometria."""
    if resolucion == ResolucionConsentimiento.NO_RESUELTO:
        raise ConsentNotResolvedError(
            "Sin consentimiento valido ni via alternativa: biometria no habilitada (D4)."
        )
    return True


def biometria_habilitada(resolucion: ResolucionConsentimiento) -> bool:
    """``True`` SOLO si se consintio la biometria (la via alternativa NO la exige)."""
    return resolucion == ResolucionConsentimiento.CONSENTIDO
