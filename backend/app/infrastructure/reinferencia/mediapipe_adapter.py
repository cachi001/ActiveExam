"""Adapter MediaPipe para la re-inferencia server-side (implementa ReinferenciaPort).

Usa MediaPipe Tasks Python (FaceDetector) con el MISMO modelo que el cliente
(face_detector_short_range.task), garantizando comparacion apples-to-apples
entre el conteo reportado por el cliente y el re-detectado por el servidor (D8).

Patron DD-17: motor de vision abstraido detras del puerto ReinferenciaPort.
Cambiar a ONNX Runtime solo requiere crear un nuevo adapter; event_service no cambia.

DEGRADACION ELEGANTE (RN-GLB-02):
    Ante cualquiera de estas condiciones:
    - mediapipe no instalado (ImportError)
    - modelo .task faltante en MEDIAPIPE_MODEL_DIR
    - sin screenshot (None o vacio)
    - imagen no decodificable (base64 invalido o formato no soportado)
    - error inesperado del detector
    El adapter devuelve veredicto='no_evaluado' SIN levantar excepcion.
    La ingesta del evento NUNCA falla por la re-inferencia.

SINGLETON: el detector se inicializa una vez al construir el adapter
(o None si hay error) para evitar recargar el modelo .task en cada request.
Si MediaPipe no es thread-safe para acceso concurrente, cada request puede
construir su propio detector (cambiar _detector a propiedad de instancia
sin caching). Hipotesis de esta implementacion: reuso entre requests OK.

L2.5: el veredicto 'discrepancia' NO sanciona — solo enriquece la evidencia
para el revisor humano. La decision disciplinaria es siempre humana.

Ley 25.326: el screenshot es dato sensible; se usa solo para re-inferencia
y NO se almacena en este modulo (la persistencia la hace el repositorio).
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from app.application.proctoring.reinferencia import ResultadoReinferencia

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_NO_EVALUADO = ResultadoReinferencia(face_count_servidor=None, veredicto="no_evaluado")


def _resolver_modelo() -> str | None:
    """Resuelve la ruta al modelo .task desde MEDIAPIPE_MODEL_DIR.

    Busca en:
    1. MEDIAPIPE_MODEL_DIR (env var)
    2. backend/models/ (desarrollo local, relativo al directorio de ejecucion)
    3. /app/models/ (contenedor Railway)
    """
    model_file = "face_detector_short_range.task"
    candidatos = [
        os.environ.get("MEDIAPIPE_MODEL_DIR", ""),
        "backend/models",
        "/app/models",
    ]
    for directorio in candidatos:
        if not directorio:
            continue
        ruta = Path(directorio) / model_file
        if ruta.exists():
            return str(ruta)
    return None


def _inicializar_detector() -> object | None:
    """Intenta crear el FaceDetector de MediaPipe Tasks. Devuelve None si falla."""
    try:
        import mediapipe as mp  # noqa: PLC0415
        from mediapipe.tasks.python import vision  # noqa: PLC0415
        from mediapipe.tasks.python.core.base_options import BaseOptions  # noqa: PLC0415
    except ImportError:
        logger.warning(
            "mediapipe no esta instalado. Re-inferencia degradada a 'no_evaluado'. "
            "Instalar con: pip install mediapipe>=0.10.14"
        )
        return None

    ruta_modelo = _resolver_modelo()
    if ruta_modelo is None:
        logger.warning(
            "face_detector_short_range.task no encontrado en MEDIAPIPE_MODEL_DIR "
            "ni en backend/models/ ni en /app/models/. Re-inferencia degradada."
        )
        return None

    try:
        options = vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=ruta_modelo),
        )
        detector = vision.FaceDetector.create_from_options(options)
        logger.info("MediaPipe FaceDetector inicializado desde %s", ruta_modelo)
        return detector
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error al inicializar MediaPipe FaceDetector: %s", exc)
        return None


class MediaPipeReinferencia:
    """Adapter de re-inferencia con MediaPipe Tasks FaceDetector.

    Implementa ReinferenciaPort (Protocol — sin herencia explicita para no
    acoplar la infraestructura al puerto; duck typing es suficiente).
    """

    def __init__(self) -> None:
        # Singleton del detector. None indica degradacion elegante.
        self._detector = _inicializar_detector()

    def evaluar(
        self,
        screenshot_b64: str | None,
        face_count_cliente: int | None,
    ) -> ResultadoReinferencia:
        """Re-detecta rostros en el screenshot con MediaPipe y produce un veredicto.

        Veredictos:
          - 'coincide': face_count_servidor == face_count_cliente
          - 'discrepancia': difieren (posible manipulacion del stream/screenshot)
          - 'no_evaluado': no se pudo evaluar (sin screenshot, error, modelo ausente)

        Nunca levanta excepcion (degradacion elegante, RN-GLB-02).
        """
        if self._detector is None:
            return _NO_EVALUADO

        if not screenshot_b64:
            return _NO_EVALUADO

        try:
            return self._evaluar_con_detector(screenshot_b64, face_count_cliente)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error en re-inferencia MediaPipe: %s", exc)
            return _NO_EVALUADO

    def _evaluar_con_detector(
        self,
        screenshot_b64: str,
        face_count_cliente: int | None,
    ) -> ResultadoReinferencia:
        """Logica interna de re-inferencia. Puede levantar excepciones (las captura evaluar)."""
        import mediapipe as mp  # noqa: PLC0415
        from mediapipe.tasks.python import vision  # noqa: PLC0415

        # Decodificar base64 a bytes de imagen
        # Soporta 'data:image/jpeg;base64,...' y base64 puro
        b64_data = screenshot_b64
        if "," in screenshot_b64:
            b64_data = screenshot_b64.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(b64_data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Base64 invalido en screenshot: %s", exc)
            return _NO_EVALUADO

        # Crear imagen MediaPipe desde bytes
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=_bytes_to_rgb_array(image_bytes),
        )

        # Re-detectar rostros
        result = self._detector.detect(mp_image)
        face_count_servidor = len(result.detections)

        # Determinar veredicto
        if face_count_cliente is None:
            # Sin conteo del cliente no se puede comparar
            return ResultadoReinferencia(
                face_count_servidor=face_count_servidor,
                veredicto="no_evaluado",
            )

        veredicto = "coincide" if face_count_servidor == face_count_cliente else "discrepancia"
        return ResultadoReinferencia(
            face_count_servidor=face_count_servidor,
            veredicto=veredicto,
        )


def _bytes_to_rgb_array(image_bytes: bytes):
    """Convierte bytes de imagen a numpy array RGB para MediaPipe.

    Usa PIL (Pillow) si esta disponible, o intenta con OpenCV como fallback.
    Levanta excepcion si no puede decodificar (la captura evaluar()).
    """
    try:
        import numpy as np  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
        import io  # noqa: PLC0415

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.array(img)
    except ImportError:
        pass

    try:
        import numpy as np  # noqa: PLC0415
        import cv2  # noqa: PLC0415

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("OpenCV no pudo decodificar la imagen")
        return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    except ImportError:
        pass

    # Fallback: numpy puro (solo para PNG/JPEG simples; puede fallar en general)
    import numpy as np  # noqa: PLC0415
    return np.frombuffer(image_bytes, dtype=np.uint8).reshape(-1, 1, 3)
