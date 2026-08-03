"""0050 - credencial de Moodle POR DOCENTE (token derivado) + service shortname.

Revision ID: 0050
Revises: 0049 (branch slim)
Create Date: 2026-07-29

RAMA: slim

PROPOSITO:
  1) Crea `moodle_credencial_docente`: la credencial personal con la que CADA docente
     devuelve las notas de sus comisiones.
  2) Agrega `moodle_credencial.service_shortname`: el nombre del servicio externo del
     campus, necesario para canjear contrasena por token (`login/token.php?service=`).

  POR QUE IMPORTA:
  Hasta ahora TODA nota se escribia con la cuenta de servicio institucional. En la
  libreta de Moodle eso significa que cada nota figura puesta por un robot: no hay
  forma de saber que docente la devolvio, y la autorizacion ("solo la libreta de mi
  materia") la teniamos que replicar nosotros en vez de dejar que Moodle la imponga.

  Con la credencial personal, la nota se escribe CON LA IDENTIDAD DEL DOCENTE:
  - ATRIBUCION: el historial de calificaciones muestra a la persona.
  - AUTORIZACION: Moodle no lo deja escribir donde no da clase. No hay que confiar
    en que nuestro control este bien puesto.

POR QUE SE GUARDA EL TOKEN Y NO LA CONTRASENA:
  Moodle NO acepta usuario/contrasena en un web service: la unica credencial valida
  es un `wstoken`. La contrasena solo sirve para CANJEARLA por un token en
  `login/token.php`. Entonces se canjea una vez y se descarta.

  Guardar el token es ademas MAS ESTABLE que guardar la contrasena: los tokens de
  Moodle NO se invalidan cuando el usuario cambia su clave (CVE-2016-7038), asi que
  una rotacion de contrasena —obligatoria en muchas universidades— rompe el modelo
  "guardo la contrasena" y no toca el modelo "guardo el token".

  Y el token queda ACOTADO al servicio externo: solo puede llamar a las funciones
  que ese servicio declara, no a toda la cuenta de la persona.

  CONTRACARA OPERATIVA (documentarla en el procedimiento de baja): como el token
  sobrevive al cambio de contrasena, dar de baja a un docente exige BORRAR SU TOKEN
  en Moodle. Cambiarle la clave NO corta el acceso.

SIN COLUMNA DE CONTRASENA — A PROPOSITO:
  No existe y no debe existir. Que el esquema no tenga donde guardarla es la garantia
  mas barata de que nadie la guarde por accidente en el futuro.
"""

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moodle_credencial_docente",
        sa.Column(
            "usuario_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # Usuario del campus. Se guarda para mostrarlo ("Conectado como ...") y para
        # re-canjear si el token cae; NO es secreto.
        sa.Column("moodle_username", sa.String(255), nullable=False),
        # Token de Web Services cifrado con Fernet (SecretCipher). NUNCA en claro.
        sa.Column("token_cifrado", sa.Text(), nullable=False),
        # Ultimos 4 caracteres, para que la persona reconozca cual cargo sin exponerlo.
        sa.Column("token_pista", sa.String(8), nullable=True),
        # 'activa' | 'caida'. 'caida' = Moodle respondio invalidtoken (revocado o
        # vencido). No se borra el token: se marca, para poder mostrar el aviso.
        sa.Column(
            "estado", sa.String(16), nullable=False, server_default="activa"
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Ultima vez que se uso con exito: sirve para diagnosticar "hace 3 meses que
        # no sincroniza" sin tener que leer logs.
        sa.Column("ultimo_uso_en", sa.DateTime(timezone=True), nullable=True),
    )

    # El shortname del servicio externo del campus. Sin esto no se puede pedir un
    # token acotado: `login/token.php` exige `service=`. Es config institucional, no
    # secreto, y lo carga el admin junto con la URL del campus.
    op.add_column(
        "moodle_credencial",
        sa.Column(
            "service_shortname",
            sa.String(100),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("moodle_credencial", "service_shortname")
    op.drop_table("moodle_credencial_docente")
