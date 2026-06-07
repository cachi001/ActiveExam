# Deploy Railway — Backend Slim (c-57)

Guia de configuracion de variables de entorno para el backend slim en Railway.
El slim requiere Postgres estandar (`postgres:16-alpine`); sin TimescaleDB, sin MinIO,
sin Keycloak ni OTEL.

## Variables requeridas (obligatorias — el proceso falla si faltan)

| Variable | Descripcion | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | URL de la base Postgres. Railway la inyecta automaticamente al linkear el servicio. | `postgresql://user:pass@host:5432/db` |
| `FRONTEND_ORIGIN` | Origen de la SPA de Vercel (CORS). | `https://activeexam.vercel.app` |
| `JWT_OWN_SECRET` | Secreto HS256 para firmar los access tokens. **>= 32 bytes aleatorios.** | Ver generacion abajo |
| `EMBEDDING_ENCRYPTION_KEY` | Clave Fernet para cifrar embeddings biometricos at-rest. **Debe ser una clave Fernet valida.** | Ver generacion abajo |

## Variables opcionales (tienen defaults seguros)

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `JWT_OWN_ISSUER` | `activeexam-auth` | Claim `iss` de los access tokens. |
| `JWT_AUDIENCE` | `activeexam` | Claim `aud` de los access tokens. |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | Duracion del access token (15 minutos). |
| `REFRESH_TOKEN_TTL_SECONDS` | `604800` | Duracion del refresh token (7 dias). |
| `AUTH_PROVIDER` | `jwt` | Proveedor de auth. En el slim siempre `jwt`. |
| `PORT` | `8000` | Puerto en que escucha uvicorn. Railway lo inyecta automaticamente. |

## Como generar los secretos

**JWT_OWN_SECRET** (string aleatorio >= 32 bytes):
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Ejemplo de salida: `k3hG8mN2pQrT5vWxYzA7bCdEfGhIjKlM`

**EMBEDDING_ENCRYPTION_KEY** (clave Fernet valida — 32 bytes en base64-urlsafe):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Ejemplo de salida: `dGVzdC1mZXJuZXQta2V5LWZvci10ZXN0cy1vbmx5LTMyYnl0ZXM=`

## Migracion de la DB

El `Dockerfile.slim` corre automaticamente antes de levantar uvicorn:
```bash
alembic upgrade slim@head
```
Esto aplica las migraciones `0005` (proctoring) y `0008` (auth + biometria)
en Postgres estandar, sin TimescaleDB.

**IMPORTANTE**: `slim@head` NO aplica las migraciones de la rama principal
(`0001`..`0007`). Eso es intencional — la rama principal requiere TimescaleDB
que no existe en Railway.

## Endpoints disponibles en el slim

| Prefijo | Descripcion |
|---------|-------------|
| `GET /api/v1/proctoring/docs` | Documentacion Swagger |
| `POST /api/v1/auth/login` | Login con usuario+password |
| `POST /api/v1/auth/refresh` | Renovar refresh token |
| `GET /api/v1/auth/me` | Perfil del usuario autenticado |
| `POST /api/v1/users/` | Crear usuario (solo admin_sistema) |
| `POST /api/v1/enrollment/foto-perfil` | Subir foto de referencia (BYTEA en DB) |
| `POST /api/v1/enrollment/embedding-referencia` | Guardar embedding cifrado |
| `POST /api/v1/proctoring/sesiones` | Crear sesion de proctoring |

## Seed de usuarios de prueba (local/staging solamente)

Correr con el flag `--slim` para no requerir las variables del stack completo:
```bash
DATABASE_URL=postgresql+asyncpg://... \
SEED_ESTUDIANTE_PASSWORD=... \
SEED_PROCTOR_PASSWORD=... \
SEED_ADMIN_PASSWORD=... \
python backend/scripts/seed_users.py --slim
```

Usuarios creados:
- `seed-estudiante` (rol: estudiante)
- `seed-proctor` (rol: proctor)
- `seed-admin` (rol: admin_sistema)

## Notas de seguridad

- `JWT_OWN_SECRET` y `EMBEDDING_ENCRYPTION_KEY` son secretos: **nunca en codigo, nunca en commits**.
- Rotacion de `JWT_OWN_SECRET`: todos los access tokens activos quedan invalidos al rotar.
  Los refresh tokens persisten en DB; tras rotar el secreto, los usuarios deben re-loginear.
- Rotacion de `EMBEDDING_ENCRYPTION_KEY`: requiere re-cifrar todos los embeddings de la tabla
  `embedding_referencia` antes de cambiar la clave. Delegar a un change futuro de gestion de claves.

## Diagnostico rapido

```bash
# Verificar que las migraciones slim estan aplicadas
alembic history | grep slim

# Verificar tablas creadas en Railway
psql $DATABASE_URL -c "\dt"
# Debe mostrar: proctoring_session, proctoring_event, proctoring_biometria,
#               usuario, refresh_tokens, foto_referencia, embedding_referencia

# Health check del servicio
curl https://<tu-servicio>.railway.app/api/v1/proctoring/docs
```
