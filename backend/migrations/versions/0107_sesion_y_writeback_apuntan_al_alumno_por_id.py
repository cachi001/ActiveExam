"""La sesión y el write-back apuntan al alumno por su id, no por un texto.

PROBLEMA
--------
El sistema referencia al usuario por su UUID en ONCE tablas (inscripciones,
consentimiento, foto, biometría, refresh tokens, asignaciones de docentes…), con
clave foránea de verdad. En TRES no: ``proctoring_session``,
``moodle_writeback_estado`` y ``moodle_writeback_audit``, que lo identifican con
dos textos — el username y el correo — y joinean por ahí.

Son justo las que registran la evidencia del examen y la devolución de la nota.

El username lo ELIGE la persona en su primer ingreso por el campus, y el correo
también puede cambiar. Cuando cambian los dos, el join se queda sin nada: el
tutor deja de ver de quién es la sesión y la nota pierde el camino a Moodle. Y el
id estaba disponible en el momento de crear la sesión: es el ``sub`` del token,
que dos líneas más arriba ya se usa para chequear el perfil del alumno.

QUE HACE ESTA MIGRACION
-----------------------
Aditiva. Agrega ``alumno_usuario_id`` (el id de ``usuario``) a
``proctoring_session`` y a ``moodle_writeback_estado``, y rellena las filas
existentes resolviendo el texto contra ``usuario`` (por username o por correo,
mismo criterio que usa hoy el código).

Los textos NO se tocan ni se renombran. Dejan de ser la llave y quedan siendo lo
único que tiene sentido que sean: la foto de qué username y qué correo tenía esa
persona en ese momento, que como evidencia de una rendición sirve. Por eso
tampoco se toca ``moodle_writeback_audit``: es un registro histórico de qué se le
mandó a Moodle, no una tabla por la que se busque a nadie.

SIN CLAVE FORANEA, A PROPOSITO
------------------------------
La columna guarda una referencia, no impone una restricción. Con FK, un id que no
resuelva contra ``usuario`` haría FALLAR el INSERT, y ese INSERT es el que crea la
sesión de examen: un problema de identidad dejaría a alguien sin poder empezar a
rendir. En el camino crítico del examen eso no se negocia.

Sin FK, un id que no resuelve simplemente no joinea y se cae al texto, que es
exactamente el comportamiento anterior. Y como efecto lateral bueno: si algún día
se borra de verdad a un usuario (baja definitiva, DSR), sus sesiones NO
desaparecen con él — son evidencia con cadena de custodia (reglas duras #6 y #7).

ROLLBACK
--------
Dropea las dos columnas. Aditivo: no toca ninguna otra tabla ni dato.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0107"
down_revision = "0106"
branch_labels = None
depends_on = None

_log = logging.getLogger("alembic.runtime.migration")

# (tabla, columna_username, columna_email)
_TABLAS = (
    ("proctoring_session", "alumno_idnumber", "alumno_email"),
    ("moodle_writeback_estado", "alumno_idnumber", "alumno_email"),
)


def upgrade() -> None:
    conn = op.get_bind()

    for tabla, col_user, col_mail in _TABLAS:
        op.add_column(
            tabla,
            sa.Column("alumno_usuario_id", UUID(as_uuid=False), nullable=True),
        )
        op.create_index(f"ix_{tabla}_alumno_usuario_id", tabla, ["alumno_usuario_id"])

        # Backfill: mismo criterio que usa el código (username O correo). El
        # username primero, que es el más específico.
        conn.execute(
            sa.text(
                f"""
                UPDATE {tabla} t
                   SET alumno_usuario_id = u.id
                  FROM usuario u
                 WHERE t.alumno_usuario_id IS NULL
                   AND t.{col_user} IS NOT NULL
                   AND u.username = t.{col_user}
                """
            )
        )
        conn.execute(
            sa.text(
                f"""
                UPDATE {tabla} t
                   SET alumno_usuario_id = u.id
                  FROM usuario u
                 WHERE t.alumno_usuario_id IS NULL
                   AND t.{col_mail} IS NOT NULL
                   AND u.email = t.{col_mail}
                """
            )
        )

        resueltas = conn.execute(
            sa.text(f"SELECT count(*) FROM {tabla} WHERE alumno_usuario_id IS NOT NULL")
        ).scalar_one()
        sin_resolver = conn.execute(
            sa.text(
                f"SELECT count(*) FROM {tabla}"
                f" WHERE alumno_usuario_id IS NULL AND {col_user} IS NOT NULL"
            )
        ).scalar_one()
        _log.info(
            "0107: %s -> %s filas con el alumno resuelto por id; %s con identidad "
            "en texto que no matchea ningún usuario (se siguen resolviendo por el "
            "camino viejo).",
            tabla,
            resueltas,
            sin_resolver,
        )


def downgrade() -> None:
    for tabla, _, _ in _TABLAS:
        op.drop_index(f"ix_{tabla}_alumno_usuario_id", table_name=tabla)
        op.drop_column(tabla, "alumno_usuario_id")
