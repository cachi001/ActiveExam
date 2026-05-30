"""Suite de tests del backend de Proctoring.

- ``test_config.py``: carga twelve-factor de config (sin servicios externos).
- ``test_app_factory.py``: smoke de arranque de la app y router base.
- ``test_smoke_startup.py``: healthchecks responden (sin servicios externos).
- ``test_connectivity.py``: conectividad DB/storage/IdP. REQUIERE el stack
  levantado (marcados ``@pytest.mark.requires_stack``); se saltan si no esta.
"""
