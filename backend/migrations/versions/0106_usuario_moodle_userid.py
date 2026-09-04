"""La identidad de Moodle deja de vivir escondida en el username.

PROBLEMA
--------
Quien entra por el link del campus nace con un username inventado por nosotros:
``lti:{deployment_id}:{sub}``, donde ``sub`` ES el userid de Moodle. Después la
persona ELIGE su propio username (el backend se lo exige en el primer ingreso) y
ese valor se reemplaza: la identidad de Moodle desaparece con él.

Desde entonces, reconocer a quien vuelve depende del CORREO, que no identifica a
una persona — se puede cambiar, y dos personas pueden compartirlo. Verificado con
tests: dos alumnos distintos que comparten dirección terminan en la misma cuenta,
y una cuenta cuyo correo cambió termina duplicada.

QUE HACE ESTA MIGRACION
-----------------------
Aditiva, sobre ``usuario``:
  - ``moodle_userid``      -> el ``sub`` del launch (el userid de Moodle).
  - ``lti_deployment_id``  -> de qué campus es ese número (dos Moodles pueden
    tener ambos un usuario 7).
  - índice por el par, para que la búsqueda del reingreso sea barata.

Y RELLENA lo que ya se puede saber, de dos fuentes:
  1. ``attrs_federados->>'moodle_userid'``, que lo guardan las cuentas creadas
     después de c-78.
  2. el username ``lti:{deployment}:{sub}`` de las que todavía no lo cambiaron.

Las que ya cambiaron su username Y son anteriores a c-78 no se pueden resolver
desde la base: quedan en NULL y se completan solas la próxima vez que la persona
entre por el campus (autorrelleno en el provisioning).

SIN UNIQUE, A PROPOSITO
-----------------------
Si en producción ya hay cuentas duplicadas por este bug, una migración con UNIQUE
FALLA y bloquea el deploy — el peor momento posible es justamente el día que se
descubre. Se crea un índice común y se DEJA CONSTANCIA de los duplicados en el
log para decidirlos a mano. El UNIQUE se agrega en otra migración, cuando la
tabla esté limpia.

ROLLBACK
--------
Dropea las dos columnas y el índice. Aditivo: no toca ninguna otra tabla.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op

revision = "0106"
down_revision = "0105"
branch_labels = None
depends_on = None

_log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    op.add_column("usuario", sa.Column("moodle_userid", sa.String(length=64), nullable=True))
    op.add_column(
        "usuario", sa.Column("lti_deployment_id", sa.String(length=255), nullable=True)
    )
    op.create_index(
        "ix_usuario_identidad_lti",
        "usuario",
        ["lti_deployment_id", "moodle_userid"],
    )

    conn = op.get_bind()

    # Fuente 1: lo que ya está guardado en attrs_federados (cuentas post c-78).
    conn.execute(
        sa.text(
            """
            UPDATE usuario
               SET moodle_userid = attrs_federados->>'moodle_userid',
                   lti_deployment_id = attrs_federados->>'lti_deployment_id'
             WHERE auth_provider = 'lti'
               AND moodle_userid IS NULL
               AND attrs_federados->>'moodle_userid' IS NOT NULL
            """
        )
    )

    # Fuente 2: el username sintético de quienes todavía no lo cambiaron.
    # `lti:{deployment}:{sub}` — el sub es todo lo que va después del ÚLTIMO ':'
    # y el deployment lo que queda en el medio. Se parte así (y no por posición)
    # porque un deployment_id podría contener ':'.
    conn.execute(
        sa.text(
            """
            UPDATE usuario
               SET moodle_userid = substring(username from '[^:]+$'),
                   lti_deployment_id = substring(username from '^lti:(.*):[^:]+$')
             WHERE auth_provider = 'lti'
               AND moodle_userid IS NULL
               AND username LIKE 'lti:%:%'
            """
        )
    )

    resueltas = conn.execute(
        sa.text(
            "SELECT count(*) FROM usuario"
            " WHERE auth_provider = 'lti' AND moodle_userid IS NOT NULL"
        )
    ).scalar_one()
    pendientes = conn.execute(
        sa.text(
            "SELECT count(*) FROM usuario"
            " WHERE auth_provider = 'lti' AND moodle_userid IS NULL"
        )
    ).scalar_one()
    _log.info(
        "0106: identidad LTI resuelta en %s cuentas; %s quedan en NULL "
        "(se completan solas al próximo ingreso por el campus).",
        resueltas,
        pendientes,
    )

    # Duplicados: NO se tocan. Solo se listan para decidirlos a mano.
    duplicados = conn.execute(
        sa.text(
            """
            SELECT lti_deployment_id, moodle_userid, count(*) AS cuantas,
                   string_agg(username, ', ' ORDER BY creado_en) AS cuentas
              FROM usuario
             WHERE moodle_userid IS NOT NULL
             GROUP BY lti_deployment_id, moodle_userid
            HAVING count(*) > 1
            """
        )
    ).all()
    if duplicados:
        _log.warning(
            "0106: hay %s identidades de Moodle con MAS DE UNA cuenta. NO se "
            "fusionan acá: mover consentimiento, biometría, sesiones y notas es "
            "una decisión humana. Listado:",
            len(duplicados),
        )
        for fila in duplicados:
            _log.warning(
                "0106:   deployment=%s moodle_userid=%s -> %s cuentas: %s",
                fila.lti_deployment_id,
                fila.moodle_userid,
                fila.cuantas,
                fila.cuentas,
            )
    else:
        _log.info("0106: no hay identidades de Moodle duplicadas.")


def downgrade() -> None:
    op.drop_index("ix_usuario_identidad_lti", table_name="usuario")
    op.drop_column("usuario", "lti_deployment_id")
    op.drop_column("usuario", "moodle_userid")
