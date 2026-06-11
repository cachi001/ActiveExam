# Spec — twelve-factor-config

> Capacidad de **configuración twelve-factor** y ejecución mono-hilo escalada. Config por entorno, secretos vía Vault/tmpfs, FastAPI mono-hilo detrás de Nginx (DD-10/DD-11). Su Done es: la app arranca sin secretos hardcodeados y escala horizontalmente.

## ADDED Requirements

### Requirement: Configuración por entorno con secretos vía Vault/tmpfs
La aplicación SHALL cargar toda su configuración desde el entorno (`DATABASE_URL`, `STORAGE_*`, `KEYCLOAK_*`, `VAULT_*`, `OTEL_*` — `08` §Variables de entorno), inyectando los secretos vía Vault en tmpfs efímero y **sin hardcodearlos en imágenes Docker** (`08` §Gestión de secretos).

#### Scenario: Secretos no presentes en la imagen
- **WHEN** se inspecciona la imagen Docker construida
- **THEN** no contiene valores de secretos (`DATABASE_URL`, claves de storage, tokens de Vault); estos se inyectan en runtime vía Vault/tmpfs

#### Scenario: La app falla cierre si falta config requerida
- **WHEN** arranca una instancia sin una variable de entorno requerida
- **THEN** la app falla de forma explícita en el arranque (twelve-factor: config por entorno), en lugar de usar un default inseguro

### Requirement: FastAPI mono-hilo escalado horizontalmente
Cada instancia SHALL ejecutarse como un proceso uvicorn de un solo hilo asíncrono (no multi-worker dentro de la instancia) y SHALL ser escalable horizontalmente detrás de Nginx, de modo que 1 instancia ≈ 1 pod (DD-10).

#### Scenario: Una instancia = un proceso mono-hilo
- **WHEN** se arranca una instancia de la API
- **THEN** corre como un único proceso uvicorn de un hilo asíncrono, con métricas por proceso interpretables y fallas aisladas

#### Scenario: Escalado horizontal detrás de Nginx
- **WHEN** se levantan N instancias FastAPI tras Nginx
- **THEN** Nginx reparte el tráfico y saca del pool por healthcheck cualquier instancia caída, sin depender de multi-worker interno
