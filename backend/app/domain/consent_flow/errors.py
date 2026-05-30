"""Errores de dominio del flujo de consentimiento (PURO, C-08).

Sin acoplarse a FastAPI; la presentacion los traduce a HTTP:
- ``MissingAffirmativeActionError`` -> 422 (no hubo accion afirmativa explicita, D2).
- ``UnknownConsentVersionError``     -> 422 (version de texto inexistente).
- ``ConsentNotResolvedError``        -> 403 (gate: ni consentimiento ni alternativa, D4).
"""

from __future__ import annotations


class ConsentError(Exception):
    """Raiz de los errores del flujo de consentimiento."""


class MissingAffirmativeActionError(ConsentError):
    """Se intento registrar un acuse sin accion afirmativa explicita (-> 422, RN-CO-02)."""


class UnknownConsentVersionError(ConsentError):
    """La version de texto referenciada no existe en el catalogo (-> 422)."""


class ConsentNotResolvedError(ConsentError):
    """El estudiante no resolvio consentimiento ni via alternativa (-> 403, gate D4)."""
