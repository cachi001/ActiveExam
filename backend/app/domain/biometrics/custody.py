"""Custodia inicial del clip y clave de sesion rotativa HMAC (PURO, RN-BIO-02/07).

Dos contratos puros:
- ``hash_clip`` / ``firmar_clip``: hash SHA-256 del clip y firma HMAC con la clave
  de sesion -> custodia inicial (misma cadena de custodia que cualquier
  evidencia, RN-BIO-07, RN-CC-04). El binario NO transita el backend (sube por URL
  firmada); aqui se firma el HASH, no el binario.
- ``derivar_clave_sesion`` / ``firmar`` / ``verificar_firma``: la clave de sesion
  ROTATIVA (HMAC) que nace de una verificacion exitosa (RN-BIO-02, D6) y firma los
  eventos posteriores (C-10) y la evidencia (C-12).

PUREZA (D1): ``hashlib``/``hmac`` son STDLIB de Python (no framework ni infra de
terceros), permitidas en el dominio. Lo PROHIBIDO es importar fastapi/sqlalchemy/
adaptadores. El SECRETO MAESTRO del que se deriva la clave de sesion se RECIBE por
parametro (inyectado desde Vault en infraestructura); NUNCA se hardcodea (regla
dura). La rotacion (``epoca``) entra en la derivacion para que la clave cambie.
"""

from __future__ import annotations

import hashlib
import hmac

# Etiqueta de dominio para derivar la clave de sesion (separa este uso de otros
# usos del mismo secreto maestro: domain-separation). No es un secreto.
_LABEL_CLAVE_SESION = b"proctoring/session-key/v1"


def hash_clip(clip_bytes: bytes) -> str:
    """SHA-256 (hex) del clip de verificacion -> ancla de la cadena de custodia."""
    return hashlib.sha256(clip_bytes).hexdigest()


def derivar_clave_sesion(
    *, secreto_maestro: bytes, session_id: str, epoca: int = 0
) -> str:
    """Deriva la clave de sesion ROTATIVA (hex) por HMAC del secreto maestro.

    La ``epoca`` permite rotacion: incrementarla produce una clave distinta para
    la misma sesion sin tocar el secreto maestro. El secreto maestro se inyecta
    desde infraestructura (Vault); este modulo NUNCA lo conoce embebido."""
    if not secreto_maestro:
        raise ValueError("secreto_maestro vacio: no se puede derivar la clave")
    mensaje = b"|".join(
        [_LABEL_CLAVE_SESION, session_id.encode("utf-8"), str(epoca).encode("ascii")]
    )
    return hmac.new(secreto_maestro, mensaje, hashlib.sha256).hexdigest()


def firmar(*, clave_sesion: str, mensaje: bytes) -> str:
    """Firma HMAC-SHA256 (hex) de ``mensaje`` con la clave de sesion (str hex/clave)."""
    return hmac.new(
        clave_sesion.encode("utf-8"), mensaje, hashlib.sha256
    ).hexdigest()


def firmar_clip(*, clave_sesion: str, clip_hash: str) -> str:
    """Firma la custodia inicial del clip: HMAC del hash del clip (RN-BIO-07)."""
    return firmar(clave_sesion=clave_sesion, mensaje=clip_hash.encode("utf-8"))


def verificar_firma(*, clave_sesion: str, mensaje: bytes, firma: str) -> bool:
    """Verifica una firma HMAC en tiempo CONSTANTE (anti timing-attack).

    Devuelve ``True`` sii la firma recomputada coincide con ``firma``. Usa
    ``hmac.compare_digest`` para no filtrar informacion por el tiempo de
    comparacion."""
    esperada = firmar(clave_sesion=clave_sesion, mensaje=mensaje)
    return hmac.compare_digest(esperada, firma)
