#!/usr/bin/env python
"""Seed de usuarios de prueba con credencial local (C-55 / c-57).

Crea 8 usuarios demo: 4 estudiantes (estudiante1..4) + coordinador + admin_sistema
+ tutor + profesor, con passwords hasheados (bcrypt 12r). Es IDEMPOTENTE: verifica
la existencia antes de insertar (no duplica si ya existen). Los 4 estudiantes
pueblan la cola de revisión con sesiones distinguibles.

Siembra además la raíz de confianza LTI (``lti_deployment_confiable``) si están las
variables ``LTI_*``: sin esa fila NINGÚN alumno entra desde el campus.

NO siembra estructura académica (materias, comisiones, matriculaciones ni exámenes).
Se sacó el 29/8/2026 por decisión del dueño: un "Programación 1 / Comisión 1"
fantasma reaparecía en cada deploy y ensuciaba la base de producción. Esa estructura
la carga cada institución desde el panel.

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
    Tutor:        username=tutor1        | email=tutor@activeexam.local
    Profesor:     username=profesor1     | email=profesor@activeexam.local

    Los 4 estudiantes comparten SEED_ESTUDIANTE_PASSWORD. El tutor usa
    SEED_TUTOR_PASSWORD y el profesor SEED_PROFESOR_PASSWORD. Ninguno nace con
    comisión ni materia a cargo: eso se asigna desde el panel.

VARIABLES LTI (opcionales; sin las cuatro no se siembra el deployment):
    LTI_ISS, LTI_CLIENT_ID, LTI_DEPLOYMENT_ID, LTI_JWKS_URI
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
            # Tutor (gestión académica). Queda sin comisión a cargo: la estructura
            # académica ya no se siembra, la carga cada institución.
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
            # decide si hubo fraude). Nace sin materias asignadas: hay que darle
            # alcance desde el panel para que su rol alcance algo.
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

    # Recuperacion de acceso (ver `reestablecer_passwords`). Va DESPUES del alta,
    # asi una corrida sola sirve tanto para una base vacia como para converger las
    # claves de una base que ya tenia los usuarios.
    await reestablecer_passwords(
        factory,
        {d["username"]: d["password"] for d in usuarios_seed},  # type: ignore[misc]
        habilitado=_reset_pedido(),
    )

    # Raíz de confianza LTI (idempotente). Va acá y no en una migración porque
    # los valores son del campus de cada institución, no del esquema.
    await _seed_lti_deployment(factory)


def _reset_pedido() -> bool:
    """`SEED_RESET_PASSWORDS` en 1/true/yes/on pide converger las claves."""
    return os.environ.get("SEED_RESET_PASSWORDS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def reestablecer_passwords(
    factory, passwords: dict[str, str], *, habilitado: bool
) -> int:
    """Hace converger la clave de los usuarios del seed a la del entorno.

    ## Por que existe

    El seed es idempotente y, si el usuario ya existe, lo saltea entero: **nunca
    toca el password**. Como default esta bien — pisar la clave que una persona
    eligio seria peor. Pero deja un caso sin salida, encontrado el 26/8/2026
    limpiando produccion:

      1. Se pierde u olvida la clave de `admin`.
      2. Cambiar `SEED_ADMIN_PASSWORD` **no hace nada**, porque el usuario existe.
      3. No queda forma de entrar, salvo escribir el hash a mano en la base.

    A dias de un examen real eso no es aceptable. Con `SEED_RESET_PASSWORDS=1` las
    cuentas del seed vuelven a la clave declarada en las variables.

    ## Lo que NO hace

    - No corre sin que se lo pidan: sin la variable, cero cambios.
    - No crea usuarios (eso es del seed normal): un nombre que no existe se informa.
    - No toca a nadie fuera de `passwords`: la clave de un alumno que entro por el
      campus es suya.

    Destraba tambien el lockout, porque el bloqueo por intentos fallidos es
    exactamente lo que se dispara cuando alguien pelea con una clave que no
    recuerda: restablecerla y dejar la cuenta bloqueada no resolveria nada.

    Devuelve cuantas claves cambio.
    """
    if not habilitado:
        return 0

    from sqlalchemy import select

    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    cambiados = 0
    async with factory() as session:
        for username, password in passwords.items():
            fila = (
                await session.execute(
                    select(UsuarioModel).where(UsuarioModel.username == username)
                )
            ).scalar_one_or_none()
            if fila is None:
                print(f"  [reset] {username}: no existe, se omite")
                continue

            fila.password_hash = hashear_password(password)
            fila.intentos_fallidos = 0
            fila.bloqueado_hasta = None
            cambiados += 1
            print(f"  [reset] {username}: clave restablecida")
        await session.commit()

    if cambiados:
        print(f"\nSEED_RESET_PASSWORDS: {cambiados} clave(s) restablecida(s).")
    return cambiados


async def _seed_lti_deployment(factory) -> None:
    """Siembra la raiz de confianza LTI del campus (idempotente).

    Sin una fila activa en ``lti_deployment_confiable`` TODO launch desde el
    campus muere en ``POST /api/v1/lti/login`` con ``403 lti_iss_no_confiable``,
    antes de mirar que usuario es: no entra NINGUN alumno. Esa fila no tenia
    seed ni migracion, asi que cada vez que se recreaba la base habia que
    restaurarla a mano desde un backup. Un dato del que depende todo el acceso
    no puede depender de que alguien se acuerde.

    Los valores vienen del entorno y NUNCA del codigo: este repo es publico y el
    emisor es el campus concreto de cada institucion. Sin las cuatro variables no
    hace nada (un entorno que no usa LTI no necesita esto) y NO rompe el arranque:
    el CMD del contenedor encadena seed y uvicorn.

    No va en una migracion de Alembic por lo mismo: el esquema es igual para
    todos, estos valores no.

    Convergencia deliberadamente conservadora: si la fila ya existe no se toca.
    Desactivarla es como se corta el acceso de un campus comprometido, y un
    redeploy que la reactivara seria un bypass.
    """
    # ComisionModel NO se usa acá, pero tiene que estar en el registry de SQLAlchemy:
    # `lti_deployment_confiable.comision_id` es una FK a `comision`, y sin el modelo
    # cargado el mapper falla con NoReferencedTableError apenas se toca la tabla.
    # Antes lo importaba de rebote el seed de contenido académico; al sacarlo, el
    # seed creaba los usuarios y moría justo antes de sembrar el LTI.
    from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
        ComisionModel,
    )
    from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel

    iss = os.environ.get("LTI_ISS")
    client_id = os.environ.get("LTI_CLIENT_ID")
    deployment_id = os.environ.get("LTI_DEPLOYMENT_ID")
    jwks_uri = os.environ.get("LTI_JWKS_URI")

    if not all([iss, client_id, deployment_id, jwks_uri]):
        print(
            "  [skip] LTI sin configurar (falta LTI_ISS / LTI_CLIENT_ID / "
            "LTI_DEPLOYMENT_ID / LTI_JWKS_URI): no se siembra el deployment."
        )
        return

    async with factory() as session:
        existente = (
            await session.execute(
                select(LtiDeploymentConfiableModel).where(
                    LtiDeploymentConfiableModel.iss == iss,
                    LtiDeploymentConfiableModel.client_id == client_id,
                    LtiDeploymentConfiableModel.deployment_id == deployment_id,
                )
            )
        ).scalar_one_or_none()

        if existente is not None:
            estado = "activo" if existente.activo else "DESACTIVADO a mano"
            print(f"  [skip] deployment LTI ya existe ({estado}): {iss}")
            return

        session.add(
            LtiDeploymentConfiableModel(
                iss=iss,
                client_id=client_id,
                deployment_id=deployment_id,
                jwks_uri=jwks_uri,
                comision_id=None,
                activo=True,
            )
        )
        await session.commit()
        print(f"  [create] deployment LTI de confianza: {iss} (deployment {deployment_id})")


if __name__ == "__main__":
    if _ACTIVEEXAM_FLAG:
        print("[seed] Modo: activeexam (DATABASE_URL directo, sin Settings del full)")
        asyncio.run(_seed_activeexam())
    else:
        print("[seed] Modo: full (app.config.Settings)")
        asyncio.run(_seed_full())
