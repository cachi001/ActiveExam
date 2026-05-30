"""Adaptador de firma maestra ASIMETRICA (RSA-2048/Ed25519) — C-12 etapa 3 (D6).

Implementa ``MasterSignerPort`` del dominio. La firma asimetrica real la hace el SDK
criptografico en produccion (``cryptography``: RSA-PSS o Ed25519); la clave PRIVADA
la custodia Vault y se inyecta en tmpfs efimero — este adaptador la recibe como
callables, NUNCA la embebe (regla dura de secretos, `08`).

La verificacion usa la clave PUBLICA: un perito externo (C-18) valida la cadena sin
acceder al secreto, que es el sentido de elegir firma asimetrica sobre HMAC (D6).
"""

from __future__ import annotations

from collections.abc import Callable

from app.domain.evidence.custody_chain import MasterSignerPort


class InjectedMasterSigner(MasterSignerPort):
    """Firma maestra que delega en callables del SDK cripto (clave de Vault).

    ``sign_fn`` envuelve la operacion de firma de la clave privada (RSA-2048/Ed25519)
    custodiada por Vault; ``verify_fn`` envuelve la verificacion con la clave publica.
    Ningun secreto entra en claro al codigo de la app: el SDK/Vault lo custodian.
    """

    def __init__(
        self,
        *,
        sign_fn: Callable[[bytes], str],
        verify_fn: Callable[[bytes, str], bool],
        algoritmo: str = "ed25519",
    ) -> None:
        if algoritmo not in ("ed25519", "rsa-2048"):
            raise ValueError(f"algoritmo de firma maestra no soportado: {algoritmo}")
        self._sign = sign_fn
        self._verify = verify_fn
        self.algoritmo = algoritmo

    def firmar(self, mensaje: bytes) -> str:
        firma = self._sign(mensaje)
        if not firma:
            raise RuntimeError("firma maestra vacia: la clave de Vault no se inyecto")
        return firma

    def verificar(self, mensaje: bytes, firma: str) -> bool:
        return self._verify(mensaje, firma)
