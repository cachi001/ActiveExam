"""Value object inmutable que describe la politica de retencion.

Slim (Postgres puro): la politica controla cuanto se conservan las sesiones
de proctoring y el audit log. No incluye archivado a Parquet ni compresion
hypertable — esos campos viven en c-67 (sucesor planificado para cuando se
migre a VPS con TimescaleDB).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionPolicy:
    """Politica de retencion de datos.

    Attributes:
        session_max_age_days: dias maximos que una sesion sin hold puede vivir
            en la DB antes de ser eliminada (cascade a sus eventos).
        audit_log_retention_years: anios que el audit log se conserva. Default 5
            por minimo legal (Ley 25.326 + estandar interno).
    """

    session_max_age_days: int
    audit_log_retention_years: int

    def __post_init__(self) -> None:
        if self.session_max_age_days <= 0:
            raise ValueError(
                "session_max_age_days debe ser > 0 "
                f"(recibido: {self.session_max_age_days})"
            )
        if self.audit_log_retention_years <= 0:
            raise ValueError(
                "audit_log_retention_years debe ser > 0 "
                f"(recibido: {self.audit_log_retention_years})"
            )

    @classmethod
    def default(cls) -> RetentionPolicy:
        """Politica por defecto: 180 dias sesiones, 5 anios audit log."""
        return cls(session_max_age_days=180, audit_log_retention_years=5)
