"""Configuracion compartida de pytest.

Registra el marker ``requires_stack`` para los tests que necesitan el stack de
Docker Compose levantado (DB/storage/IdP). Esos tests se SALTAN automaticamente
salvo que ``RUN_STACK_TESTS=1`` este en el entorno, para que la suite unitaria
corra sin servicios externos.

Ademas restaura el esquema completo antes de CADA modulo de test (ver
``_esquema_completo_por_modulo``): sin eso, la suite entera no da senal.

CORRE LOS TESTS CONTRA UNA BASE APARTE. Varios modulos hacen
``DROP TABLE ... CASCADE`` de tablas compartidas (usuario, materia,
examen_contenido, proctoring_session): apuntar la suite a la base de desarrollo
la deja sin tablas, sin datos y sin FK, y la app arranca en crashloop porque el
seed no encuentra `materia`. No es hipotetico — paso tres veces el 28/8/2026.

    docker exec -e DATABASE_URL="postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring_test" \\
        activeexam-dev-backend-1 python -m pytest tests/ -q

La base se crea una sola vez con
``CREATE DATABASE proctoring_test OWNER proctoring;`` mas
``CREATE EXTENSION IF NOT EXISTS pgcrypto;`` (los ids son ``gen_random_uuid()``).
El resto del esquema lo levanta el hook de abajo desde los modelos.
"""

from __future__ import annotations

import asyncio
import os

import pytest


#: Sufijo obligatorio de la base contra la que corre la suite. Los modulos hacen
#: DROP TABLE de tablas compartidas, asi que apuntar a la base de desarrollo la
#: destruye: paso tres veces, y el sintoma no es obvio (la app empieza a tirar
#: 500 "current transaction is aborted" porque falta una tabla suelta).
_SUFIJO_BASE_DE_TEST = "_test"


def _abortar_si_apunta_a_la_base_equivocada() -> None:
    """Corta la corrida si DATABASE_URL no es una base de test.

    Sin esto, olvidarse la variable hace que la suite corra contra la base de
    desarrollo y le borre tablas. Es preferible no correr ningun test a dejar el
    entorno roto de una forma que despues se investiga como si fuera un bug de
    la aplicacion.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return  # sin URL los tests de integracion se saltan solos

    nombre = url.rsplit("/", 1)[-1].split("?")[0]
    if not nombre.endswith(_SUFIJO_BASE_DE_TEST):
        raise pytest.UsageError(
            f"DATABASE_URL apunta a {nombre!r} y la suite DROPEA tablas: eso "
            "destruye esa base. Usa una que termine en '_test' "
            "(por ejemplo proctoring_test)."
        )


def pytest_configure(config: pytest.Config) -> None:
    _abortar_si_apunta_a_la_base_equivocada()
    config.addinivalue_line(
        "markers",
        "requires_stack: el test necesita el stack de Docker Compose levantado "
        "(DB/storage/IdP). Se salta salvo RUN_STACK_TESTS=1.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if os.environ.get("RUN_STACK_TESTS") == "1":
        return
    skip = pytest.mark.skip(
        reason="Requiere el stack levantado. Exporta RUN_STACK_TESTS=1 con el "
        "compose arriba para ejecutarlo."
    )
    for item in items:
        if "requires_stack" in item.keywords:
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# Aislamiento de esquema entre modulos
# ---------------------------------------------------------------------------
#
# PROBLEMA: varios modulos hacen `DROP TABLE ... CASCADE` de tablas COMPARTIDAS
# (usuario, materia, comision, examen_contenido, proctoring_session, ...) en su
# setup/teardown de modulo, para arrancar de cero. El modulo que corre despues
# encuentra tierra arrasada y revienta con UndefinedTable, aunque su codigo este
# perfecto. Resultado: los archivos pasan de a uno pero la suite completa no.
#
# SOLUCION: antes de cada modulo se re-crea el esquema faltante (create_all con
# checkfirst=True: crea SOLO lo que no existe, no toca datos ni tablas vivas).
# No se toca ningun fixture de los modulos: los que dropean y crean lo suyo
# siguen funcionando igual, y los que asumen un esquema ya migrado dejan de
# depender del orden de ejecucion.


# Tablas que NO se pueden recrear desde el modelo ORM: su definicion REAL vive en
# la migracion e incluye objetos que el modelo no describe. Crear una version
# "parecida" es peor que no crearla — deja pasar tests contra una tabla que no se
# comporta como la de produccion.
#   - audit_log: dos triggers (audit_log_encadenar / append-only). hash_self lo
#     materializa el trigger; sin el, la cadena de hash tamper-evident no existe.
#   - foto_referencia: tiene DOS variantes fisicas incompatibles (full = uri_storage
#     + bucket contra MinIO; activeexam = foto_bytes BYTEA). El modelo del full y el del
#     activeexam NO se pueden importar juntos (misma tabla, columnas distintas). Cual
#     corresponde lo decide la migracion del entorno, no este hook.
_TABLAS_QUE_NO_SE_RECREAN = frozenset({"audit_log", "foto_referencia"})

#: Copia EXACTA del seed de la migracion 0014 (mismos valores que DEFAULT_CONFIG).
#: Idempotente por el ON CONFLICT: correrlo por modulo no pisa nada.
_SEED_CONFIG_SISTEMA = """
    INSERT INTO configuracion_sistema
        (id, face_absent_ms, multiple_faces_frames, gaze_deviation_threshold,
         gaze_sustained_ms, gaze_fixation_tolerance, umbral_cola_revision,
         detectores_activos, retencion_dias_default, consent_version_vigente, version)
    VALUES
        ('global', 3000, 5, 0.20, 2500, 0.25, 70,
         '["rostro_ausente","multiples_rostros","mirada_desviada_sostenida",
           "perdida_de_foco","cambio_pestana","monitor_adicional",
           "salida_pantalla_completa","copiar_pegar"]'::jsonb,
         365, 'v1', 1)
    ON CONFLICT (id) DO NOTHING
