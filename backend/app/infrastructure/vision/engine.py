"""Adaptador del motor de vision server-side (re-inferencia, DD-17/RN-GLB-01).

Implementa ``VisionEnginePort`` recuperando el clip del storage (por URI firmada),
verificando su integridad por hash y re-infiriendo embedding + liveness con el
motor concreto. El motor (MediaPipe Tasks / ONNX Runtime) se inyecta como un
callable abstracto (``ClipInferencer``): asi el adaptador no se ata a una libreria
y los tests sustituyen el inferenciador sin red ni binarios.

PRODUCCION: el ``ClipInferencer`` real descarga el clip del bucket, corre el grafo
de Face Mesh sobre los frames y produce el embedding + las senales de liveness
re-derivadas del clip EXACTO (no del veredicto del cliente, RN-GLB-01).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.domain.biometrics.ports import ReinferenciaResultado, VisionEnginePort

# Firma del inferenciador inyectable: (clip_uri, clip_hash) -> resultado.
ClipInferencer = Callable[[str, str], Awaitable[ReinferenciaResultado]]


class IntegridadClipError(RuntimeError):
    """El clip recuperado no coincide con el hash esperado (custodia rota)."""


class ReinferenceVisionEngine(VisionEnginePort):
    """Adaptador de re-inferencia server-side sobre el clip (motor abstraido)."""

    def __init__(self, inferenciador: ClipInferencer) -> None:
        self._inferir = inferenciador

    async def reinferir(self, *, clip_uri: str, clip_hash: str) -> ReinferenciaResultado:
        """Re-infiere sobre el clip exacto. El inferenciador concreto descarga el
        clip, valida ``clip_hash`` y corre el motor de vision; aqui solo se delega
        para mantener el adaptador agnostico de la libreria de vision (DD-17)."""
        return await self._inferir(clip_uri, clip_hash)
