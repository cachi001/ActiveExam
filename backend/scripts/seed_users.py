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

CREDENCIALES SEED (para probar el login — identificadores estilo produccion):
    Estudiante: id_institucional=EST-001   | email=estudiante@activeexam.local
    Proctor:    id_institucional=PROC-001  | email=proctor@activeexam.local
    Admin:      id_institucional=ADMIN-001 | email=admin@activeexam.local
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
            "id_institucional": "EST-001",
            "email": "estudiante@activeexam.local",
            "password": pw_estudiante,
            "roles": ["estudiante"],
            "nombre": "Estudiante",
            "apellido": "Prueba",
        },
        {
            "id_institucional": "PROC-001",
            "email": "proctor@activeexam.local",
            "password": pw_proctor,
            "roles": ["proctor"],
            "nombre": "Proctor",
            "apellido": "Prueba",
        },
        {
            "id_institucional": "ADMIN-001",
            "email": "admin@activeexam.local",
            "password": pw_admin,
            "roles": ["admin_sistema"],
            "nombre": "Admin",
            "apellido": "Sistema",
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
                nombre=datos.get("nombre"),
                apellido=datos.get("apellido"),
            )
            session.add(usuario)
            print(f"  [create] {datos['id_institucional']} ({', '.join(datos['roles'])})")
            creados += 1

        await session.commit()

    print(f"\nSeed completado: {creados} creados, {existentes} ya existentes.")

    # Contenido académico demo: materia + comisión + examen (idempotente).
    await _seed_contenido(factory)


async def _seed_contenido(factory) -> None:
    """Siembra contenido académico demo (idempotente).

    Programación 1 → Comisión 1 → "Examen de Programación 1", cuyas preguntas se
    importan del Moodle XML ``scripts/fixtures/programacion-1.xml`` (mismo parser
    que el endpoint /moodle-import). El examen se rinde on-demand pero tiene HORA
    DE INICIO visible (apertura); ventana abierta (sin cierre). 2 intentos, 40 min.
    """
    from datetime import datetime, timezone

    from app.application.exam_content.moodle_parser import parse_moodle_xml
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
        OpcionRespuestaModel,
        PreguntaExamenModel,
    )

    MATERIA_CODIGO = "PROG1"
    MATERIA_NOMBRE = "Programación 1"
    COMISION_CODIGO = "C1"
    COMISION_NOMBRE = "Comisión 1"
    # C-70: código de matriculación de demo (enrolment key) para la Comisión C1.
    COMISION_MATRICULACION = "PROG1-C1"
    EXAMEN_TITULO = "Examen de Programación 1"
    XML_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "programacion-1.xml")

    async with factory() as session:
        # 1. Materia (idempotente por codigo único).
        materia = (
            await session.execute(
                select(MateriaModel).where(MateriaModel.codigo == MATERIA_CODIGO)
            )
        ).scalar_one_or_none()
        if materia is None:
            materia = MateriaModel(codigo=MATERIA_CODIGO, nombre=MATERIA_NOMBRE)
            session.add(materia)
            await session.flush()  # obtener materia.id para la FK de comisión
            print(f"  [create] materia {MATERIA_NOMBRE} ({MATERIA_CODIGO})")
        else:
            print(f"  [skip] materia ya existe: {MATERIA_CODIGO}")

        # 2. Comisión (idempotente por (materia_id, codigo)).
        comision = (
            await session.execute(
                select(ComisionModel).where(
                    ComisionModel.materia_id == materia.id,
                    ComisionModel.codigo == COMISION_CODIGO,
                )
            )
        ).scalar_one_or_none()
        if comision is None:
            comision = ComisionModel(
                materia_id=materia.id,
                codigo=COMISION_CODIGO,
                nombre=COMISION_NOMBRE,
                periodo="1C",
                anio=2026,
                codigo_matriculacion=COMISION_MATRICULACION,
            )
            session.add(comision)
            await session.flush()  # obtener comision.id para la FK del examen
            print(f"  [create] comision {COMISION_NOMBRE} ({COMISION_CODIGO})")
        else:
            print(f"  [skip] comision ya existe: {COMISION_CODIGO}")

        # 3. Examen (idempotente por (titulo, comision_id)).
        examen = (
            await session.execute(
                select(ExamenContenidoModel).where(
                    ExamenContenidoModel.titulo == EXAMEN_TITULO,
                    ExamenContenidoModel.comision_id == comision.id,
                )
            )
        ).scalar_one_or_none()
        if examen is not None:
            print(f"  [skip] examen ya existe: {EXAMEN_TITULO}")
        elif not os.path.exists(XML_PATH):
            print(f"  [skip] fixture no encontrado: {XML_PATH} (examen no importado)")
        else:
            with open(XML_PATH, "rb") as f:
                parseo = parse_moodle_xml(f.read())
            examen = ExamenContenidoModel(
                titulo=EXAMEN_TITULO,
                comision_id=comision.id,
                tiempo_limite_min=40,
                intentos_permitidos=2,
                # Ventana de rendición (obligatoria): abierta y rendible ya. Editable
                # luego desde el panel del docente. Cierre lejano para el demo.
                apertura=datetime(2026, 7, 7, 9, 0, tzinfo=timezone.utc),
                cierre=datetime(2026, 12, 31, 23, 0, tzinfo=timezone.utc),
                # Demo: nota INMEDIATA (se ve al entregar, sin esperar el cierre) +
                # revisión habilitada.
                mostrar_nota="inmediata",
                revision_habilitada=True,
            )
            for i, pd in enumerate(parseo.preguntas):
                pregunta = PreguntaExamenModel(
                    enunciado=pd.enunciado,
                    tipo=pd.tipo,
                    orden=i,
                    seleccionada=True,
                )
                for j, op in enumerate(pd.opciones):
                    pregunta.opciones.append(
                        OpcionRespuestaModel(
                            texto=op.texto, es_correcta=op.es_correcta, orden=j
                        )
                    )
                examen.preguntas.append(pregunta)
            session.add(examen)
            print(f"  [create] examen {EXAMEN_TITULO} ({len(parseo.preguntas)} preguntas del XML)")

        await session.commit()


if __name__ == "__main__":
    if _SLIM_FLAG:
        print("[seed] Modo: slim (DATABASE_URL directo, sin Settings del full)")
        asyncio.run(_seed_slim())
    else:
        print("[seed] Modo: full (app.config.Settings)")
        asyncio.run(_seed_full())
