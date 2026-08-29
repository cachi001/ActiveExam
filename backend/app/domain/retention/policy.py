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


#: Piso de retencion de CAPTURAS de proctoring (fotos del rostro del alumno que
#: toma la camara; la pantalla NO se captura): decision del dueño. Es el dato mas
#: pesado (~360 MB cada 100 alumnos, en base64 dentro de Postgres) y el mas
#: sensible (imagen biometrica) — pero bajar el piso demasiado arriesga
#: borrar evidencia antes de que un reclamo pueda resolverse. Default 180 dias
#: (un cuatrimestre), nunca configurable por debajo de este minimo.
RETENCION_CAPTURAS_DIAS_MINIMO = 90


def validar_retencion_capturas_dias(dias: int) -> None:
    """Valida el piso de ``retencion_capturas_dias`` (90 dias, decision del dueño).

    Se valida ACA (dominio) y en el endpoint que edita la config — a proposito
    NUNCA con un CHECK de base: un CHECK devuelve un error de constraint crudo
    e ilegible; esto devuelve un mensaje que explica el POR QUE del piso, para
    que quien lo intenta bajar entienda que no es un capricho arbitrario.
    """
    if dias < RETENCION_CAPTURAS_DIAS_MINIMO:
        raise ValueError(
            "retencion_capturas_dias no puede ser menor a "
            f"{RETENCION_CAPTURAS_DIAS_MINIMO} dias: las capturas son evidencia de "
            "proctoring (rostro y pantalla del alumno) y bajar el piso arriesga "
            "borrar evidencia necesaria antes de que un reclamo pueda resolverse "
            f"(recibido: {dias})."
        )
