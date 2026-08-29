"""Disparo AUTOMATICO de la purga de capturas vencidas (decision del dueño, 28/8/2026).

## Por que existe

`purgar_capturas_vencidas` ya existia, pero solo la llamaba un endpoint admin: el
plazo de retencion era una intencion, no un hecho. El consentimiento que firma el
alumno ahora declara un plazo concreto (180 dias por default), y eso solo se
puede prometer si algo lo ejecuta sin depender de que una persona se acuerde.

## Que borra, y que NO

Borra UNA sola cosa: la imagen (`screenshot_b64` / `screenshot_bin`). NUNCA
elimina eventos ni sesiones — son la prueba del examen (decision explicita del
dueño). Despues de la purga sigue constando que se tomo la captura, con que
huella (`screenshot_sha256`) y en que evento: la cadena de custodia sobrevive y
la evaluacion sigue siendo defendible ante un reclamo.

La otra purga del motor de retencion (`retention/session`, que SI borra filas)
queda deliberadamente fuera de este modulo: se sigue disparando a mano.

## Por que corre al arrancar y no solo cada 24 horas

En Render el proceso se duerme por inactividad. Una tarea que solo despierta cada
24 horas puede no correr nunca. La primera pasada es al arranque (con un respiro
para no competir con el resto del boot) y despues cada `intervalo_horas`.

## Por que hay un advisory lock

Con mas de un worker uvicorn, cada proceso levanta su propia tarea. El purgado es
idempotente, asi que no corrompe nada, pero sin el lock se escribirian N entradas
de auditoria por la misma corrida. `pg_try_advisory_lock` no espera: el worker
que no lo consigue simplemente no corre esta vuelta.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.application.audit.acciones import (
    AccionAuditoria,
    EntidadAuditoria,
    ModuloAuditoria,
)
from app.application.audit.service import registrar_seguro
from app.application.compliance.purga_refresh_tokens import (
    purgar_refresh_tokens_muertos,
)
from app.application.compliance.retencion_capturas import purgar_capturas_vencidas
from app.infrastructure.persistence.repositories.config_sistema import (
    ConfiguracionSistemaSqlRepository,
)

logger = logging.getLogger("retencion")

#: Identificador del advisory lock. Constante arbitraria pero ESTABLE: cambiarla
#: deja de excluir a los workers que sigan usando la anterior.
_LOCK_ID = 8_026_0828

#: Respiro antes de la primera pasada: que el arranque termine de cablear todo y
#: atienda los primeros requests antes de ponerse a escribir en proctoring_event.
_DEMORA_INICIAL_SEG = 30.0


async def ejecutar_purga_programada(session_factory) -> int:
    """Lee el plazo de la config, purga las imagenes vencidas y audita.

    Devuelve cuantas capturas purgo. **Best-effort**: cualquier fallo (base
    caida, tabla ausente, lock tomado por otro worker) devuelve 0 y se loguea,
    nunca se propaga — esto corre en una tarea de fondo colgada del arranque y
    no puede tumbar la app.
    """
    try:
        async with session_factory() as session:
            # Un solo worker por vuelta. El lock se libera al cerrar la sesion.
            tomado = (
                await session.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": _LOCK_ID}
                )
            ).scalar_one()
            if not tomado:
                logger.debug("Purga de capturas: otro worker la esta corriendo.")
                return 0

            cfg = await ConfiguracionSistemaSqlRepository(session).ensure_singleton()
            dias = cfg.retencion_capturas_dias
            purgadas = await purgar_capturas_vencidas(session, dias)
            await session.commit()
    except Exception:  # noqa: BLE001 — una tarea de fondo no tumba el arranque
        logger.exception("Purga automatica de capturas: fallo, se reintenta la proxima.")
        return 0

    # Los refresh tokens muertos se limpian en la misma vuelta: es otra tabla que
    # solo crecia (85 sesiones de `admin` en un dia de pruebas). Va DESPUES del
    # commit de las capturas y con su propio manejo de errores, asi que un fallo
    # aca no arrastra al purgado de imagenes ni al reves.
    await purgar_refresh_tokens_muertos(session_factory)

    if purgadas:
        logger.info(
            "Purga automatica: %d captura(s) mas vieja(s) que %d dias. Imagen "
            "borrada; evento, huella y sesion conservados.",
            purgadas,
            dias,
        )

    # Un borrado de evidencia se audita SIEMPRE, incluso con 0 purgadas: la
    # ausencia de entradas tiene que poder distinguirse de "no corrio nunca".
    await registrar_seguro(
        session_factory,
        actor="sistema:purga_automatica",
        accion=AccionAuditoria.RETENCION_CAPTURAS_PURGADAS,
        modulo=ModuloAuditoria.EVIDENCIA,
        entidad=EntidadAuditoria.SISTEMA,
        proposito=(
            f"Purga automatica: {purgadas} captura(s) mas vieja(s) que {dias} dias "
            "(imagen borrada, evento y hash conservados)"
        ),
    )
    return purgadas


def programar_purga_capturas(
    session_factory,
    *,
    intervalo_horas: int = 24,
    demora_inicial_seg: float = _DEMORA_INICIAL_SEG,
) -> asyncio.Task:
    """Arranca la tarea de fondo y devuelve su ``Task`` (para cancelarla al cerrar).

    Corre una vez poco despues del arranque y luego cada ``intervalo_horas``.
    ``demora_inicial_seg`` existe para que el test no tenga que esperar el respiro
    de arranque real.
    """

    async def _bucle() -> None:
        await asyncio.sleep(demora_inicial_seg)
        while True:
            await ejecutar_purga_programada(session_factory)
            await asyncio.sleep(intervalo_horas * 3600)

    return asyncio.create_task(_bucle(), name="purga_capturas_vencidas")
