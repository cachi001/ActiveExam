"""Puerto abstracto de re-inferencia server-side (DD-17).

Define la interfaz ``ReinferenciaPort`` que el ``event_service`` usa para
re-detectar rostros sobre screenshots. El adapter concreto vive en
``app.infrastructure.reinferencia.mediapipe_adapter`` (MediaPipeReinferencia).

La re-inferencia materializa RN-GLB-01 (cliente = sensor no confiable):
el backend NO le cree al navegador a ciegas; re-detecta y produce un veredicto.

L2.5: el veredicto ('coincide' | 'discrepancia' | 'no_evaluado') NO sanciona;
solo enriquece la evidencia para el revisor humano. La decision disciplinaria
es siempre humana.

Cambiar de motor (MediaPipe → ONNX Runtime) solo requiere un nuevo adapter;
la capa de aplicacion (event_service) no cambia.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ResultadoReinferencia:
    """Resultado de la re-inferencia server-side sobre un screenshot.

    face_count_servidor: None si el veredicto es 'no_evaluado' (no se pudo evaluar).
    veredicto: 'coincide' | 'discrepancia' | 'no_evaluado'
    """

    face_count_servidor: int | None
    veredicto: str  # 'coincide' | 'discrepancia' | 'no_evaluado'


class ReinferenciaPort(Protocol):
    """Interfaz del motor de re-inferencia. Depende solo de esta interfaz; nunca
    de MediaPipe ni de ninguna libreria de vision directamente."""

    def evaluar(
        self,
        screenshot_b64: str | None,
        face_count_cliente: int | None,
    ) -> ResultadoReinferencia:
        """Re-detecta rostros en el screenshot y produce un veredicto.

        Args:
            screenshot_b64: Screenshot codificado en base64 (o None si no hay).
            face_count_cliente: Conteo de rostros reportado por el cliente (o None).

        Returns:
            ResultadoReinferencia con face_count_servidor y veredicto.
            Nunca levanta excepcion — ante cualquier error devuelve 'no_evaluado'
            (degradacion elegante, RN-GLB-02).
        """
        ...
