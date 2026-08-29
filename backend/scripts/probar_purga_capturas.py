"""Demuestra la purga de capturas vencidas sin esperar 180 dias.

Uso (con el stack de dev arriba):

    docker exec activeexam-dev-backend-1 python scripts/probar_purga_capturas.py

Crea TRES sesiones de mentira, fechadas 200 dias atras, cada una con una captura:

  1. normal      -> sin decision, sin señales de riesgo
  2. anulada     -> decision = 'anulado'
  3. en revision -> sin decision, con un evento de severidad critica (score 80)

Corre la purga real (la MISMA funcion que dispara la tarea automatica y el boton
de administracion) y muestra cual perdio la imagen y cual la conservo. Al final
borra las tres sesiones que creo — NO toca ninguna sesion existente.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.application.compliance.retencion_capturas import (  # noqa: E402
    purgar_capturas_vencidas,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: E402,F401
    ExamenContenidoModel,  # registra la tabla que referencia la FK de la sesion
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: E402
    ProctoringEventModel,
    ProctoringSessionModel,
)

ETIQUETA = "PRUEBA-PURGA-borrame"
IMAGEN = "ZmFrZS1iYXNlNjQtaW1hZ2U="


async def _crear(sesion_db, *, decision: str | None, severidad: str) -> tuple[str, str]:
    sesion = ProctoringSessionModel(modo="test", etiqueta=ETIQUETA)
    if decision:
        sesion.decision = decision
    sesion_db.add(sesion)
    await sesion_db.flush()
    sesion.creada_en = datetime.now(timezone.utc) - timedelta(days=200)
    evento = ProctoringEventModel(
        session_id=sesion.id,
        tipo="multiples_rostros",
        severidad=severidad,
        ts_cliente=datetime.now(timezone.utc),
        ts_backend=datetime.now(timezone.utc),
        payload={},
        screenshot_b64=IMAGEN,
        screenshot_sha256="d" * 64,
    )
    sesion_db.add(evento)
    await sesion_db.flush()
    return sesion.id, evento.id


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    if url.rstrip("/").endswith("_test"):
        print("Apuntá DATABASE_URL a la base de DEV, no a la de tests.")
        return
    engine = create_async_engine(url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    casos: dict[str, tuple[str, str]] = {}
    async with factory() as db:
        casos["normal"] = await _crear(db, decision=None, severidad="media")
        casos["anulada"] = await _crear(db, decision="anulado", severidad="media")
        casos["en revision"] = await _crear(db, decision=None, severidad="critica")
        await db.commit()

    async with factory() as db:
        purgadas = await purgar_capturas_vencidas(db, dias=180)
        await db.commit()

    print(f"\nLa purga borro {purgadas} imagen(es) de 3 capturas de 200 dias.\n")
    async with factory() as db:
        for nombre, (_, evento_id) in casos.items():
            ev = await db.get(ProctoringEventModel, evento_id)
            tiene_imagen = ev.screenshot_b64 is not None or ev.screenshot_bin is not None
            estado = "CONSERVA la foto" if tiene_imagen else "foto BORRADA"
            print(f"  {nombre:<12} -> {estado}")
            print(
                f"  {'':<12}    el evento sigue existiendo: tipo={ev.tipo}, "
                f"huella={(ev.screenshot_sha256 or '')[:12]}…"
            )

    async with factory() as db:
        ids = (
            (
                await db.execute(
                    select(ProctoringSessionModel.id).where(
                        ProctoringSessionModel.etiqueta == ETIQUETA
                    )
                )
            )
            .scalars()
            .all()
        )
        await db.execute(
            delete(ProctoringEventModel).where(
                ProctoringEventModel.session_id.in_(list(ids))
            )
        )
        await db.execute(
            delete(ProctoringSessionModel).where(ProctoringSessionModel.id.in_(list(ids)))
        )
        await db.commit()
    print(f"\nSe borraron las {len(ids)} sesiones de prueba. Nada mas fue tocado.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
