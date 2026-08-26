#!/usr/bin/env python
"""Seed de usuarios de prueba con credencial local (C-55 / c-57).

Crea 6 usuarios demo: 4 estudiantes (estudiante1..4) + 1 coordinador + 1 admin_sistema,
con passwords hasheados (bcrypt 12r). Es IDEMPOTENTE: verifica la existencia
antes de insertar (no duplica si ya existen). Los 4 estudiantes pueblan la cola
de revisión con sesiones distinguibles.

MODOS:
  - Modo full (default): usa ``app.config.Settings`` (requiere todas las vars
    del stack completo: Keycloak, MinIO, OTEL, etc.).
  - Modo activeexam (``--activeexam``): usa ``DATABASE_URL`` del entorno directamente con
    ``ActiveExamSettings`` (solo requiere DATABASE_URL). Compatible con Railway.

SEGURIDAD:
- Falla con error EXPLICITO si ``ENVIRONMENT=production`` (no seed en prod).
- Los passwords se toman de variables de entorno (SEED_*_PASSWORD); nunca
  hardcodeados en el codigo.
- El script NO crea usuarios en produccion — es exclusivamente para local/staging.

USO (modo activeexam — Railway / Postgres estandar):
    DATABASE_URL=postgresql+asyncpg://... \\
    SEED_ESTUDIANTE_PASSWORD=... \\
    SEED_COORDINADOR_PASSWORD=... \\
    SEED_ADMIN_PASSWORD=... \\
    python scripts/seed_users.py --activeexam

USO (modo full — stack completo):
    DATABASE_URL=postgresql+asyncpg://... \\
    SEED_ESTUDIANTE_PASSWORD=... \\
    ... (todas las vars del stack completo) \\
    python scripts/seed_users.py

CREDENCIALES SEED (para probar el login — usernames simples, no codigos tipo legajo):
    Estudiante:   username=estudiante1   | email=estudiante@activeexam.local (Estudiante Prueba1)
    Estudiante 2: username=estudiante2   | email=estudiante2@activeexam.local (Estudiante Prueba2)
    Estudiante 3: username=estudiante3   | email=estudiante3@activeexam.local (Estudiante Prueba3)
    Estudiante 4: username=estudiante4   | email=estudiante4@activeexam.local (Estudiante Prueba4)
    Coordinador:  username=coordinador1  | email=proctor@activeexam.local (rol coordinador; ex-proctor, c-76.
                  El email se conserva por idempotencia de una migracion vieja
                  -- ya NO hay rol "proctor" en el sistema.)
    Admin:        username=admin         | email=admin@activeexam.local
    Tutor:        username=tutor1        | email=tutor@activeexam.local (docente de PROG1/C1)

    Los 4 estudiantes comparten SEED_ESTUDIANTE_PASSWORD. El tutor usa
    SEED_TUTOR_PASSWORD y queda asignado como docente de la Comisión C1 de PROG1.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

# Asegurarse de que el script puede importar app (corre desde backend/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ACTIVEEXAM_FLAG = "--activeexam" in sys.argv


async def _seed_activeexam() -> None:
    """Seed en modo activeexam: usa DATABASE_URL directamente sin cargar Settings del full."""
    from app.config_activeexam import ActiveExamSettings
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: Falta la variable de entorno DATABASE_URL.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ActiveExamSettings requiere jwt_own_secret y embedding_encryption_key; en seed
    # solo usamos DATABASE_URL, por lo que pasamos placeholders para las otras.
    # Usamos directamente la URL del entorno para construir el engine activeexam.
    # Normalizar el esquema para asyncpg.
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgresql://"):]

    print(f"[activeexam] Conectando a: {database_url[:30]}...", file=sys.stderr)

    engine = create_activeexam_engine(database_url)
    factory = create_activeexam_session_factory(engine)

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
    pw_coordinador = os.environ.get("SEED_COORDINADOR_PASSWORD")
    pw_admin = os.environ.get("SEED_ADMIN_PASSWORD")
    pw_tutor = os.environ.get("SEED_TUTOR_PASSWORD")
    # c-78: el rol PROFESOR se agrego con el change y el seed no lo cubria, asi
    # que no habia forma de probarlo sin crear el usuario a mano.
    pw_profesor = os.environ.get("SEED_PROFESOR_PASSWORD")

    if not all([pw_estudiante, pw_coordinador, pw_admin, pw_tutor, pw_profesor]):
        print(
            "ERROR: Faltan variables de entorno SEED_ESTUDIANTE_PASSWORD, "
            "SEED_COORDINADOR_PASSWORD, SEED_ADMIN_PASSWORD, SEED_TUTOR_PASSWORD "
            "y/o SEED_PROFESOR_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)

    usuarios_seed = [
        {
            "username": "estudiante1",
            "email": "estudiante@activeexam.local",
            "password": pw_estudiante,
            "roles": ["estudiante"],
            "nombre": "Estudiante",
            "apellido": "Prueba1",
        },
        {
            "username": "estudiante2",
            "email": "estudiante2@activeexam.local",
            "password": pw_estudiante,
            "roles": ["estudiante"],
            "nombre": "Estudiante",
            "apellido": "Prueba2",
        },
        {
            "username": "estudiante3",
            "email": "estudiante3@activeexam.local",
            "password": pw_estudiante,
            "roles": ["estudiante"],
            "nombre": "Estudiante",
            "apellido": "Prueba3",
        },
        {
            "username": "estudiante4",
            "email": "estudiante4@activeexam.local",
            "password": pw_estudiante,
            "roles": ["estudiante"],
            "nombre": "Estudiante",
            "apellido": "Prueba4",
        },
        {
            # c-76: el rol "proctor" fue eliminado; el COORDINADOR absorbe la
            # supervision global + veredicto. El usuario de seed pasa a coordinador.
            # Se conserva el email proctor@activeexam.local para idempotencia (no
            # re-crea si ya existe; la migracion 0068 ya remapeo su rol en DB),
            # pero el rol sembrado es "coordinador". No hay otro coordinador de
            # seed, asi que no se duplica.
            "username": "coordinador1",
            "email": "proctor@activeexam.local",
            "password": pw_coordinador,
            "roles": ["coordinador"],
            "nombre": "Coordinador",
            "apellido": "Prueba",
        },
        {
            "username": "admin",
            "email": "admin@activeexam.local",
            "password": pw_admin,
            "roles": ["admin_sistema"],
            "nombre": "Admin",
            "apellido": "Sistema",
        },
        {
            # Tutor (gestión académica) a cargo de la Comisión C1 de PROG1.
            # Queda asignado como docente_id de la comisión en _seed_docente_comision().
            "username": "tutor1",
            "email": "tutor@activeexam.local",
            "password": pw_tutor,
            "roles": ["tutor"],
            "nombre": "Tutor",
            "apellido": "Prueba",
        },
        {
            # Profesor (c-78, E-04/D11): crea examenes y gestiona el banco de SUS
            # materias, pero NO emite el veredicto de integridad — esa decision es
            # exclusiva del COORDINADOR (regla dura #5: quien pone la nota no
            # decide si hubo fraude). Queda asignado a PROG1 en
            # _seed_profesor_materia(), que es lo que le da alcance a algo.
            "username": "profesor1",
            "email": "profesor@activeexam.local",
            "password": pw_profesor,
            "roles": ["profesor"],
            "nombre": "Profesor",
            "apellido": "Prueba",
        },
    ]

    creados = 0
    existentes = 0
    actualizados = 0

    async with factory() as session:
        for datos in usuarios_seed:
            # Idempotencia: no insertar si ya existe.
            result = await session.execute(
                select(UsuarioModel).where(
                    UsuarioModel.username == datos["username"]
                )
            )
            existente = result.scalar_one_or_none()
            if existente is not None:
                # Convergencia no-destructiva de nombre/apellido: si el seed cambió
                # el nombre de un usuario que ya existe (p. ej. renombrar los EST de
                # prueba), lo actualizamos en vez de saltearlo. No toca password,
                # email, roles ni datos que el usuario pueda haber editado.
                cambios = []
                if existente.nombre != datos.get("nombre"):
                    existente.nombre = datos.get("nombre")
                    cambios.append("nombre")
                if existente.apellido != datos.get("apellido"):
                    existente.apellido = datos.get("apellido")
                    cambios.append("apellido")
                if cambios:
                    print(
                        f"  [update] {datos['username']} -> "
                        f"{datos.get('nombre')} {datos.get('apellido')} ({', '.join(cambios)})"
                    )
                    actualizados += 1
                else:
                    print(f"  [skip] Usuario ya existe: {datos['username']}")
                    existentes += 1
                continue

            usuario = UsuarioModel(
                username=datos["username"],
                email=datos["email"],
                roles=datos["roles"],
                password_hash=hashear_password(datos["password"]),  # type: ignore[arg-type]
                auth_provider=auth_provider,
                attrs_federados={},
                nombre=datos.get("nombre"),
                apellido=datos.get("apellido"),
            )
            session.add(usuario)
            print(f"  [create] {datos['username']} ({', '.join(datos['roles'])})")
            creados += 1

        await session.commit()

    print(
        f"\nSeed completado: {creados} creados, {actualizados} actualizados, "
        f"{existentes} ya existentes."
    )

    # Contenido académico demo: materia + comisión + examen (idempotente).
    await _seed_contenido(factory)

    # Asignar el tutor seed (tutor1) como tutor a cargo de la Comisión C1
    # de PROG1 (idempotente). Sin esto, la comisión queda sin tutor.
    await _seed_docente_comision(factory)

    # Asignar el profesor seed (profesor1) a PROG1 (idempotente). Sin materia
    # asignada el rol no alcanza nada: su permiso es sobre LO SUYO.
    await _seed_profesor_materia(factory)

    # Matriculación demo: los estudiantes seed quedan inscriptos a la Comisión C1
    # (idempotente). Con el gate de inscripción (C-71), sin esto no verían el examen.
    await _seed_matriculaciones(factory)


async def _seed_docente_comision(factory) -> None:
    """Asigna tutor1 como tutor a cargo de la Comisión C1 de PROG1 (idempotente).

    El tutor es el eslabón que vuelve derivable quién devuelve la nota
    (examen.comision_id → comision_tutor.tutor_id) y contra qué se valida "lo
    suyo" del rol tutor. Sin esta asignación la comisión queda sin tutor.

    c-79 reemplazó `comision.docente_id` por la tabla puente N:M `comision_tutor`
    (una comisión puede tener varios tutores) y la migración 0093 dropeó la
    columna vieja.
    """
    from app.infrastructure.persistence.models.comision_tutor import ComisionTutorModel
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    MATERIA_CODIGO = "PROG1"
    COMISION_CODIGO = "C1"
    TUTOR_ID = "tutor1"

    async with factory() as session:
        tutor = (
            await session.execute(
                select(UsuarioModel).where(UsuarioModel.username == TUTOR_ID)
            )
        ).scalar_one_or_none()
        if tutor is None:
            print(f"  [skip] docente-comisión: no existe el tutor {TUTOR_ID}")
            return

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
            print("  [skip] docente-comisión: no existe la comisión PROG1/C1 todavía")
            return

        # c-78: el seed seguia escribiendo `comision.docente_id`, columna que la
        # migracion 0093 DROPEO (c-79 la reemplazo por la tabla puente N:M
        # `comision_tutor`). El seed reventaba con AttributeError a mitad de
        # camino, asi que un `docker compose up` limpio dejaba la base a medio
        # sembrar: sin tutor asignado y sin las matriculaciones que van despues.
        ya_asignado = (
            await session.execute(
                select(ComisionTutorModel).where(
                    ComisionTutorModel.comision_id == comision.id,
                    ComisionTutorModel.tutor_id == tutor.id,
                )
            )
        ).scalar_one_or_none()
        if ya_asignado is not None:
            print(f"  [skip] {TUTOR_ID} ya es tutor de {MATERIA_CODIGO}/{COMISION_CODIGO}")
            return

        session.add(ComisionTutorModel(comision_id=comision.id, tutor_id=tutor.id))
        await session.commit()
        print(f"  [update] {TUTOR_ID} asignado como tutor de {MATERIA_CODIGO}/{COMISION_CODIGO}")


async def _seed_profesor_materia(factory) -> None:
    """Asigna profesor1 a la materia PROG1 (idempotente, c-78).

    El PROFESOR se define por su alcance: crea exámenes y gestiona el banco de
    SUS materias. Sin una materia asignada el rol no alcanza nada y no se puede
    probar — que es como quedaba antes, porque el seed ni siquiera creaba el
    usuario.

    La asignación es a la MATERIA (tabla `materia_profesor`), no a la comisión:
    el profesor arma el examen de la materia, el tutor supervisa la comisión.
    """
    from sqlalchemy import select

    from app.infrastructure.persistence.models.comision_tutor import (
        MateriaProfesorModel,
    )
    from app.infrastructure.persistence.models.exam_content import MateriaModel
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    MATERIA_CODIGO = "PROG1"
    PROFESOR_ID = "profesor1"

    async with factory() as session:
        profesor = (
            await session.execute(
                select(UsuarioModel).where(UsuarioModel.username == PROFESOR_ID)
            )
        ).scalar_one_or_none()
        if profesor is None:
            print(f"  [skip] profesor-materia: no existe el profesor {PROFESOR_ID}")
            return

        materia = (
            await session.execute(
                select(MateriaModel).where(MateriaModel.codigo == MATERIA_CODIGO)
            )
        ).scalar_one_or_none()
        if materia is None:
            print(f"  [skip] profesor-materia: no existe la materia {MATERIA_CODIGO}")
            return

        ya_asignado = (
            await session.execute(
                select(MateriaProfesorModel).where(
                    MateriaProfesorModel.materia_id == materia.id,
                    MateriaProfesorModel.profesor_id == profesor.id,
                )
            )
        ).scalar_one_or_none()
        if ya_asignado is not None:
            print(f"  [skip] {PROFESOR_ID} ya es profesor de {MATERIA_CODIGO}")
            return

        session.add(
            MateriaProfesorModel(materia_id=materia.id, profesor_id=profesor.id)
        )
        await session.commit()
        print(f"  [update] {PROFESOR_ID} asignado como profesor de {MATERIA_CODIGO}")


async def _seed_matriculaciones(factory) -> None:
    """Matricula SOLO a estudiante1 en la Comisión C1 (idempotente).

    Con el gate de inscripción (C-71) el alumno solo ve/rinde exámenes de las
    comisiones donde está inscripto. estudiante1 queda inscripto en Comisión C1
    (demo del gate, sin examen sembrado — ver c-78). estudiante2..4 quedan
    LIBRES a propósito, para demostrar el flujo de inscripción desde el panel
    del docente.
    """
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.inscripcion import InscripcionModel
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    MATERIA_CODIGO = "PROG1"
    COMISION_CODIGO = "C1"
    # Solo estudiante1 queda inscripto: así hay UN alumno que puede rendir (demo del
    # gate de inscripción, C-71). estudiante2..4 quedan LIBRES a propósito, para
    # poder demostrar el flujo de inscripción desde el panel del docente (si
    # estuvieran los 4 inscriptos, el picker los mostraría todos como "Ya
    # inscripto" y no habría a quién inscribir).
    ESTUDIANTES = ["estudiante1"]

    async with factory() as session:
        # Comisión C1 de PROG1 (creada por _seed_contenido).
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
            print("  [skip] matriculación: no existe la comisión PROG1/C1 todavía")
            return

        creadas = 0
        for idn in ESTUDIANTES:
            usuario = (
                await session.execute(
                    select(UsuarioModel).where(UsuarioModel.username == idn)
                )
            ).scalar_one_or_none()
            if usuario is None:
                continue
            existe = (
                await session.execute(
                    select(InscripcionModel.id).where(
                        InscripcionModel.usuario_id == usuario.id,
                        InscripcionModel.comision_id == comision.id,
                    )
                )
            ).scalar_one_or_none()
            if existe is not None:
                print(f"  [skip] matriculación ya existe: {idn} -> {COMISION_CODIGO}")
                continue
            session.add(
                InscripcionModel(usuario_id=usuario.id, comision_id=comision.id)
            )
            print(f"  [create] matriculación {idn} -> {MATERIA_CODIGO}/{COMISION_CODIGO}")
            creadas += 1

        await session.commit()
    print(f"\nMatriculaciones: {creadas} creadas.")


async def _seed_contenido(factory) -> None:
    """Siembra estructura académica demo (idempotente): Programación 1 → Comisión 1.

    NO siembra ningún examen — un examen de demo sin banco de preguntas propio
    no tiene sentido operativo y, al no tener baja lógica (ver c-78 Bloque A),
    volvía a recrearse en cada deploy aunque se borrara a mano. Si se necesita
    un examen de prueba, se crea manualmente desde el panel de administración.
    """
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        MateriaModel,
    )

    MATERIA_CODIGO = "PROG1"
    MATERIA_NOMBRE = "Programación 1"
    COMISION_CODIGO = "C1"
    COMISION_NOMBRE = "Comisión 1"
    # C-70: código de matriculación de demo (enrolment key) para la Comisión C1.
    COMISION_MATRICULACION = "PROG1-C1"

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
            # C-70: converger el código de matriculación demo a PROG1-C1 (idempotente).
            # Si la comisión preexistía, la migración 0038 le puso un código aleatorio;
            # lo fijamos al demo salvo que otro registro ya lo tenga (unicidad global).
            if comision.codigo_matriculacion != COMISION_MATRICULACION:
                conflicto = (
                    await session.execute(
                        select(ComisionModel.id).where(
                            ComisionModel.codigo_matriculacion == COMISION_MATRICULACION,
                            ComisionModel.id != comision.id,
                        )
                    )
                ).scalar_one_or_none()
                if conflicto is None:
                    comision.codigo_matriculacion = COMISION_MATRICULACION
                    print(f"  [update] codigo_matriculacion -> {COMISION_MATRICULACION}")

        await session.commit()


if __name__ == "__main__":
    if _ACTIVEEXAM_FLAG:
        print("[seed] Modo: activeexam (DATABASE_URL directo, sin Settings del full)")
        asyncio.run(_seed_activeexam())
    else:
        print("[seed] Modo: full (app.config.Settings)")
        asyncio.run(_seed_full())
