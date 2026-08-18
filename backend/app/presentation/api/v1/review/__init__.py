"""Endpoints de la cola de revision humana (c-16 activeexam)."""

from app.presentation.api.v1.review.router import router as review_activeexam_router

__all__ = ["review_activeexam_router"]
