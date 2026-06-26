"""Tests unitarios del helper puro de contextualizacion de score (C-15 6.4.1).

Sin DB, sin red. Verifica que ``eventos_en_pausa_autorizada`` selecciona los ids
de eventos cuyo ts_backend cae dentro de una ventana de pausa APROBADA, y que
``calcular_score`` sobre los eventos restantes los excluye (L2.5: contextualiza,
no borra).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.application.proctoring.scoring import (
    calcular_score,
    eventos_en_pausa_autorizada,
)

_T0 = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)


@dataclass
class _Ev:
    id: str
    ts_backend: datetime
    severidad: str = "alta"
    tipo: str = ""


@dataclass
class _Pausa:
    estado: str
    inicio_en: datetime | None
    fin_en: datetime | None


def _t(min_offset: int) -> datetime:
    return _T0 + timedelta(minutes=min_offset)


def test_sin_pausas_no_excluye_nada() -> None:
    """Sin ventanas de pausa, ningun evento queda excluido."""
    eventos = [_Ev("e1", _t(5)), _Ev("e2", _t(10))]
    assert eventos_en_pausa_autorizada(eventos, []) == set()


def test_evento_dentro_de_pausa_aprobada_finalizada() -> None:
    """Evento dentro de [inicio, fin] de una pausa finalizada queda excluido."""
    eventos = [_Ev("dentro", _t(5)), _Ev("fuera", _t(20))]
    ventanas = [_Pausa("finalizada", inicio_en=_t(0), fin_en=_t(10))]
    assert eventos_en_pausa_autorizada(eventos, ventanas) == {"dentro"}


def test_pausa_aprobada_activa_usa_ahora_como_cierre() -> None:
    """Pausa 'aprobada' sin fin_en: la ventana se cierra en 'ahora'."""
    eventos = [_Ev("dentro", _t(5)), _Ev("futuro", _t(100))]
    ventanas = [_Pausa("aprobada", inicio_en=_t(0), fin_en=None)]
    ahora = _t(10)  # cierre explicito para reproducibilidad
    assert eventos_en_pausa_autorizada(eventos, ventanas, ahora=ahora) == {"dentro"}


def test_pausa_rechazada_o_solicitada_no_abre_ventana() -> None:
    """'rechazada' y 'solicitada' no abren ventana: no excluyen nada."""
    eventos = [_Ev("e1", _t(5))]
    ventanas = [
        _Pausa("rechazada", inicio_en=None, fin_en=None),
        _Pausa("solicitada", inicio_en=None, fin_en=None),
    ]
    assert eventos_en_pausa_autorizada(eventos, ventanas) == set()


def test_bordes_de_ventana_inclusive() -> None:
    """Eventos exactamente en inicio_en y fin_en estan DENTRO (bordes inclusive)."""
    eventos = [
        _Ev("borde_inicio", _t(0)),
        _Ev("borde_fin", _t(10)),
        _Ev("justo_antes", _t(-1)),
        _Ev("justo_despues", _t(11)),
    ]
    ventanas = [_Pausa("aprobada", inicio_en=_t(0), fin_en=_t(10))]
    assert eventos_en_pausa_autorizada(eventos, ventanas) == {
        "borde_inicio",
        "borde_fin",
    }


def test_score_excluye_eventos_en_pausa() -> None:
    """calcular_score sobre los eventos restantes baja al excluir los de la pausa."""
    eventos = [
        _Ev("e1", _t(5), severidad="alta"),  # 45, dentro de pausa
        _Ev("e2", _t(20), severidad="media"),  # 20, fuera
    ]
    ventanas = [_Pausa("finalizada", inicio_en=_t(0), fin_en=_t(10))]
    ids = eventos_en_pausa_autorizada(eventos, ventanas)
    restantes = [e for e in eventos if e.id not in ids]
    assert calcular_score(eventos) == 65  # sin contextualizar
    assert calcular_score(restantes) == 20  # contextualizado (excluye e1)
