"""003 - inmutabilidad de la cadena de custodia de Evidencia (C-12, DD-07/RN-CC-02).

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-30

Scope (C-12, evidence-custody-chain + evidence-worm-storage). El binario vive en el
bucket WORM (Object Lock modo Compliance) — inmutabilidad fisica del clip. Esta
migracion agrega DEFENSA EN PROFUNDIDAD a nivel motor sobre la fila ``evidencia``:

- Trigger ``trg_evidencia_cadena_inmutable`` (BEFORE UPDATE): una columna de la
  cadena ya FIJADA (no NULL) NO puede cambiar de valor (RN-CC-02: las firmas se
  ENCADENAN, no se reemplazan). SI se permite la transicion NULL -> valor, porque el
  worker completa ``firma_maestra`` y ``output_reinferencia`` en las etapas 3/4 de
  forma acumulativa. Tampoco se pueden borrar ``session_id``/``uri_bucket``/hashes.
- Trigger ``trg_evidencia_no_delete`` (BEFORE DELETE): la evidencia no se borra
  (la retencion/holds la maneja C-19; aqui es inmutable).

CONVENCION DESTRUCTIVA EN DOS PASOS: el ``downgrade`` solo elimina triggers y
funciones (no toca la tabla ``evidencia``, que es de la 002).
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Inmutabilidad acumulativa de la cadena: NULL -> valor permitido (worker), pero
    # valor -> otro valor RECHAZADO (RN-CC-02). hash_backend nace en la etapa 2 y no
    # cambia; firma_maestra/output_reinferencia nacen en el worker (etapas 3/4).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION evidencia_cadena_inmutable()
        RETURNS trigger AS $$
        BEGIN
            -- session_id y uri_bucket nunca cambian.
            IF NEW.session_id IS DISTINCT FROM OLD.session_id THEN
                RAISE EXCEPTION 'evidencia.session_id es inmutable (cadena de custodia)';
            END IF;
            IF NEW.uri_bucket IS DISTINCT FROM OLD.uri_bucket THEN
                RAISE EXCEPTION 'evidencia.uri_bucket es inmutable (cadena de custodia)';
            END IF;
            -- Una etapa ya fijada (no NULL) no puede reescribirse a otro valor.
            IF OLD.hash_cliente IS NOT NULL
               AND NEW.hash_cliente IS DISTINCT FROM OLD.hash_cliente THEN
                RAISE EXCEPTION 'evidencia.hash_cliente ya fijado: no se reemplaza (RN-CC-02)';
            END IF;
            IF OLD.firma_cliente IS NOT NULL
               AND NEW.firma_cliente IS DISTINCT FROM OLD.firma_cliente THEN
                RAISE EXCEPTION 'evidencia.firma_cliente ya fijado: no se reemplaza (RN-CC-02)';
            END IF;
            IF OLD.hash_backend IS NOT NULL
               AND NEW.hash_backend IS DISTINCT FROM OLD.hash_backend THEN
                RAISE EXCEPTION 'evidencia.hash_backend ya fijado: no se reemplaza (RN-CC-02)';
            END IF;
            IF OLD.firma_maestra IS NOT NULL
               AND NEW.firma_maestra IS DISTINCT FROM OLD.firma_maestra THEN
                RAISE EXCEPTION 'evidencia.firma_maestra ya fijada: no se reemplaza (RN-CC-02)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_evidencia_cadena_inmutable
        BEFORE UPDATE ON evidencia
        FOR EACH ROW EXECUTE FUNCTION evidencia_cadena_inmutable();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION evidencia_no_delete()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'evidencia es inmutable: DELETE rechazado (retencion/holds via C-19)';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_evidencia_no_delete
        BEFORE DELETE ON evidencia
        FOR EACH ROW EXECUTE FUNCTION evidencia_no_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evidencia_no_delete ON evidencia")
    op.execute("DROP TRIGGER IF EXISTS trg_evidencia_cadena_inmutable ON evidencia")
    op.execute("DROP FUNCTION IF EXISTS evidencia_no_delete()")
    op.execute("DROP FUNCTION IF EXISTS evidencia_cadena_inmutable()")
