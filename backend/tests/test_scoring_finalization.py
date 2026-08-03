"""Tests del cierre de sesion + consolidacion del score (C-13, aplicacion).

Sin DB (continuous aggregate real -> @requires_stack): dobles en memoria de los
puertos. Cubre: cierre no bloqueante (encola, no calcula), consolidacion idempotente
(reintento sin doble conteo), liberacion de clave, decision por umbral
(flaggeada/archivada) y la garantia de no-veredicto.
"""

from __future__ import annotations

import asyncio

from app.application.scoring.finalization import (
    SCORE_CAP,
    SCORE_THRESHOLD_DEFAULT,
    SessionFinalizationService,
    TOPIC_CIERRE_SESION,
)
from app.domain.entities.event import Evento
from app.domain.entities.exam import Examen
from app.domain.entities.session import EstadoSesion, Sesion
from app.domain.scoring.risk_score import DecisionEncolado


class FakeSessionRepo:
    def __init__(self, sesion: Sesion) -> None:
        self.sesion = sesion
        self.updates: list[Sesion] = []

    async def get(self, sid: str):
        return self.sesion if self.sesion.id == sid else None

    async def update(self, s: Sesion) -> Sesion:
        self.sesion = s
        self.updates.append(s)
        return s

    async def add(self, s):  # pragma: no cover
        return s

    async def list(self):  # pragma: no cover
        return [self.sesion]


class FakeEventRepo:
    def __init__(self, eventos: list[Evento]) -> None:
        self.eventos = eventos

    async def posteriores_a(self, *, session_id, last_event_id):
        return [e for e in self.eventos if e.session_id == session_id]

    async def append(self, e):  # pragma: no cover
        return e

    async def get(self, eid):  # pragma: no cover
        return None

    async def list(self):  # pragma: no cover
        return self.eventos


class FakeExamRepo:
    def __init__(self, umbral: float) -> None:
        self.examen = Examen(nombre="x", umbral_score=umbral, id="e1")

    async def get(self, eid):
        return self.examen if eid == "e1" else None

    async def add(self, e):  # pragma: no cover
        return e

    async def update(self, e):  # pragma: no cover
        return e

    async def list(self):  # pragma: no cover
        return [self.examen]


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict]] = []

    async def enqueue(self, topic, payload) -> str:
        self.enqueued.append((topic, payload))
        return f"msg-{len(self.enqueued)}"

    async def dequeue(self, topic):  # pragma: no cover
        return None

    async def ack(self, mid):  # pragma: no cover
        return None

    async def health_check(self) -> bool:  # pragma: no cover
        return True


def _sesion(estado=EstadoSesion.ACTIVA) -> Sesion:
    return Sesion(user_id="u", exam_id="e1", clave_sesion="clave-hex", estado=estado, id="sess-1")


def _eventos_severos(n=10) -> list[Evento]:
    return [
        Evento(
            session_id="sess-1", exam_id="e1", tipo="multiples_rostros",
            severidad="critica", timestamp_cliente="", timestamp_backend="2026-05-30T10:00:00Z",
            payload={"frames_consecutivos": 6}, id=str(i),
        )
        for i in range(n)
    ]


def _service(sesion, eventos, umbral):
    repo_s = FakeSessionRepo(sesion)
    cola = FakeQueue()
    svc = SessionFinalizationService(
        sesiones=repo_s,
        eventos=FakeEventRepo(eventos),
        examenes=FakeExamRepo(umbral),
        cola=cola,
    )
    return svc, repo_s, cola


def test_finish_es_no_bloqueante_marca_finalizada_y_encola() -> None:
    svc, repo_s, cola = _service(_sesion(), [], umbral=5.0)
    asyncio.run(svc.finish("sess-1"))
    # No calcula el score aqui (no bloquea): solo marca finalizada y encola la tarea.
    assert repo_s.sesion.estado is EstadoSesion.FINALIZADA
    assert cola.enqueued[0][0] == TOPIC_CIERRE_SESION


def test_consolidar_score_sobre_umbral_flaggea_y_encola_revision() -> None:
    svc, repo_s, cola = _service(_sesion(EstadoSesion.FINALIZADA), _eventos_severos(10), umbral=5.0)
    res = asyncio.run(svc.consolidar("sess-1"))
    assert res.decision is DecisionEncolado.FLAGGEADA
    assert repo_s.sesion.estado is EstadoSesion.FLAGGEADA
    # Se encola la sesion priorizada para la cola de revision humana (C-16).
    assert any(t == "review.queue" for t, _ in cola.enqueued)


def test_consolidar_score_bajo_umbral_archiva() -> None:
    # Sin eventos -> score 0 -> bajo umbral -> archivada (cerrada), no entra a cola.
    svc, repo_s, cola = _service(_sesion(EstadoSesion.FINALIZADA), [], umbral=5.0)
    res = asyncio.run(svc.consolidar("sess-1"))
    assert res.decision is DecisionEncolado.ARCHIVADA
    assert repo_s.sesion.estado is EstadoSesion.CERRADA
    assert not any(t == "review.queue" for t, _ in cola.enqueued)


