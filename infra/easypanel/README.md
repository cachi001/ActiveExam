# Deploy de STAGING — Backend en EasyPanel (VPS) + Frontend en Vercel

Guía de despliegue del stack **slim** de ActiveExam. Adaptada al proyecto a partir
de la convención EasyPanel de referencia.

**Arquitectura del deploy:**

```
  Vercel (SPA)  ──HTTPS──►  EasyPanel/VPS: Traefik ──► backend FastAPI :8000 ──► Postgres
   frontend Vite                                        (SSE en el mismo backend, sin Redis/ws)
```

El frontend (Vite) va en Vercel; el backend + Postgres van en la VPS con EasyPanel.
NO hay Keycloak, MinIO, TimescaleDB ni Redis (eso es la arquitectura enterprise, no la slim).

---

## Parte A — Backend + Postgres en EasyPanel

### 1. Crear el servicio Compose
1. EasyPanel → `+ Project` → nombre (ej. `activeexam-staging`).
2. Dentro del proyecto → `+ Service` → tipo **Compose**, nombre `backend`.

### 2. Fuente (GitHub)
- Type: GitHub · Repo: `<tu-usuario>/<repo>` · Branch: `main` (o la de release).

### 3. Apuntar al compose
- Compose file: `infra/easypanel/docker-compose.staging.yml`

### 4. Variables de entorno (pestaña Environment)
Cargar TODAS las de [`staging.env.example`](./staging.env.example) con valores reales.
Generarlas:
```bash
openssl rand -base64 24   # POSTGRES_PASSWORD
openssl rand -base64 32   # JWT_OWN_SECRET
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # EMBEDDING_ENCRYPTION_KEY
```
- `DATABASE_URL`: misma password que `POSTGRES_PASSWORD`, host `postgres`.
- `FRONTEND_ORIGIN`: la URL de Vercel (se completa después de la Parte B).
- **NUNCA** commitear estos valores. EasyPanel los inyecta por override en runtime.

### 5. Deploy y validación
- Click **Deploy**. Buildea con `Dockerfile.slim`, migra (`alembic slim@head`),
  seedea (idempotente) y sirve uvicorn en `0.0.0.0:8000`.
- **Logs** — esperar: `Uvicorn running on http://0.0.0.0:8000`.
  ⚠️ Si dice `127.0.0.1` → falta `--host 0.0.0.0` / `exec` (ya están en el compose).

### 6. Dominio + TLS (Traefik)
- Pestaña **Domains** → agregar host apuntando al puerto **8000**.
- El proctoring usa `getUserMedia` (cámara), que **exige HTTPS** — Traefik lo da.

### 7. Smoke test
```bash
curl https://<backend>.<id>.easypanel.host/api/v1/proctoring/health
# → {"status":"ok","db":"ok"}
```

---

## Parte B — Frontend en Vercel

1. Vercel → New Project → importar el repo, **Root Directory = `frontend`**.
2. Framework: Vite (autodetectado). `vercel.json` ya trae el rewrite SPA.
3. **Environment Variable** (Build): `VITE_API_BASE = https://<backend>.<id>.easypanel.host/api/v1`
   - Sin esto, el front pega a `/api/v1` relativo (a Vercel) y falla. Debe ser la URL ABSOLUTA del backend.
4. Deploy. Copiar la URL final (`https://<algo>.vercel.app`).

---

## Parte C — Sincronizar CORS (después de tener ambas URLs)

En EasyPanel → backend → Environment → setear `FRONTEND_ORIGIN` a la URL de Vercel
y **Deploy** de nuevo. Sin esto, el browser bloquea los requests por CORS.

---

## Checklist previo a producción real (NO staging)

- [ ] Secretos reales rotables (Vault / secret manager), no en el panel a mano.
- [ ] Backups de Postgres (volumen `pgdata`) — la evidencia y las notas viven ahí.
- [ ] Vigilar el DISCO: los screenshots (cifrados) se guardan en Postgres; crecen rápido.
- [ ] Capacidad: la slim NO está dimensionada para el pico del NFR (1.000-2.100 concurrentes) — eso lo decide la PoC C-03.
- [ ] Revisar retención de evidencia (Ley 25.326): eliminación al egreso, DPIA firmado.
