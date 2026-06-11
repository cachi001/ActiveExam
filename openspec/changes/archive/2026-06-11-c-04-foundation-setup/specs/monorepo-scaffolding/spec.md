# Spec — monorepo-scaffolding

> Capacidad de **estructura del repositorio por capas**. Fija el árbol Clean/Hexagonal (backend), por features (frontend) e infra, cerrando la suposición SU-07. Su Done es estructural: el dominio queda aislado y la infraestructura sustituible.

## ADDED Requirements

### Requirement: Árbol del backend por capas con dominio puro aislado
El monorepo SHALL exponer `backend/app/` particionado en las capas `domain`, `application`, `infrastructure` (con submódulos `persistence`, `messaging`, `storage`, `auth`), `presentation`, `workers` y `observability`, donde la capa `domain` NO importa framework ni adaptadores de infraestructura.

#### Scenario: Dominio sin dependencias de framework
- **WHEN** se inspecciona cualquier módulo bajo `backend/app/domain/`
- **THEN** no contiene imports de FastAPI, SQLAlchemy, ni de los adaptadores de `infrastructure/`, garantizando un dominio puro y testeable

#### Scenario: Infraestructura sustituible por submódulo
- **WHEN** se revisa `backend/app/infrastructure/`
- **THEN** existen los submódulos `persistence`, `messaging`, `storage` y `auth` como adaptadores detrás de puertos, de modo que la pieza de mensajería (ganador de C-03) se puede sustituir sin tocar dominio

### Requirement: Árbol del frontend por features y del repo con infra
El monorepo SHALL exponer `frontend/src/` con las carpetas `features`, `shared`, `vision`, `proctoring`, `transport` y `pages`, y una carpeta `infra/` con `docker-compose/`, `nginx/` y `observability/`, conforme a `08` §Estructura de directorios.

#### Scenario: Estructura del frontend y de infra presente
- **WHEN** se clona el repo y se lista el árbol
- **THEN** existen `frontend/src/{features,shared,vision,proctoring,transport,pages}` e `infra/{docker-compose,nginx,observability}` como convención canónica (cierra SU-07)
