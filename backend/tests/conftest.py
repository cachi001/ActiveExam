"""Configuracion compartida de pytest.

Registra el marker ``requires_stack`` para los tests que necesitan el stack de
Docker Compose levantado (DB/storage/IdP). Esos tests se SALTAN automaticamente
salvo que ``RUN_STACK_TESTS=1`` este en el entorno, para que la suite unitaria
corra sin servicios externos.

Ademas restaura el esquema completo antes de CADA modulo de test (ver
``_esquema_completo_por_modulo``): sin eso, la suite entera no da senal.
"""

from __future__ import annotations

import asyncio
import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
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
