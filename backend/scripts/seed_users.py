#!/usr/bin/env python
"""Seed de usuarios de prueba con credencial local (C-55).

Crea 3 usuarios demo (uno por cada rol MVP: estudiante, proctor, admin_sistema)
con passwords hasheados (bcrypt 12r). Es IDEMPOTENTE: verifica la existencia
antes de insertar (no duplica si ya existen).

SEGURIDAD:
- Falla con error EXPLICITO si ``ENVIRONMENT=production`` (no seed en prod).
- Los passwords se toman de variables de entorno (SEED_*_PASSWORD); nunca
  hardcodeados en el codigo.
- El script NO crea usuarios en produccion — es exclusivamente para local/staging.

USO (desde el directorio backend/):
    DATABASE_URL=postgresql+asyncpg://... \\
    SEED_ESTUDIANTE_PASSWORD=... \\
    SEED_PROCTOR_PASSWORD=... \\
    SEED_ADMIN_PASSWORD=... \\
    python scripts/seed_users.py

Variables de entorno requeridas adicionales (via Settings):
    STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY,
    STORAGE_BUCKET_EVIDENCE, KEYCLOAK_ISSUER, KEYCLOAK_JWKS_URL,
    JWT_AUDIENCE, OTEL_EXPORTER_OTLP_ENDPOINT

    Para seed local rapido, exportar todas las vars con valores de placeholder:
    STORAGE_ENDPOINT=http://localhost STORAGE_ACCESS_KEY=k ...

CREDENCIALES SEED (para probar el login):
    Estudiante: id_institucional=seed-estudiante@demo.test | email=seed-estudiante@demo.test
    Proctor:    id_institucional=seed-proctor@demo.test   | email=seed-proctor@demo.test
    Admin:      id_institucional=seed-admin@demo.test     | email=seed-admin@demo.test
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

# Asegurarse de que el script puede importar app (corre desde backend/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def _seed() -> None:
    from app.config import Settings
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session import create_engine, create_session_factory

    settings = Settings()

    # Guardia de produccion: el seed NUNCA corre en prod.
    if settings.environment == "production":
        print("ERROR: seed_users.py NO corre en environment=production.", file=sys.stderr)
        sys.exit(1)

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

    engine = create_engine()
    factory = create_session_factory(engine)

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
                auth_provider="local",
                attrs_federados={},
            )
            session.add(usuario)
            print(f"  [create] {datos['id_institucional']} ({', '.join(datos['roles'])})")
            creados += 1

        await session.commit()

    print(f"\nSeed completado: {creados} creados, {existentes} ya existentes.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_seed())
