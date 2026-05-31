"""Tests de las INVARIANTES EN EL MOTOR del modelo de datos (C-05).

Verifican que la migracion 002 materializa las garantias en la BASE, no solo en
la aplicacion (`04`, DD-07, D1-D4):
- el ENUM de Sesion rechaza estados fuera de la lista (capability session-lifecycle-enum);
- el trigger del audit_log rechaza UPDATE y DELETE (capability append-only-audit-log);
- el encadenamiento de hash es consistente y una ruptura es detectable;
- el Evento es una hypertable con sus indices y politica de compresion (event-hypertable).

REQUIEREN EL STACK LEVANTADO (Postgres/TimescaleDB con la 002 aplicada). Estan
marcados ``@pytest.mark.requires_stack`` y se SALTAN salvo ``RUN_STACK_TESTS=1``.
No mockean la base (regla dura de codigo): golpean Postgres real.

Comando (con el stack arriba y la 002 aplicada):
    RUN_STACK_TESTS=1 pytest backend/tests/test_db_invariants.py
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.requires_stack


def _connect():
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.fail("Falta DATABASE_URL: el stack debe exportar la conexion.")
    dsn = dsn.replace("+asyncpg", "").replace("+psycopg_async", "").replace("+psycopg", "")
    return psycopg.connect(dsn, connect_timeout=5)


def _crear_usuario_y_examen(cur) -> tuple[str, str]:
    inst = f"inst-{uuid.uuid4()}"
    cur.execute(
        "INSERT INTO usuario (id_institucional, email) VALUES (%s, %s) RETURNING id",
        (inst, f"{inst}@uni.test"),
    )
    user_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO examen (nombre, umbral_score) VALUES (%s, %s) RETURNING id",
        ("Final", 0.8),
    )
    exam_id = cur.fetchone()[0]
    return user_id, exam_id


# --- Sesion: enum (tarea 2.3) -------------------------------------------------


def test_sesion_estado_valido_aceptado() -> None:
    with _connect() as conn, conn.cursor() as cur:
        user_id, exam_id = _crear_usuario_y_examen(cur)
        for estado in ("iniciada", "activa", "finalizada", "flaggeada", "cerrada"):
            cur.execute(
                "INSERT INTO sesion (user_id, exam_id, estado, clave_sesion) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (user_id, exam_id, estado, "k"),
            )
            assert cur.fetchone()[0] is not None
        conn.rollback()


def test_sesion_estado_invalido_rechazado_por_la_base() -> None:
    psycopg = pytest.importorskip("psycopg")
    with _connect() as conn, conn.cursor() as cur:
        user_id, exam_id = _crear_usuario_y_examen(cur)
        # 'pausada' no pertenece al enum estado_sesion -> la base debe rechazar.
        with pytest.raises(psycopg.errors.Error):
            cur.execute(
                "INSERT INTO sesion (user_id, exam_id, estado, clave_sesion) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, exam_id, "pausada", "k"),
            )
        conn.rollback()


# --- Audit log: trigger append-only (tarea 3.4) -------------------------------


def _insert_audit(cur, actor: str, accion: str) -> str:
    cur.execute(
        "INSERT INTO audit_log (actor, accion) VALUES (%s, %s) RETURNING id",
        (actor, accion),
    )
    return cur.fetchone()[0]


def test_audit_log_insert_permitido() -> None:
    with _connect() as conn, conn.cursor() as cur:
        entry_id = _insert_audit(cur, "auditor", "login")
        assert entry_id is not None
        conn.rollback()


def test_audit_log_update_rechazado_por_el_trigger() -> None:
    psycopg = pytest.importorskip("psycopg")
    with _connect() as conn, conn.cursor() as cur:
        entry_id = _insert_audit(cur, "auditor", "login")
        with pytest.raises(psycopg.errors.Error):
            cur.execute(
                "UPDATE audit_log SET accion = %s WHERE id = %s",
                ("alterado", entry_id),
            )
        conn.rollback()


def test_audit_log_delete_rechazado_por_el_trigger() -> None:
    psycopg = pytest.importorskip("psycopg")
    with _connect() as conn, conn.cursor() as cur:
        entry_id = _insert_audit(cur, "auditor", "login")
        with pytest.raises(psycopg.errors.Error):
            cur.execute("DELETE FROM audit_log WHERE id = %s", (entry_id,))
        conn.rollback()


# --- Audit log: encadenamiento de hash (tarea 3.5) ----------------------------


def test_audit_log_cadena_de_hash_consistente() -> None:
    genesis = "0" * 64
    with _connect() as conn, conn.cursor() as cur:
        # Aislamiento: la cadena se valida desde el genesis sobre un audit_log
        # pristino. El audit_log PERSISTE entre tests; sin truncar, filas de otros
        # tests rompen el supuesto del genesis (hash_prev = 0*64) en la suite
        # completa. El trigger append-only es BEFORE UPDATE/DELETE a nivel fila,
        # no afecta a TRUNCATE (que es lo que permite re-aislar en el test).
        cur.execute("TRUNCATE audit_log")
        conn.commit()
        _insert_audit(cur, "a1", "login")
        _insert_audit(cur, "a2", "ver_evidencia")
        _insert_audit(cur, "a3", "exportar")
        cur.execute(
            "SELECT hash_prev, hash_self FROM audit_log "
            "ORDER BY timestamp ASC, id ASC"
        )
        filas = cur.fetchall()
        assert len(filas) >= 3
        prev = genesis
        for hash_prev, hash_self in filas:
            # El hash_prev de cada entrada coincide con el hash_self de la anterior.
            assert hash_prev == prev, "ruptura de cadena detectada"
            assert hash_self is not None and len(hash_self) == 64
            prev = hash_self
        conn.rollback()


# --- Evento: hypertable + indices + compresion (tarea 4.5) --------------------


def test_evento_es_hypertable() -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM timescaledb_information.hypertables "
            "WHERE hypertable_name = 'evento'"
        )
        assert cur.fetchone() is not None, "evento no es hypertable"


def test_evento_tiene_los_indices_del_modelo() -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'evento'"
        )
        idx = {r[0] for r in cur.fetchall()}
        assert "ix_evento_session_ts" in idx, "falta indice (session_id, timestamp)"
        assert "ix_evento_exam_ts" in idx, "falta indice (exam_id, timestamp)"


def test_evento_tiene_politica_de_compresion() -> None:
    with _connect() as conn, conn.cursor() as cur:
        # La compresion debe estar habilitada en la hypertable.
        cur.execute(
            "SELECT compression_enabled FROM timescaledb_information.hypertables "
            "WHERE hypertable_name = 'evento'"
        )
        row = cur.fetchone()
        assert row is not None and row[0] is True, "compresion no habilitada"
        # Y debe existir una compression policy (job de compresion programado).
        cur.execute(
            "SELECT 1 FROM timescaledb_information.jobs "
            "WHERE proc_name = 'policy_compression' "
            "AND hypertable_name = 'evento'"
        )
        assert cur.fetchone() is not None, "falta la compression policy (7d)"


def test_continuous_aggregates_base_existen() -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT view_name FROM timescaledb_information.continuous_aggregates"
        )
        caggs = {r[0] for r in cur.fetchall()}
        esperados = {
            "cagg_eventos_sesion_min",
            "cagg_score_sesion",
            "cagg_sesiones_activas_examen",
            "cagg_distribucion_tipo",
        }
        assert esperados <= caggs, f"faltan continuous aggregates: {esperados - caggs}"
