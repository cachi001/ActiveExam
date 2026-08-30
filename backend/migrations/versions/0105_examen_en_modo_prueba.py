"""0105 - modo prueba del examen + alumnos habilitados a verlo.

Revision ID: 0105
Revises: 0104
Create Date: 2026-08-29

## Por que

Probar un examen antes de tomarlo no tenia forma de hacerse sin ensuciar datos
reales. Las dos alternativas que habia eran malas:

- **Rendirlo con una cuenta de alumno**: la rendicion cuenta, genera nota, entra
  a las estadisticas, puede caer en la Cola de revision, el examen ya no puede
  volver a borrador, y esa sesion NO se puede borrar (el endpoint de borrado
  rechaza las sesiones de examen real: son evidencia academica).
- **Que rinda el docente**: el backend ya lo soporta (`es_prueba`), pero las
  pantallas de rendir exigen rol estudiante, y la biometria tambien lo exige del
  lado del servidor. El docente no tiene consentimiento ni foto de referencia, y
  no tiene por que tenerlos.

## Que agrega

**`examen_contenido.modo_prueba`**: mientras esta en true, el examen es un ensayo.
Solo lo ven los alumnos habilitados (no la comision entera) y toda sesion que se
cree sobre el nace marcada `es_prueba`, con lo cual hereda todo lo que ya estaba
construido: no cuenta como intento, no genera nota, no va a Moodle, no entra a la
Cola de revision ni a las estadisticas, y se puede borrar desde el detalle.

**`examen_prueba_habilitado`**: que alumnos pueden verlo. Es una lista explicita
y no la comision entera, para que un ensayo no le aparezca a 70 personas.

El alumno rinde con SU cuenta y su flujo real (consentimiento, foto, biometria,
calibracion): es la unica forma de que el ensayo pruebe lo que de verdad va a
pasar el dia del examen.

## Notas

`modo_prueba` es independiente de `borrador`: un examen en modo prueba se puede
rendir aunque no este habilitado para la comision, que es justo el punto (probarlo
antes de soltarlo). El ON DELETE CASCADE en las dos FK evita filas huerfanas al
borrar el examen o dar de baja al usuario.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column(
            "modo_prueba",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    op.create_table(
        "examen_prueba_habilitado",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "examen_contenido_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("examen_contenido.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "usuario_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Habilitar dos veces a la misma persona es la misma habilitacion.
        sa.UniqueConstraint(
            "examen_contenido_id", "usuario_id", name="uq_examen_prueba_habilitado"
        ),
    )
    op.create_index(
        "ix_examen_prueba_habilitado_examen",
        "examen_prueba_habilitado",
        ["examen_contenido_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_examen_prueba_habilitado_examen", table_name="examen_prueba_habilitado")
    op.drop_table("examen_prueba_habilitado")
    op.drop_column("examen_contenido", "modo_prueba")
