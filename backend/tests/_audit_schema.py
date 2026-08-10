"""DDL de ``audit_log`` para tests: tabla + cadena de hash (2 triggers).

POR QUE EXISTE ESTE ARCHIVO
---------------------------
``audit_log`` es dominio CRITICO (append-only, tamper-evident). Su definicion real
vive en la migracion slim 0012 (+ columnas modulo/entidad/entidad_id/tipo_accion
agregadas en 0044, C-73) e incluye DOS objetos que el modelo ORM NO describe:

  1. ``audit_log_encadenar()`` + trigger BEFORE INSERT: encadena ``hash_prev`` con
     el ultimo registro y MATERIALIZA ``hash_self`` (sha256). La app NO lo calcula:
     lo hace la base.
  2. La extension ``pgcrypto`` (``digest()``/``encode()`` del trigger).

Crear la tabla desde ``AuditLogModel.__table__`` produce algo *parecido* pero SIN
la cadena de hash: los INSERT fallan por ``hash_self NOT NULL``, y si no fallaran
seria peor — tests de auditoria en verde contra una tabla que no encadena nada.

La DDL estaba DUPLICADA en test_c20_audit.py y test_c73_examen_audit_wiring.py.
Se centraliza aca para que exista una sola version y el conftest pueda restaurar
la tabla cuando un modulo la deja dropeada.

NOTA: la FK a ``evidencia`` se omite a proposito (aislamiento del test); todo lo
demas —columnas, defaults y triggers— es identico a la migracion.
"""

from __future__ import annotations

CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor varchar(255) NOT NULL,
    timestamp timestamptz NOT NULL DEFAULT now(),
    ip inet,
    user_agent text,
    accion varchar(255) NOT NULL,
    modulo varchar(64),
    entidad varchar(64),
    entidad_id varchar(255),
    tipo_accion varchar(32),
    evidencia_id uuid,
    proposito text,
    hash_prev varchar(64) NOT NULL DEFAULT '',
    hash_self varchar(64)
)
"""

# Cada sentencia por separado: el cuerpo $$...$$ lleva ';' adentro y no se puede
# splitear por ';'.
DDL_TRIGGERS = [
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    """
    CREATE OR REPLACE FUNCTION audit_log_encadenar() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_prev text;
        v_genesis constant text := repeat('0', 64);
    BEGIN
        SELECT hash_self INTO v_prev FROM audit_log ORDER BY timestamp DESC, id DESC LIMIT 1;
        IF v_prev IS NULL THEN v_prev := v_genesis; END IF;
        NEW.hash_prev := v_prev;
        NEW.hash_self := encode(digest(concat_ws('|',
            NEW.actor,
            to_char(NEW.timestamp AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
            host(NEW.ip),
            coalesce(NEW.user_agent, ''),
            NEW.accion,
            coalesce(NEW.evidencia_id::text, ''),
            coalesce(NEW.proposito, ''),
            NEW.hash_prev
        ), 'sha256'), 'hex');
        RETURN NEW;
    END; $$
    """,
    "DROP TRIGGER IF EXISTS trg_audit_log_encadenar ON audit_log",
    "CREATE TRIGGER trg_audit_log_encadenar BEFORE INSERT ON audit_log "
    "FOR EACH ROW EXECUTE FUNCTION audit_log_encadenar()",
]

#: Tabla + triggers, en orden. Idempotente: se puede correr sobre una DB que ya
#: la tiene (IF NOT EXISTS / CREATE OR REPLACE / DROP TRIGGER IF EXISTS).
DDL_COMPLETA = [CREAR_TABLA, *DDL_TRIGGERS]
