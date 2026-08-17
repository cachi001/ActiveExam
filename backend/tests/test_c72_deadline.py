"""C-72 §1 — Deadline efectivo (dominio puro).

Corren SIN base de datos. Validan el cálculo del deadline efectivo y la
verificación de vencimiento con gracia. Hora del servidor, nunca del cliente
(regla dura de dominio #6).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.exam_content.deadline import deadline_efectivo, vencido


def _dt(hh: int, mm: int) -> datetime:
    return datetime(2026, 7, 16, hh, mm, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1.1-1.3 — deadline_efectivo = min(creada_en + limite, cierre)
# ---------------------------------------------------------------------------

def test_limite_individual_vence_antes_que_la_ventana():
    # arranca 10:00, 40 min → 10:40; la ventana cierra 12:00 → gana el límite
    assert deadline_efectivo(
        creada_en=_dt(10, 0), tiempo_limite_min=40, cierre=_dt(12, 0)
    ) == _dt(10, 40)


def test_ventana_cierra_antes_que_el_limite_individual():
    # arranque tardío 11:50, 40 min → 12:30; pero la ventana cierra 12:00 → gana el cierre
    assert deadline_efectivo(
        creada_en=_dt(11, 50), tiempo_limite_min=40, cierre=_dt(12, 0)
    ) == _dt(12, 0)


def test_sin_limite_individual_gana_el_cierre():
    # tiempo_limite_min None (sin límite) → el vencimiento es el cierre de la ventana
    assert deadline_efectivo(
        creada_en=_dt(10, 0), tiempo_limite_min=None, cierre=_dt(12, 0)
    ) == _dt(12, 0)


# ---------------------------------------------------------------------------
# 1.5-1.7 — vencido(deadline, ahora, gracia_seg): la gracia es tolerancia a
# latencia, parámetro explícito, nunca leída del cliente.
# ---------------------------------------------------------------------------

_DEADLINE = _dt(12, 0)


def test_no_vencido_antes_del_deadline():
    # 5 min antes del deadline → no vencido
    assert vencido(deadline=_DEADLINE, ahora=_dt(11, 55), gracia_seg=60) is False


def test_no_vencido_dentro_de_la_gracia():
    # 30s después del deadline, con 60s de gracia → todavía no vencido
    ahora = _DEADLINE + timedelta(seconds=30)
    assert vencido(deadline=_DEADLINE, ahora=ahora, gracia_seg=60) is False


def test_vencido_pasada_la_gracia():
    # 61s después del deadline, con 60s de gracia → vencido
    ahora = _DEADLINE + timedelta(seconds=61)
    assert vencido(deadline=_DEADLINE, ahora=ahora, gracia_seg=60) is True


def test_borde_justo_en_el_deadline_no_vencido():
    # exactamente en el deadline → dentro de la gracia, no vencido
    assert vencido(deadline=_DEADLINE, ahora=_DEADLINE, gracia_seg=60) is False


def test_borde_justo_al_fin_de_la_gracia_no_vencido():
    # exactamente en deadline + gracia → borde inclusivo, aún no vencido
    ahora = _DEADLINE + timedelta(seconds=60)
    assert vencido(deadline=_DEADLINE, ahora=ahora, gracia_seg=60) is False


# ---------------------------------------------------------------------------
# 1.8 — la gracia default (60s) vive en la config (env), no en el dominio
# ---------------------------------------------------------------------------

_ENV_MINIMO = dict(
    database_url="postgresql://u:p@h:5432/db",
    frontend_origin="https://example.test",
    jwt_own_secret="x" * 32,
    embedding_encryption_key="k" * 32,
)


def test_gracia_default_60():
    from app.config_activeexam import ActiveExamSettings

    assert ActiveExamSettings(**_ENV_MINIMO).deadline_gracia_seg == 60


def test_gracia_configurable():
    from app.config_activeexam import ActiveExamSettings

    assert ActiveExamSettings(**_ENV_MINIMO, deadline_gracia_seg=90).deadline_gracia_seg == 90
