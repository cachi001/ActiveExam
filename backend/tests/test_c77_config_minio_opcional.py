"""Tests de configuracion MinIO opcional (c-77, tarea 17).

``ActiveExamSettings`` no debe EXIGIR ninguna variable MINIO_* (Render arranca
hoy sin VPS). ``minio_configurado`` es la funcion pura que decide si el bucket
WORM esta disponible: exige las 4 variables juntas o ninguna, para no arrancar
"a medias" con solo alguna configurada.
"""

from __future__ import annotations

from app.config_activeexam import ActiveExamSettings, minio_configurado

_BASE_ENV_VARS = {
    "database_url": "postgresql+asyncpg://u:p@localhost:5432/db",
    "frontend_origin": "http://localhost:5173",
    "jwt_own_secret": "x" * 32,
    "embedding_encryption_key": "VXqRzW9ksjWE2eCa752juwQdOtAPCrYVnratlmHj7b0=",
}


def _settings(**overrides) -> ActiveExamSettings:
    return ActiveExamSettings(**{**_BASE_ENV_VARS, **overrides})


def test_settings_sin_ninguna_var_minio_no_falla_y_minio_configurado_es_false() -> None:
    settings = _settings()

    assert settings.minio_endpoint is None
    assert settings.minio_access_key is None
    assert settings.minio_secret_key is None
    assert settings.minio_bucket_evidencia is None
    assert minio_configurado(settings) is False


def test_settings_con_las_4_vars_minio_completas_minio_configurado_es_true() -> None:
    settings = _settings(
        minio_endpoint="minio:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin123",
        minio_bucket_evidencia="activeexam-evidencia",
    )

    assert minio_configurado(settings) is True


def test_minio_configurado_false_si_falta_solo_una_de_las_4() -> None:
    """Triangulacion: config A MEDIAS (solo endpoint+bucket) no debe habilitar MinIO."""
    settings = _settings(
        minio_endpoint="minio:9000",
        minio_bucket_evidencia="activeexam-evidencia",
        # falta minio_access_key y minio_secret_key
    )

    assert minio_configurado(settings) is False


def test_minio_configurado_false_si_falta_solo_el_bucket() -> None:
    """Segundo caso de 'a medias': todas menos el bucket."""
    settings = _settings(
        minio_endpoint="minio:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin123",
    )

    assert minio_configurado(settings) is False