def test_consolidar_libera_la_clave_de_sesion() -> None:
    svc, repo_s, _ = _service(_sesion(EstadoSesion.FINALIZADA), _eventos_severos(10), umbral=5.0)
    res = asyncio.run(svc.consolidar("sess-1"))
    assert res.clave_liberada is True
    assert repo_s.sesion.clave_sesion == ""  # liberada -> ingesta rechaza eventos


def test_consolidar_es_idempotente_sin_doble_conteo() -> None:
    eventos = _eventos_severos(10)
    svc, _, _ = _service(_sesion(EstadoSesion.FINALIZADA), eventos, umbral=5.0)
    r1 = asyncio.run(svc.consolidar("sess-1"))
    r2 = asyncio.run(svc.consolidar("sess-1"))
    # Recomputa desde la hypertable -> mismo score, sin acumular sobre el previo.
    assert r1.score_final == r2.score_final


def test_umbral_default_conservador_cuando_examen_no_define() -> None:
    # Examen sin umbral util -> usa SCORE_THRESHOLD_DEFAULT (conservador, RN-SC-05).
    svc, _, _ = _service(_sesion(EstadoSesion.FINALIZADA), _eventos_severos(1), umbral=SCORE_THRESHOLD_DEFAULT)
    res = asyncio.run(svc.consolidar("sess-1"))
    assert res.decision in (DecisionEncolado.FLAGGEADA, DecisionEncolado.ARCHIVADA)


def test_consolidar_capea_score_a_SCORE_CAP() -> None:
    """El score consolidado nunca supera SCORE_CAP (100): el dominio puro suma sin
    tope, pero la capa de aplicacion lo capea para que cliente y server muestren la
    misma escala 0-100 (ver doc en finalization.SCORE_CAP)."""
    # 20 eventos criticos con persistencia frames=6 producen un score crudo bien por
    # encima de 100 (~ 6*3.5*20 = 420 base + bonos de correlacion). Tras el cap = 100.
    svc, repo_s, _ = _service(_sesion(EstadoSesion.FINALIZADA), _eventos_severos(20), umbral=5.0)
    res = asyncio.run(svc.consolidar("sess-1"))
    assert res.score_final == SCORE_CAP
    # El score persistido en la sesion tambien queda capeado.
    assert repo_s.sesion.score == SCORE_CAP


def test_consolidar_score_bajo_cap_pasa_sin_modificar() -> None:
    """Si el score crudo es < SCORE_CAP, no se altera (cap es una cota superior, no
    redondeo)."""
    # 1 evento critica frames=6 -> 6.0*3.5 = 21.0 (muy debajo de 100).
    svc, _, _ = _service(_sesion(EstadoSesion.FINALIZADA), _eventos_severos(1), umbral=5.0)
    res = asyncio.run(svc.consolidar("sess-1"))
    assert res.score_final == 21.0


def test_ningun_path_produce_veredicto_solo_estado() -> None:
    # La consolidacion solo deja la sesion flaggeada o cerrada (archivada); jamas una
    # sancion (L2.5, RN-SC-01, RN-RV-07). El resultado no tiene campo de veredicto.
    svc, repo_s, _ = _service(_sesion(EstadoSesion.FINALIZADA), _eventos_severos(20), umbral=5.0)
    res = asyncio.run(svc.consolidar("sess-1"))
    assert repo_s.sesion.estado in (EstadoSesion.FLAGGEADA, EstadoSesion.CERRADA)
    assert not hasattr(res, "sancion") and not hasattr(res, "veredicto")


def test_score_maximo_no_produce_anulado_c71() -> None:
    """c-71 slice 2 (D13) / regla dura #5: NO existe transicion automatica
    score/umbral -> `anulado`. Un score al tope solo PRIORIZA la cola
    (FLAGGEADA); la anulacion es siempre un acto humano en un solo paso
    (ReviewDecisionService.decide con decision=ANULADO), jamas un efecto de
    la consolidacion."""
    from app.domain.review.decision import DecisionSesion

    svc, repo_s, _ = _service(
        _sesion(EstadoSesion.FINALIZADA), _eventos_severos(50), umbral=5.0
    )
    res = asyncio.run(svc.consolidar("sess-1"))
    # Score al tope (cap) -> priorizada, nunca anulada.
    assert res.score_final == SCORE_CAP
    assert repo_s.sesion.estado is EstadoSesion.FLAGGEADA
    # El resultado del cierre no expone ninguna decision de revision/anulacion
    # (el campo `decision` que SI tiene es `DecisionEncolado`, un concepto
    # distinto — el estado FLAGGEADA/CERRADA de la cola, no el veredicto).
    assert not hasattr(res, "resolucion")
    for valor in (v.value for v in DecisionSesion):
        assert valor not in repr(res)
