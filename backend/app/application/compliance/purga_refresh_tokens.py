"""Limpieza de refresh tokens muertos.

## Por que existe

`refresh_tokens` solo crecia: no habia nada que borrara filas. Medido en
desarrollo el 29/8/2026 tras un dia de pruebas: `admin` con 85 sesiones activas,
`estudiante1` con 25, `estudiante2` con 21.

Cada login inserta una fila y cada refresh rota la anterior (le pone `rotado_en`)
e inserta otra. En un examen de una hora con access tokens de 15 minutos, cada
alumno rota unas 4 veces: 100 alumnos son ~500 filas por examen, ninguna de las
cuales se borraba nunca.

## Que borra

- **Vencidos** (`expires_at < ahora`): imposibles de usar, se van siempre.
- **Rotados hace mas de `HORAS_DE_GRACIA_ROTADO`**: ya fueron canjeados.

## Que NO borra

Los tokens VIGENTES. Borrar uno cierra la sesion de alguien que esta usando el
sistema, posiblemente rindiendo. La tabla queda acotada a "las sesiones de los
ultimos 7 dias", que es exactamente lo util.

## Por que borrar los rotados no debilita la deteccion de reuso

`DbRefreshStore.rotate_async` levanta `RefreshTokenError` cuando el token no esta
vigente, y lo resuelve con un `scalar_one_or_none()`: da igual si la fila esta
marcada como rotada o si ya no existe — las dos caen en `registro_viejo is None`
y producen el mismo error, con el mismo efecto (la sesion se cierra). La gracia
de 24 h es conservadora, no imprescindible.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_

from app.infrastructure.persistence.models.transactional import RefreshTokenModel

logger = logging.getLogger("retencion")

#: Cuanto se conserva un token ya rotado antes de borrarlo. Margen por si hiciera
#: falta mirar un reuso reciente; no cumple ninguna funcion tecnica.
HORAS_DE_GRACIA_ROTADO = 24


async def purgar_refresh_tokens_muertos(session_factory) -> int:
    """Borra los refresh tokens que ya no pueden usarse. Devuelve cuantos borro.

    **Best-effort**: corre en la tarea de fondo del arranque, asi que cualquier
    fallo devuelve 0 y se loguea en vez de propagarse.
    """
    ahora = datetime.now(timezone.utc)
    corte_rotados = ahora - timedelta(hours=HORAS_DE_GRACIA_ROTADO)
    try:
        async with session_factory() as session:
            resultado = await session.execute(
                delete(RefreshTokenModel).where(
                    or_(
                        RefreshTokenModel.expires_at < ahora,
                        RefreshTokenModel.rotado_en < corte_rotados,
                    )
                )
            )
            await session.commit()
            borrados = resultado.rowcount or 0
    except Exception:  # noqa: BLE001 — una tarea de fondo no tumba el arranque
        logger.exception("Purga de refresh tokens: fallo, se reintenta la proxima.")
        return 0

    if borrados:
        logger.info(
            "Purga de refresh tokens: %d fila(s) muerta(s) borrada(s). "
            "Las sesiones vigentes no se tocan.",
            borrados,
        )
    return borrados
