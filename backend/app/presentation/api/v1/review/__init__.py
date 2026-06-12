"""Endpoints de la cola de revision humana (c-16 slim)."""

from app.presentation.api.v1.review.router import router as review_slim_router

__all__ = ["review_slim_router"]
