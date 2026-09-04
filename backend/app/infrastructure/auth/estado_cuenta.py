"""Estado VIGENTE de una cuenta, para que revocar no espere al vencimiento del token.

El access token porta los roles y dura 15 minutos, y el guard no consultaba la
base: dar de baja a alguien, o quitarle un rol, no lo sacaba del sistema hasta que
su token venciera. En un examen en curso eso es una ventana de hasta 15 minutos
operando con permisos ya revocados.

Consultar la base en CADA request no es gratis: con 100 personas rindiendo, entre
el polling del panel y el envío de eventos, son miles de consultas por minuto
contra la misma fila. De ahí el cache con TTL corto: la revocación tarda a lo sumo
el TTL (30 s por defecto) en vez de 15 minutos, y la base ve una consulta por
usuario cada 30 s.

El cache es por proceso y no se comparte entre workers. Con TTL corto eso no
importa: nadie depende de que dos workers coincidan, solo de que ninguno se quede
con el dato viejo más que el TTL.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EstadoCuenta:
    """Lo que la BASE dice hoy de una cuenta (no lo que decía su token)."""

    activa: bool
    roles: tuple[str, ...]


class CacheEstadoCuenta:
    """Cache por usuario con TTL, para no pegarle a la base en cada request.

    ``reloj`` se inyecta para que los tests controlen el paso del tiempo sin
    dormir. Por defecto ``time.monotonic``: inmune a que el reloj del sistema se
    ajuste hacia atrás, que con un TTL de segundos dejaría entradas frescas
    "eternas".
    """

    __slots__ = ("_ttl", "_reloj", "_entradas")

    def __init__(
        self,
        ttl_segundos: float = 30.0,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_segundos
        self._reloj = reloj
        self._entradas: dict[str, tuple[float, EstadoCuenta]] = {}

    async def obtener(
        self,
        usuario_id: str,
        cargar: Callable[[], Awaitable[EstadoCuenta | None]],
    ) -> EstadoCuenta | None:
        """Estado vigente de ``usuario_id``, del cache o de ``cargar()``.

        ``None`` = no hay fila para ese id. Se cachea igual: un subject que no es
        una cuenta local (otro emisor, un token de servicio) llega en CADA request
        y no tiene sentido preguntarle a la base por él una y otra vez.
        """
        ahora = self._reloj()
        entrada = self._entradas.get(usuario_id)
        if entrada is not None and ahora - entrada[0] < self._ttl:
            return entrada[1]

        estado = await cargar()
        # Un fallo de la carga propaga la excepción y NO deja nada cacheado: que lo
        # decida quien llama (el guard deja pasar, ver dependencies.py).
        self._entradas[usuario_id] = (ahora, estado)  # type: ignore[assignment]
        return estado

    def invalidar(self, usuario_id: str) -> None:
        """Olvida lo que sabía de un usuario (tras editarlo o darlo de baja)."""
        self._entradas.pop(usuario_id, None)

    def limpiar(self) -> None:
        """Vacía el cache entero. Para los tests y para el arranque."""
        self._entradas.clear()


#: Instancia de proceso. Se usa desde el guard y se invalida desde el router de
#: usuarios cuando un admin edita o da de baja a alguien, para que el efecto sea
#: inmediato en ESTE worker sin esperar el TTL.
CACHE_ESTADO_CUENTA = CacheEstadoCuenta()
