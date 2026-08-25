"""0092 - c-78 E-07/E-08: sorteo de preguntas por intento + examen en borrador.

Revision ID: 0092
Revises: 0091
Create Date: 2026-08-24

PROPOSITO (E-07 — sorteo por intento):
  Hoy el sorteo de preguntas es de ARMADO: `crear-desde-banco` elige N preguntas
  una sola vez, las copia al examen, y los 40 alumnos de la comision rinden esas
  mismas N. Moodle en cambio guarda la CONDICION ("10 preguntas de Unidad 1") y
  resuelve el set al arrancar CADA intento, asi cada alumno recibe preguntas
  distintas.

  Se adopta ese modelo con una diferencia deliberada: el sorteo corre contra el
  POOL YA COPIADO dentro del examen (`pregunta_examen`), NO contra el banco vivo.

  POR QUE ESA DIFERENCIA IMPORTA:
    Moodle referencia el banco, y por eso necesito construir versionado de
    preguntas (4.0+) para que editar una pregunta no le cambie el examen a quien
    esta rindiendo, mas el bloqueo de borrado de categorias en uso. Aun asi le
    queda un agujero documentado: si la categoria se queda sin suficientes
    preguntas al momento del sorteo, el ALUMNO ve un error.

    ActiveExam ya copia las preguntas al examen (la "Opcion B / pool" de la
    migracion 0031). Sorteando de esa copia se obtiene la misma proteccion sin
    versionar nada, y el "no alcanzan las preguntas" se detecta al ARMAR el
    examen, cuando todavia hay alguien mirando que puede corregirlo.

  Dos tablas nuevas:
    - `tramo_sorteo_examen`: la condicion del sorteo (categoria, subcategorias si
      o no, tipos admitidos, cantidad). Es lo que ANTES se perdia: se guardaba el
      resultado del sorteo y no la regla que lo genero.
    - `pregunta_sesion`: que preguntas le tocaron a CADA intento. Con sorteo por
      intento, "las preguntas de este examen" deja de ser un dato del examen y
      pasa a ser un dato del intento — la correccion, la revision y el calculo de
      nota leen de aca. Se persiste al arrancar y no se vuelve a tocar: es lo que
      permite reconstruir exactamente que rindio cada alumno (regla dura #6).

  `examen_contenido.modo_preguntas` decide cual de los dos caminos corre.

PROPOSITO (E-07 — borrador):
  No habia forma de probar un examen sin exponerlo: la ventana apertura/cierre es
  obligatoria y se aplica igual al docente, asi que adelantar la apertura para
  esconderlo tambien te deja afuera a vos. `borrador` lo hace invisible para el
  alumno mientras el docente lo puede rendir en modo prueba.

COMPATIBILIDAD — LA PARTE QUE IMPORTA:
  `modo_preguntas` nace en 'fijo' y `borrador` en false. Los examenes que ya
  existen, y los importados de XML (que no pasan por el armado desde el banco),
  se comportan EXACTAMENTE igual que antes: `pregunta_examen.seleccionada` sigue
  decidiendo que ve el alumno. Ningun lector viejo se rompe y no hay backfill.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: dos columnas nuevas NOT NULL con server_default (no reescriben
  filas) y dos tablas nuevas. Nada se dropea ni se renombra.

REVERSIBILIDAD (downgrade):
  Dropea las dos tablas y las dos columnas. Se pierde la definicion de los sorteos
  y el registro de que preguntas le tocaron a cada intento — los examenes en modo
  'sorteo_por_intento' quedarian sin forma de decidir que mostrar. Por eso el
  downgrade SOLO es seguro si ningun examen paso a ese modo todavia; se deja la
  verificacion explicita abajo en vez de romper en silencio.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column(
            "borrador",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="c-78 E-07: examen en borrador (invisible para el alumno).",
        ),
    )
    op.add_column(
        "examen_contenido",
        sa.Column(
            "modo_preguntas",
            sa.String(24),
            nullable=False,
            server_default="fijo",
            comment="c-78 E-07: 'fijo' | 'sorteo_por_intento'.",
        ),
    )

    op.create_table(
        "tramo_sorteo_examen",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "examen_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("examen_contenido.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SET NULL a proposito: si la categoria del banco desaparece, el tramo
        # sigue sirviendo — las preguntas ya estan copiadas en el examen.
        sa.Column(
            "categoria_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("categoria_pregunta.id", ondelete="SET NULL"),
            nullable=True,
            comment="Categoria del tramo. NULL = Sin clasificar.",
        ),
        sa.Column(
            "incluir_subcategorias",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "tipos",
            postgresql.JSONB(),
            nullable=True,
            comment="Tipos de pregunta admitidos. NULL = cualquiera.",
        ),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("cantidad > 0", name="ck_tramo_sorteo_cantidad_positiva"),
    )
    op.create_index(
        "ix_tramo_sorteo_examen_examen_id", "tramo_sorteo_examen", ["examen_id"]
    )

    op.create_table(
        "pregunta_sesion",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pregunta_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("pregunta_examen.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "session_id", "pregunta_id", name="uq_pregunta_sesion_sesion_pregunta"
        ),
    )
    op.create_index("ix_pregunta_sesion_session_id", "pregunta_sesion", ["session_id"])


def downgrade() -> None:
    # Un examen en 'sorteo_por_intento' se queda sin forma de decidir que mostrar
    # si se dropean estas tablas. Mejor fallar fuerte que dejar examenes rotos.
    conn = op.get_bind()
    en_sorteo = conn.execute(
        sa.text(
            "SELECT count(*) FROM examen_contenido "
            "WHERE modo_preguntas = 'sorteo_por_intento'"
        )
    ).scalar_one()
    if en_sorteo:
        raise RuntimeError(
            f"Hay {en_sorteo} examen(es) en modo 'sorteo_por_intento'. El downgrade "
            "los dejaria sin preguntas resolubles. Pasalos a 'fijo' primero "
            "(fijando su seleccion de preguntas) y volve a intentar."
        )

    op.drop_index("ix_pregunta_sesion_session_id", table_name="pregunta_sesion")
    op.drop_table("pregunta_sesion")
    op.drop_index("ix_tramo_sorteo_examen_examen_id", table_name="tramo_sorteo_examen")
    op.drop_table("tramo_sorteo_examen")
    op.drop_column("examen_contenido", "modo_preguntas")
    op.drop_column("examen_contenido", "borrador")
