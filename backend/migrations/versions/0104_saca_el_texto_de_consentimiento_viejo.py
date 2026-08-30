"""0104 - borra el texto de consentimiento viejo sembrado por 0019.

Revision ID: 0104
Revises: 0103
Create Date: 2026-08-29

## Por que

La migracion 0019 sembro un texto de consentimiento que quedo obsoleto en dos
sentidos, y que sigue apareciendo en cualquier base donde esa migracion corrio
(desarrollo, y cualquier instalacion nueva).

**1. Prometia cosas que el sistema no hace.** Decia "mediante tu camara y la
captura de pantalla": la pantalla NO se graba ni se fotografia en ningun momento.
Tambien hablaba de "cifrada at-rest" y "WORM", que es jerga y ademas describe una
infraestructura que no es la que corre hoy. Un consentimiento que describe mal el
tratamiento no sirve como consentimiento.

**2. Citaba una norma en un texto para alumnos.** Decision del dueno (29/8/2026):
las citas legales se sacan de todo lo que lee un alumno. Confunden a quien las
lee y no aportan nada a la comprension de que se hace con sus datos.

El texto vigente vive en `app/domain/consent_flow/text_catalog.py` (`_V1`), esta
escrito en lenguaje claro y es el que la app usa cuando la tabla esta vacia
— que es exactamente como corre produccion hoy.

## Que hace

Borra la fila `v1` SOLO si su contenido es el viejo (se reconoce porque menciona
la norma). Si alguien edito el texto a mano, la fila NO se toca: no es tarea de
una migracion pisar lo que un administrador escribio a proposito.

Sin fila, la app cae en el catalogo del codigo. No hay perdida: el registro de
QUIEN consintio y QUE version acepto vive en `consentimiento_perfil`, que es
append-only y no se toca acá.

## Downgrade

No repone el texto viejo a proposito: volver a mostrarle a un alumno un
consentimiento que describe mal el tratamiento seria un retroceso, no una
reversion util. El downgrade queda como no-op explicito.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0104"
down_revision = "0103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # La tabla puede no existir en instalaciones que nunca corrieron 0018.
    existe = conn.execute(
        sa.text("SELECT to_regclass('public.consent_texto_version') IS NOT NULL")
    ).scalar()
    if not existe:
        return

    conn.execute(
        sa.text(
            "DELETE FROM consent_texto_version "
            "WHERE version = 'v1' AND bloques::text LIKE '%25.326%'"
        )
    )


def downgrade() -> None:
    """No-op: ver el docstring. No se repone un texto que describe mal el trato."""
    pass
