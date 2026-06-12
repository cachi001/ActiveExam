"""Application layer del motor de retencion (c-19).

Orquestador puro que consume los puertos del dominio y produce un
``RetentionRunReport`` con los borrados ejecutados + holds diferidos.
"""

from app.application.retention.engine import RetentionEngine

__all__ = ["RetentionEngine"]
