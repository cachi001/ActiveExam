"""Contador en memoria de intentos fallidos de conexión a Moodle (C-73, seguridad).

Deliberadamente SIN tabla nueva: el objetivo es avisar de un patrón de "muchos
intentos seguidos" (alguien probando contraseñas), no armar un historial
forense completo — para eso ya existen las filas de auditoría normales de
CONECTAR/RENOVAR. Vive en memoria del proceso backend: si reinicia, el
contador vuelve a cero. Trade-off aceptado a propósito por simplicidad; no
hace falta persistencia para cumplir el objetivo.
"""

from __future__ import annotations

from collections import defaultdict


class IntentosFallidosTracker:
    """Cuenta fallos consecutivos por usuario_id y avisa al llegar al umbral."""

    def __init__(self, umbral: int = 5) -> None:
        self._umbral = umbral
        self._conteo: dict[str, int] = defaultdict(int)

    def registrar_fallo(self, usuario_id: str) -> bool:
        """Suma un fallo. Devuelve True al llegar al umbral, y resetea el
        contador para poder volver a disparar tras otra tanda de fallos."""
        self._conteo[usuario_id] += 1
        if self._conteo[usuario_id] >= self._umbral:
            self._conteo[usuario_id] = 0
            return True
        return False

    def resetear(self, usuario_id: str) -> None:
        """Un intento correcto borra el contador: no se arrastran fallos viejos."""
        self._conteo.pop(usuario_id, None)
