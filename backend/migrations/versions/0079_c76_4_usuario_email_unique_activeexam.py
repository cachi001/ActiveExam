"""0079 - c-76-4 (rama activeexam): usuario.email pasa a ser UNIQUE.

Revision ID: 0079
Revises: 0077
Create Date: 2026-08-16

PROPOSITO:
  Vulnerabilidad real encontrada al auditar el login: ``POST /auth/login``
  matchea por ``email OR username`` (ambos formas validas de login), pero
  ``email`` NUNCA tuvo constraint de unicidad — solo ``username``. La query de
  login usa ``scalar_one_or_none()``, que ERROR-EA (``MultipleResultsFound``,
  500 sin capturar) si el WHERE devuelve 2 filas.

  Con auto-registro publico (``POST /auth/register``, en camino a eliminarse)
  cualquiera podia registrarse con ``username`` = el email de otra persona
  real. La proxima vez que la victima intentara loguearse con su propio
  email, la query matcheaba su fila (por email) Y la del atacante (por
  username) -> 500 en vez de 401 -> la victima queda bloqueada del login
  (DoS dirigido) y el 500 en si mismo filtra que ese email existe en el
  sistema (rompe la propiedad "mensaje generico" documentada en el propio
  codigo del endpoint).

  Este constraint cierra el hueco de raiz: dos usuarios nunca pueden
  compartir email, así que el ``OR`` del login nunca puede devolver 2 filas
  por esta via. Complementado con: validacion cruzada username<->email en la
  creacion (schemas de ``users/router.py``), manejo defensivo en el JIT de
  LTI (reusa cuenta por email en vez de crashear — importa para un futuro
  escenario multi-tenant/multi-deployment) y manejo defensivo de
  ``MultipleResultsFound`` en el login.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  Parcialmente aplica: si YA existen filas con emails duplicados, el
  ``ALTER TABLE ... ADD CONSTRAINT UNIQUE`` falla explicitamente (Postgres
  rechaza el ADD CONSTRAINT, no corrompe datos). En ese caso hay que
  deduplicar a mano antes de re-correr esta migracion — no se intenta un
  merge automatico de cuentas duplicadas aqui (decision de negocio, no de
  esquema).

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion: el downgrade solo quita el
  constraint, no toca filas.
"""

from __future__ import annotations

from alembic import op

revision = "0079"
down_revision = "0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_usuario_email", "usuario", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_usuario_email", "usuario", type_="unique")
