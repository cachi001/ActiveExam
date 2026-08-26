# ActiveExam

Plataforma self-hosted de proctoring **L2.5** para exámenes universitarios remotos:
análisis en el navegador + verificación biométrica + evidencia con cadena de custodia.

**El sistema nunca sanciona.** Detecta, produce evidencia y prioriza una cola; la
decisión disciplinaria es siempre humana.

> **Dominio, reglas duras y roadmap**: [CLAUDE.md](CLAUDE.md) · `knowledge-base/` ·
> [CHANGES.md](CHANGES.md).

## Levantar el proyecto

Espeja el deploy real (backend + Postgres en contenedor, frontend con Vite), con login
JWT real y los usuarios de prueba creados siempre.

**Requisitos**: Docker Desktop corriendo + Node 18 o superior.

```bash
# 1. Backend + base (build, migra, seed y uvicorn en http://localhost:8000)
./scripts/dev-up.ps1          # Windows
./scripts/dev-up.sh           # macOS / Linux

# 2. Frontend, en otra terminal  ->  http://localhost:5173
cd frontend && npm install && npm run dev
```

Para frenar: `./scripts/dev-down.ps1` (con `-v` además resetea la base).

El frontend lee `frontend/.env.development` (commiteado): apunta a
`http://localhost:8000/api/v1` con `VITE_AUTH_PROVIDER=jwt`.

### Usuarios de prueba

El seed es idempotente: se puede correr las veces que haga falta.

| Rol | Usuario | Contraseña |
|---|---|---|
| `admin_sistema` | `admin` | `Admin123` |
| `coordinador` | `coordinador1` | `Coordinador123` |
| `profesor` | `profesor1` | `Profesor123` |
| `tutor` | `tutor1` | `Tutor123` |
| `estudiante` | `estudiante1` … `estudiante4` | `Estudiante123` |

`profesor1` queda asignado a la materia PROG1, `tutor1` a su comisión C1 y `estudiante1`
matriculado ahí — es el camino mínimo para probar una rendición completa. Los otros tres
estudiantes quedan libres a propósito, para ejercitar el flujo de inscripción.

> Las contraseñas y secretos de `docker-compose.dev.yml` son **solo para desarrollo**
> (base local, JWT y clave Fernet de juguete). En producción se inyectan por el
> dashboard del proveedor y nunca viven en el repo.

## Los seis roles

Definidos en `backend/app/domain/auth/roles.py`. El acceso se decide por **capacidad**,
no por lista de roles (`domain/auth/capabilities.py`).

| Rol | Qué puede |
|---|---|
| `estudiante` | Rendir sus exámenes y ver sus notas. |
| `tutor` | Supervisar **sus** comisiones y cerrar notas. No toca materias ni comisiones. |
| `profesor` | Crear exámenes y gestionar el banco de **sus** materias. **No emite veredicto de integridad.** |
| `coordinador` | Lo del profesor en **sus** materias, más el veredicto de integridad. |
| `admin_sistema` | Único rol de alcance institucional: configuración, usuarios y auditoría. |

La línea que separa a `profesor` de `coordinador` es deliberada: **quien pone la nota no
decide si hubo fraude.** Y desde c-79 el coordinador quedó acotado a sus materias — dejó
de tener alcance global.

## Estructura del repositorio

```
backend/
  app/
    domain/          # entidades, reglas y scoring — PURO, sin framework
    application/     # casos de uso
    infrastructure/  # adaptadores detrás de puertos (Postgres, storage, cripto)
    presentation/    # routers FastAPI /api/v1
    observability/   # logging JSON + métricas Prometheus
  migrations/        # Alembic (las destructivas, en dos pasos)
  tests/             # contra Postgres real, sin mocks de base
frontend/
  src/               # screens | ui | lib | proctoring | vision | transport
infra/
  docker-compose/    # stack local
  observability/     # Prometheus + Grafana
knowledge-base/      # fuente de verdad del dominio
openspec/            # specs y changes
```

### Convenciones

- **Dominio puro**: `backend/app/domain/` no importa FastAPI ni SQLAlchemy. Lo verifica
  `tests/test_architecture.py`.
- **Config por entorno** (`config.py`, twelve-factor). La app falla explícito al arrancar
  si falta configuración; nunca arranca con un default inseguro.
- **Tests sin mocks de base**: Postgres real o contenedor descartable. Mockear la base
  invalida el test.
- **Migraciones destructivas en dos pasos** (expand/contract).

## Autenticación

JWT propio (HS256), emitido y validado por el backend. **No hay Keycloak ni ningún
proveedor externo**: se eliminó en c-55, con `auth_provider` fijo en `jwt`.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123"}'
```

El access token vive 15 minutos y se renueva con el refresh token; el frontend lo hace
solo (`fetchAutenticado`).

**MFA**: todavía no está implementado. El proveedor emite `mfa_satisfecho=false` para
todos los roles y el frontend muestra un aviso visible. No bloquea a nadie en el MVP.

## Tests

```bash
# Frontend (host)
cd frontend && npm test

# Backend: contra una base descartable, NUNCA contra la de desarrollo
# (los módulos de test dropean tablas con CASCADE)
docker exec activeexam-dev-postgres-1 psql -U proctoring -d postgres \
  -c "CREATE DATABASE tests OWNER proctoring;"
docker exec \
  -e DATABASE_URL="postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/tests" \
  -e ENVIRONMENT=local \
  activeexam-dev-backend-1 python -m pytest tests/ -q
```

Los tests marcados `requires_stack` se saltean salvo que exportes `RUN_STACK_TESTS=1`.

## Observabilidad

`/metrics` expone latencia, throughput, memoria y CPU en formato Prometheus.

**Está cerrado por defecto**: sin la variable `METRICS_TOKEN` el endpoint responde 404, y
con ella exige `Authorization: Bearer <token>` — el esquema que Prometheus habla nativo.
Es a propósito: el cuerpo publica el catálogo completo de rutas de la API y los volúmenes
de tráfico, así que olvidarse la variable no puede dejarlo abierto.

En desarrollo, `docker-compose.dev.yml` levanta Prometheus (`:9090`) y Grafana (`:3001`)
ya configurados.
