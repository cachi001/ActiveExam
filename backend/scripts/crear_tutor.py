#!/usr/bin/env python
"""Crea (idempotente) una cuenta de TUTOR con contraseña temporal para probar el
flujo de primer login + la sincronización del banco desde Moodle.

Qué hace:
  1. Crea el usuario ``TUT-001`` (tutor@activeexam.local) con rol ``tutor``,
     ``auth_provider='local'`` y ``debe_cambiar_password=True`` → en el primer
     login la web lo obliga a definir su propia contraseña (política Media).
  2. Lo asigna como TUTOR A CARGO de la comisión demo ``PROG1/C1`` (setea
     ``comision.docente_id``) para que pueda operar el banco de preguntas de esa
     materia y ejecutar el sync desde el campus.

Es IDEMPOTENTE: re-ejecutar no duplica ni pisa una contraseña ya cambiada por el
usuario (si ``debe_cambiar_password`` ya es False, NO resetea la clave).

USO (modo slim — Postgres estándar / Railway):
    DATABASE_URL=postgresql+asyncpg://... \\
    TUTOR_PASSWORD_TEMPORAL=Temporal123 \\
    python scripts/crear_tutor.py --slim

Si no se pasa TUTOR_PASSWORD_TEMPORAL, se genera una temporal y se imprime.
La contraseña temporal solo sirve para el primer login; NO tiene que cumplir la
política Media (esa aplica a la que el usuario define después).
"""

from __future__ import annotations

import asyncio
import os
import secrets
import string
import sys

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SLIM_FLAG = "--slim" in sys.argv

TUTOR_ID_INSTITUCIONAL = "TUT-001"
TUTOR_EMAIL = "tutor@activeexam.local"
TUTOR_NOMBRE = "Tutor"
TUTOR_APELLIDO = "Prueba"
MATERIA_CODIGO = "PROG1"
COMISION_CODIGO = "C1"


def _normalizar_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


async def _run(factory, auth_provider: str) -> None:
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    password_temporal = os.environ.get("TUTOR_PASSWORD_TEMPORAL")
    generada = False
    if not password_temporal:
        alphabet = string.ascii_letters + string.digits
        password_temporal = "".join(secrets.choice(alphabet) for _ in range(12))
        generada = True

    async with factory() as session:
        # 1. Usuario tutor (idempotente por id_institucional).
        usuario = (
            await session.execute(
                select(UsuarioModel).where(
                    UsuarioModel.id_institucional == TUTOR_ID_INSTITUCIONAL
                )
            )
        ).scalar_one_or_none()

        if usuario is None:
            usuario = UsuarioModel(
                id_institucional=TUTOR_ID_INSTITUCIONAL,
                email=TUTOR_EMAIL,
                roles=["tutor"],
                nombre=TUTOR_NOMBRE,
                apellido=TUTOR_APELLIDO,
                password_hash=hashear_password(password_temporal),
                auth_provider=auth_provider,
                debe_cambiar_password=True,
                attrs_federados={},
            )
            session.add(usuario)
            await session.flush()
            print(f"  [create] tutor {TUTOR_ID_INSTITUCIONAL} ({TUTOR_EMAIL})")
            print(f"           contraseña temporal: {password_temporal}"
                  + ("  (generada)" if generada else ""))
        else:
            print(f"  [skip] el tutor {TUTOR_ID_INSTITUCIONAL} ya existe (no se toca la contraseña)")

        # 2. Asignar como tutor a cargo de PROG1/C1 (idempotente).
        comision = (
            await session.execute(
                select(ComisionModel)
                .join(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
                .where(
                    MateriaModel.codigo == MATERIA_CODIGO,
                    ComisionModel.codigo == COMISION_CODIGO,
                )
            )
        ).scalar_one_or_none()

        if comision is None:
            print(
                f"  [warn] no existe la comisión {MATERIA_CODIGO}/{COMISION_CODIGO}. "
                "Corré primero seed_users.py para el contenido demo."
            )
        elif comision.docente_id == usuario.id:
            print(f"  [skip] el tutor ya está a cargo de {MATERIA_CODIGO}/{COMISION_CODIGO}")
        else:
            comision.docente_id = usuario.id
            print(f"  [assign] tutor a cargo de {MATERIA_CODIGO}/{COMISION_CODIGO}")

        await session.commit()

    print("\nListo. Entrá a la web con:")
    print(f"  usuario:  {TUTOR_EMAIL}   (o {TUTOR_ID_INSTITUCIONAL})")
    print(f"  password: {password_temporal}" + ("  (generada arriba)" if generada else ""))
    print("En el primer login la web te va a pedir definir tu propia contraseña.")


async def _slim() -> None:
    from app.infrastructure.persistence.session_slim import (
        create_slim_engine,
        create_slim_session_factory,
    )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: falta DATABASE_URL.", file=sys.stderr)
        sys.exit(1)
    engine = create_slim_engine(_normalizar_url(database_url))
    factory = create_slim_session_factory(engine)
    await _run(factory, auth_provider="jwt")
    await engine.dispose()


async def _full() -> None:
    from app.config import Settings
    from app.infrastructure.persistence.session import create_engine, create_session_factory

    settings = Settings()
    if settings.environment == "production":
        print("ERROR: crear_tutor.py NO corre en environment=production.", file=sys.stderr)
        sys.exit(1)
    engine = create_engine()
    factory = create_session_factory(engine)
    await _run(factory, auth_provider="local")
    await engine.dispose()


if __name__ == "__main__":
    if _SLIM_FLAG:
        print("[crear_tutor] Modo: slim (DATABASE_URL directo)")
        asyncio.run(_slim())
    else:
        print("[crear_tutor] Modo: full (app.config.Settings)")
        asyncio.run(_full())