"""


def _importar_todos_los_modelos() -> None:
    """Puebla Base.metadata con TODAS las tablas (import con efecto de registro)."""
    from app.infrastructure.persistence.models import (  # noqa: F401
        alternative_request,
        audit_log,
        chat_pausa,
        comision_tutor,
        event,
        exam_content,
        inscripcion,
        lti,
        moodle_writeback,
        observacion,
        proctoring,
        transactional,
    )


#: Las FK que YA estan, por (tabla, columnas). Se compara por columnas y no por
#: nombre porque el nombre lo genera Postgres cuando el modelo no lo declara.
_FKS_EXISTENTES = """
    SELECT c.conrelid::regclass::text AS tabla,
           array_agg(a.attname ORDER BY a.attname) AS columnas
    FROM pg_constraint c
    JOIN unnest(c.conkey) AS k(attnum) ON true
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.contype = 'f'
    GROUP BY c.oid, c.conrelid
"""


async def _reponer_fks(engine) -> None:
    """Vuelve a poner las FK que el modelo declara y la base perdio."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import AddConstraint

    from app.infrastructure.persistence.base import Base

    async with engine.begin() as conn:
        tablas = {
            fila[0]
            for fila in await conn.exec_driver_sql(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
        }
        presentes = {
            (fila[0], tuple(sorted(fila[1])))
            for fila in await conn.exec_driver_sql(_FKS_EXISTENTES)
        }

    for tabla in Base.metadata.sorted_tables:
        if tabla.name in _TABLAS_QUE_NO_SE_RECREAN or tabla.name not in tablas:
            continue
        for fk in tabla.foreign_key_constraints:
            columnas = tuple(sorted(c.name for c in fk.columns))
            if (tabla.name, columnas) in presentes:
                continue
            # Cada una en su propia transaccion, igual que las tablas: si una no
            # se puede crear (la tabla apuntada no existe), no se lleva puestas a
            # las demas.
            try:
                async with engine.begin() as conn:
                    await conn.execute(AddConstraint(fk))
                continue
            except Exception:
                pass

            # Suele fallar por filas huerfanas: las dejo pasar la MISMA ausencia
            # de FK que estamos reponiendo. NOT VALID crea la constraint sin
            # revisar lo que ya esta: la cascada y el rechazo vuelven a funcionar
            # de aca en adelante, que es lo que los tests necesitan, y no se
            # borra un solo dato para conseguirlo.
            try:
                ddl = str(AddConstraint(fk).compile(dialect=postgresql.dialect()))
                async with engine.begin() as conn:
                    await conn.exec_driver_sql(f"{ddl.strip()} NOT VALID")
            except Exception:
                continue


@pytest.fixture(scope="module", autouse=True)
def _esquema_completo_por_modulo() -> None:
    """Re-crea las tablas que falten antes de cada modulo (no-op sin DATABASE_URL)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.infrastructure.persistence.base import Base

    from tests._audit_schema import DDL_COMPLETA as DDL_AUDIT_LOG

    _importar_todos_los_modelos()

    async def _crear_faltantes() -> None:
        engine = create_async_engine(url, poolclass=NullPool, future=True)
        try:
            # UNA consulta para saber que hay, en vez de ~45 CREATE ... checkfirst
            # (cada uno con su round-trip y su transaccion) por cada uno de los
            # ~264 modulos de test. Ese barrido costaba ~3 s de setup POR MODULO
            # —hasta en modulos que no tocan la base, como test_architecture— y era
            # el grueso de lo que hacia impracticable correr la suite entera.
            # La semantica no cambia: se sigue creando solo lo que falta.
            async with engine.begin() as conn:
                filas = await conn.exec_driver_sql(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
                existentes = {fila[0] for fila in filas}

            # audit_log primero y por DDL propia: el modelo no describe sus
            # triggers (ver tests/_audit_schema.py).
            if "audit_log" not in existentes:
                try:
                    async with engine.begin() as conn:
                        for sentencia in DDL_AUDIT_LOG:
                            await conn.exec_driver_sql(sentencia)
                except Exception:
                    pass

            # Tabla por tabla y cada una en su propia transaccion: un create_all
            # global aborta TODO ante el primer choque (p. ej. `evento`, que es
            # hypertable de TimescaleDB y a la que checkfirst no le acierta), y
            # entonces no se crearia ninguna de las que si faltan.
            for tabla in Base.metadata.sorted_tables:
                if tabla.name in _TABLAS_QUE_NO_SE_RECREAN:
                    continue
                if tabla.name in existentes:
                    continue
                try:
                    async with engine.begin() as conn:
                        await conn.run_sync(tabla.create, checkfirst=True)
                except Exception:
                    continue  # ya existe o no aplica en esta DB de test

            # Las FK NO vuelven con la tabla. `DROP TABLE usuario CASCADE` no se
            # lleva solo `usuario`: borra tambien las FK de las OTRAS tablas, las
            # que apuntaban a ella. Esas tablas siguen existiendo, asi que el paso
            # de arriba (que solo crea lo que FALTA) no las mira nunca mas y la
            # constraint no vuelve sola.
            #
            # Una FK que falta no rompe de entrada, y por eso es peor: hace PASAR
            # tests que deberian fallar. El que verifica que dar de baja a un
            # docente arrastra su credencial de Moodle no prueba nada si la
            # cascada ya no existe. Ver `test_esquema_de_test_conserva_las_fk.py`.
            await _reponer_fks(engine)

            # El singleton de configuracion_sistema. En produccion lo siembra la
            # migracion 0014; una base de test armada desde el modelo ORM (que es
            # como se arman todas) nunca lo tiene, y sin esa fila el arranque de
            # una sesion de proctoring responde 503 `config_no_disponible`. Eso
            # tumbaba en bloque a todos los modulos que crean una sesion, por una
            # carencia del harness y no por un defecto del codigo.
            try:
                async with engine.begin() as conn:
                    await conn.exec_driver_sql(_SEED_CONFIG_SISTEMA)
            except Exception:
                pass
        finally:
            await engine.dispose()

    try:
        asyncio.run(_crear_faltantes())
    except Exception:
        # Nunca romper la coleccion por esto: si la DB no esta disponible, los
        # propios fixtures del modulo hacen skip con su mensaje.
        pass
