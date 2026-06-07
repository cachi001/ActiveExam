## MODIFIED Requirements

### Requirement: enrollment router toma session_factory del app state

El router `presentation/api/v1/enrollment/router.py` SHALL obtener la `async_sessionmaker` de `request.app.state.session_factory` en lugar de importar `from app.infrastructure.persistence.session import get_session`. La función helper interna (`_get_session_factory`) SHALL leer `request.app.state.session_factory` y lanzar HTTP 500 si no está inicializada. Este cambio es retrocompatible: el full (`main.py`) ya cablea `app.state.session_factory` en `create_app()`.

#### Scenario: enrollment router funciona en slim con session_factory del state
- **WHEN** el enrollment router procesa `POST /enrollment/foto-perfil` con `app.state.session_factory` inicializada por main_slim
- **THEN** el endpoint funciona correctamente sin importar módulos del full (`app.config.Settings`)

#### Scenario: enrollment router funciona en full sin cambio de comportamiento
- **WHEN** el enrollment router procesa `POST /enrollment/foto-perfil` con `app.state.session_factory` inicializada por create_app del full
- **THEN** el comportamiento es idéntico al anterior (retrocompatible)

#### Scenario: session_factory no inicializada retorna 500
- **WHEN** el router recibe una request y `app.state.session_factory` es None
- **THEN** la respuesta es 500 con mensaje `"Subsistema de persistencia no inicializado."`
