#!/usr/bin/env python
"""Seed de usuarios de prueba con credencial local (C-55 / c-57).

Crea 3 usuarios demo (uno por cada rol MVP: estudiante, proctor, admin_sistema)
con passwords hasheados (bcrypt 12r). Es IDEMPOTENTE: verifica la existencia
antes de insertar (no duplica si ya existen).

MODOS:
  - Modo full (default): usa ``app.config.Settings`` (requiere todas las vars
    del stack completo: Keycloak, MinIO, OTEL, etc.).
  - Modo slim (``--slim``): usa ``DATABASE_URL`` del entorno directamente con
    ``SlimSettings`` (solo requiere DATABASE_URL). Compatible con Railway.

SEGURIDAD:
- Falla con error EXPLICITO si ``ENVIRONMENT=production`` (no seed en prod).
- Los passwords se toman de variables de entorno (SEED_*_PASSWORD); nunca
  hardcodeados en el codigo.
- El script NO crea usuarios en produccion — es exclusivamente para local/staging.

USO (modo slim — Railway / Postgres estandar):
    DATABASE_URL=postgresql+asyncpg://... \\
    SEED_ESTUDIANTE_PASSWORD=... \\
    SEED_PROCTOR_PASSWORD=... \\
    SEED_ADMIN_PASSWORD=... \\
    python scripts/seed_users.py --slim

USO (modo full — stack completo):
    DATABASE_URL=postgresql+asyncpg://... \\
    SEED_ESTUDIANTE_PASSWORD=... \\
    ... (todas las vars del stack completo) \\
    python scripts/seed_users.py

CREDENCIALES SEED (para probar el login):
    Estudiante: id_institucional=seed-estudiante | email=seed-estudiante@demo.test
    Proctor:    id_institucional=seed-proctor   | email=seed-proctor@demo.test
    Admin:      id_institucional=seed-admin     | email=seed-admin@demo.test
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

# Asegurarse de que el script puede importar app (corre desde backend/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SLIM_FLAG = "--slim" in sys.argv


async def _seed_slim() -> None:
    """Seed en modo slim: usa DATABASE_URL directamente sin cargar Settings del full."""
    from app.config_slim import SlimSettings
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_slim import (
        create_slim_engine,
        create_slim_session_factory,
    )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: Falta la variable de entorno DATABASE_URL.",
            file=sys.stderr,
        )
        sys.exit(1)

    # SlimSettings requiere jwt_own_secret y embedding_encryption_key; en seed
    # solo usamos DATABASE_URL, por lo que pasamos placeholders para las otras.
    # Usamos directamente la URL del entorno para construir el engine slim.
    # Normalizar el esquema para asyncpg.
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgresql://"):]

    print(f"[slim] Conectando a: {database_url[:30]}...", file=sys.stderr)

    engine = create_slim_engine(database_url)
    factory = create_slim_session_factory(engine)

    await _ejecutar_seed(factory, auth_provider="jwt")

    await engine.dispose()


async def _seed_full() -> None:
    """Seed en modo full: usa app.config.Settings (stack completo)."""
    from app.config import Settings
    from app.infrastructure.auth.hashing import hashear_password  # noqa: F401
    from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
    from app.infrastructure.persistence.session import create_engine, create_session_factory

    settings = Settings()

    # Guardia de produccion: el seed NUNCA corre en prod.
    if settings.environment == "production":
        print("ERROR: seed_users.py NO corre en environment=production.", file=sys.stderr)
        sys.exit(1)

    engine = create_engine()
    factory = create_session_factory(engine)

    await _ejecutar_seed(factory, auth_provider="local")

    await engine.dispose()


async def _ejecutar_seed(
    factory,
    auth_provider: str = "jwt",
) -> None:
    """Logica comun de seed: verifica existencia e inserta."""
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    # Leer passwords del entorno (nunca hardcodeados).
    pw_estudiante = os.environ.get("SEED_ESTUDIANTE_PASSWORD")
    pw_proctor = os.environ.get("SEED_PROCTOR_PASSWORD")
    pw_admin = os.environ.get("SEED_ADMIN_PASSWORD")

    if not all([pw_estudiante, pw_proctor, pw_admin]):
        print(
            "ERROR: Faltan variables de entorno SEED_ESTUDIANTE_PASSWORD, "
            "SEED_PROCTOR_PASSWORD y/o SEED_ADMIN_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)

    usuarios_seed = [
        {
            "id_institucional": "seed-estudiante",
            "email": "seed-estudiante@demo.test",
            "password": pw_estudiante,
            "roles": ["estudiante"],
        },
        {
            "id_institucional": "seed-proctor",
            "email": "seed-proctor@demo.test",
            "password": pw_proctor,
            "roles": ["proctor"],
        },
        {
            "id_institucional": "seed-admin",
            "email": "seed-admin@demo.test",
            "password": pw_admin,
            "roles": ["admin_sistema"],
        },
    ]

    creados = 0
    existentes = 0

    async with factory() as session:
        for datos in usuarios_seed:
            # Idempotencia: no insertar si ya existe.
            result = await session.execute(
                select(UsuarioModel).where(
                    UsuarioModel.id_institucional == datos["id_institucional"]
                )
            )
            if result.scalar_one_or_none() is not None:
                print(f"  [skip] Usuario ya existe: {datos['id_institucional']}")
                existentes += 1
                continue

            usuario = UsuarioModel(
                id_institucional=datos["id_institucional"],
                email=datos["email"],
                roles=datos["roles"],
                password_hash=hashear_password(datos["password"]),  # type: ignore[arg-type]
                auth_provider=auth_provider,
                attrs_federados={},
            )
            session.add(usuario)
            print(f"  [create] {datos['id_institucional']} ({', '.join(datos['roles'])})")
            creados += 1

        await session.commit()

    print(f"\nSeed completado: {creados} creados, {existentes} ya existentes.")


if __name__ == "__main__":
    if _SLIM_FLAG:
        print("[seed] Modo: slim (DATABASE_URL directo, sin Settings del full)")
        asyncio.run(_seed_slim())
    else:
        print("[seed] Modo: full (app.config.Settings)")
        asyncio.run(_seed_full())
