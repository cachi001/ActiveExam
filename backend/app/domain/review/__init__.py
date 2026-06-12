"""Dominio de la cola de revision humana (c-16 slim).

Implementa la decision terminal inmutable del revisor sobre una sesion de
proctoring flaggeada. Slim persiste 4 columnas en proctoring_session
(decision, decision_actor, decision_at, decision_observaciones).
"""

from app.domain.review.decision import (
    DecisionTerminal,
    ReviewDecisionRecord,
    ReviewDecisionResult,
)
from app.domain.review.ports import ReviewAuditor, SessionReviewRepository

__all__ = [
    "DecisionTerminal",
    "ReviewAuditor",
    "ReviewDecisionRecord",
    "ReviewDecisionResult",
    "SessionReviewRepository",
]
