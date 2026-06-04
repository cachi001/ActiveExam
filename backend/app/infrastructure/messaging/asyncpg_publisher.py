"""Publisher asyncpg para LISTEN/NOTIFY de Postgres (PoC C-03 D9, DESCARTABLE).

Implementa el publisher que ejecuta ``pg_notify(canal, payload)`` con una conexion
asyncpg DEDICADA (separada del pool SQLAlchemy). Una conexion dedicada garantiza
que el NOTIFY no compite con las queries de dominio por slots del pool.

PATRON lazy-connect: la conexion asyncpg se crea al primer ``publish()`` para no
bloquear el arranque. Si la conexion se pierde, el siguiente publish() la reconecta
(best-effort; apropiado para la PoC descartable).

LIMITE DE PAYLOAD: Postgres rechaza silenciosamente un NOTIFY con payload > 8 KB.
El payload contiene SOLO el ``event_id`` (UUID, ~36 bytes) -- muy por debajo del
limite. El panel SSE resuelve el detalle del evento contra la DB si necesita mas
campos. Ver design.md D9 y poc/README.md §Payload de NOTIFY.

ENTORNO WINDOWS / WSL2: asyncpg puede fallar al resolver 'localhost' en Docker
Desktop con WSL2. Por eso se reemplaza 'localhost' por '127.0.0.1' en el DSN
si el DSN viene del entorno (ver design.md §Riesgos especificos Windows).

Este modulo es DESCARTABLE: C-10 re-implementa el publisher con lifecycle completo
(pool supervisado, reconexion con backoff, circuit-breaker, cierre ordenado en
shutdown).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

_log = logging.getLogger(__name__)

# Metrica de persistencia (Bloque 5): el publisher observa el tramo ts_backend->ts_publish
# (INSERT+commit, ya ocurrido cuando llega aqui). Import tolerante.
try:
    from app.observability.poc_metrics import persist_latency_seconds
except Exception:  # noqa: BLE001
    persist_latency_seconds = None

# asyncpg es un import OPCIONAL: si no esta instalado el publisher queda no-op
# y el arranque no falla (el backplane queda inerte en ese caso).
try:
    import asyncpg  # type: ignore[import-untyped]
    _ASYNCPG_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]
    _ASYNCPG_AVAILABLE = False


def _dsn_asyncpg(dsn: str) -> str:
    """Convierte un DSN SQLAlchemy (postgresql+asyncpg://...) a un DSN asyncpg puro.

    Tambien reemplaza 'localhost' por '127.0.0.1' para evitar el problema de
    resolucion DNS de asyncpg en Docker Desktop / WSL2 (design.md §Riesgos Windows).
    """
    # Quitar el prefijo de driver SQLAlchemy si existe.
    clean = re.sub(r"^postgresql\+asyncpg://", "postgresql://", dsn)
    # Reemplazar localhost por IP explicita (asyncpg + WSL2/Docker Desktop).
    clean = re.sub(r"@localhost([\s:/]|$)", r"@127.0.0.1\1", clean)
    return clean


class AsyncpgPublisher:
    """Publisher asyncpg de pg_notify para el backplane A4 (PoC C-03 D9).

    Interfaz compatible con el tipo ``Publisher`` de ``backplane.py``:
        ``async def publish(canal: str, payload: dict) -> None``

    La conexion asyncpg se abre en el primer ``publish()`` (lazy) y se reutiliza
    en llamadas siguientes. Si se pierde (OSError / asyncpg.InterfaceError), se
    reconecta en el siguiente intento (best-effort, sin backoff — PoC descartable).
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = _dsn_asyncpg(dsn)
        self._conn: object | None = None  # asyncpg.Connection | None

    async def _ensure_connection(self) -> object:
        """Devuelve la conexion activa; reconecta si es necesario."""
        if not _ASYNCPG_AVAILABLE:
            raise RuntimeError(
                "asyncpg no esta instalado. "
                "Agregue 'asyncpg' a las dependencias para habilitar el publisher PoC."
            )
        if self._conn is None or self._conn.is_closed():  # type: ignore[union-attr]
            _log.info("AsyncpgPublisher: abriendo conexion dedicada a Postgres.")
            self._conn = await asyncpg.connect(self._dsn)
        return self._conn

    async def publish(self, canal: str, payload: dict) -> None:
        """Ejecuta ``SELECT pg_notify($1, $2)`` con canal y payload slim JSON.

        El canal sigue la convencion del backplane: ``panel:{exam_id}``.

        SLIM de payload (limite 8 KB de Postgres NOTIFY, design.md D9):
        aunque el llamador (ingestion._serializar) pasa el evento completo, el
        NOTIFY solo transporta los campos necesarios para medir la latencia del
        concern (c): ``event_id`` y ``ts_backend`` (con microsegundos). El panel
        SSE puede resolver el resto del evento contra la DB si necesita mas campos.
        Esto garantiza que el payload sea siempre << 8 KB (aprox. 80 bytes).

        Si asyncpg no esta disponible o la conexion falla, loga el error y
        retorna sin lanzar (best-effort; la PoC no debe matar la ingesta)."""
        # Slim: solo los campos necesarios para medir la latencia de fan-out.
        # ``id`` es el event_id del evento persistido; ``ts_backend`` tiene microsegundos
        # (fix de _now_iso(), C-03 D11) y es la referencia de tiempo para el delta.
        # ts_publish: momento JUSTO antes del NOTIFY. Parte el delta total en persist
        # (ts_backend->ts_publish, ya ocurrido) y backplane puro (ts_publish->ts_rx,
        # lo mide el panel). Permite no atribuir al backplane lo que es persistencia.
        ts_publish_dt = datetime.now(timezone.utc)
        ts_backend_str = payload.get("ts_backend")
        if persist_latency_seconds is not None and ts_backend_str:
            try:
                ts_backend_dt = datetime.fromisoformat(str(ts_backend_str).replace("Z", "+00:00"))
                persist_s = (ts_publish_dt - ts_backend_dt).total_seconds()
                if persist_s >= 0:
                    persist_latency_seconds.observe(persist_s)
            except (ValueError, TypeError):
                pass

        slim = {
            "event_id": payload.get("id"),
            "ts_backend": ts_backend_str,
            "ts_publish": ts_publish_dt.isoformat(),
        }
        payload_str = json.dumps(slim, separators=(",", ":"))
        # Validacion preventiva del limite de 8 KB de Postgres NOTIFY.
        if len(payload_str.encode("utf-8")) > 8000:
            _log.warning(
                "AsyncpgPublisher: payload de NOTIFY > 8 KB (%d bytes) para canal '%s'. "
                "Postgres rechaza silenciosamente payloads > 8192 bytes. "
                "Reducir el payload al minimo (event_id + ts_backend).",
                len(payload_str.encode("utf-8")),
                canal,
            )
        try:
            conn = await self._ensure_connection()
            await conn.execute("SELECT pg_notify($1, $2)", canal, payload_str)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 - best-effort, no matar la ingesta
            _log.error(
                "AsyncpgPublisher: error ejecutando pg_notify en canal '%s': %s. "
                "Reconectando en el siguiente intento.",
                canal,
                exc,
            )
            # Forzar reconexion en el siguiente intento.
            self._conn = None

    async def close(self) -> None:
        """Cierra la conexion asyncpg si esta abierta."""
        if self._conn is not None and not self._conn.is_closed():  # type: ignore[union-attr]
            await self._conn.close()  # type: ignore[union-attr]
            _log.info("AsyncpgPublisher: conexion cerrada.")
        self._conn = None
