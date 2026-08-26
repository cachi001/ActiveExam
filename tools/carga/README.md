# Prueba de carga del backend real

Mide el backend que corre en producción (`main_activeexam`), no el del PoC C-03.

> **No confundir con `poc/k6/`.** Ese harness le pega a `/api/v1/events/ws` con un
> JWT de Keycloak: es el backend del PoC C-03, otra arquitectura, y su código está
> marcado como descartable. Este de acá apunta al sistema que está desplegado.

## Qué simula

El camino caliente de una rendición, por alumno:

1. `POST /api/v1/proctoring/sessions` (modo `test`)
2. Durante la rendición, **tres cosas en paralelo**, cada una a la cadencia del
   cliente real:
   - `POST .../events` — N por minuto
   - `GET .../chat` — cada **3,5 s** (espeja `POLL_MS` de `ui/ChatBox.tsx`)
   - `GET .../pausas` — cada **20 s** (espeja `POLL_PAUSA_INACTIVO_MS`; el alumno
     virtual no pide pausas, así que se queda en reposo, que es el 99% del examen)
3. `PATCH .../finalizar`

> **Los pollers no son un adorno.** Medido el 25/8/2026, el tráfico dominante NO
> son los eventos: con 100 alumnos el chat son ~29 req/s y las pausas otros
> tantos, sobre un techo de 80 req/s. Hasta esta versión el harness solo posteaba
> eventos, así que daba un número cómodo que no describía la realidad. Si querés
> medir solo la ingesta, apagalos con `-e CHAT=false -e PAUSAS=false`.

## Cómo se corre

Necesita [k6](https://k6.io/docs/get-started/installation/).

```bash
# Contra el stack local (docker compose -f infra/docker-compose/docker-compose.dev.yml up)
k6 run -e BASE=http://localhost:8000 \
       -e USUARIO=estudiante1 -e PASSWORD=Estudiante123 \
       -e VUS=200 -e DURACION=5m \
       tools/carga/carga-activeexam.js
```

| Variable | Default | Qué es |
|---|---|---|
| `BASE` | `http://localhost:8000` | URL del backend |
| `USUARIO` / `PASSWORD` | `estudiante1` | Cuenta con la que se loguea |
| `VUS` | `50` | Alumnos concurrentes |
| `DURACION` | `2m` | Duración de la corrida |
| `EVENTOS_POR_MINUTO` | `20` | Eventos por alumno por minuto |
| `CHAT` | `true` | Pollear el chat. `false` lo apaga |
| `PAUSAS` | `true` | Pollear las pausas. `false` lo apaga |
| `CHAT_POLL_MS` | `3500` | Cadencia del poller de chat |
| `PAUSA_POLL_MS` | `20000` | Cadencia del poller de pausas en reposo |
| `CAPTURAS` | `0` | Fracción de eventos con captura (0 a 1). **Ver el aviso** |
| `CAPTURA_BYTES` | `114000` | Tamaño de la captura sintética en base64 |
| `CAIDA_SEG` | `0` | Segundos que dura la caída de conexión. `0` la apaga |
| `CAIDA_PCT` | `1` | Fracción de alumnos que se cae (1 = todos) |
| `CAIDA_EN_SEG` | `20` | A qué altura de la rendición se cae |
| `STAFF_USUARIO` / `STAFF_PASSWORD` | `admin` / `Admin123` | Solo para verificar la caída |

## Caída de conexión

Se prende con `CAIDA_SEG`. Lo que se mide **no** es que el sistema aguante menos
tráfico: mientras el alumno está caído no manda nada. Lo que se mide es el
**regreso**. El cliente bufferea en IndexedDB y al volver la conexión drena todo
junto, y si se cae el wifi del aula no vuelve un alumno: vuelven todos a la vez.

```bash
k6 run -e BASE=http://localhost:8000 -e VUS=70 -e DURACION=2m \
       -e CAIDA_SEG=30 -e CAIDA_PCT=1 -e CAIDA_EN_SEG=15 \
       tools/carga/carga-activeexam.js
```

Dos preguntas, y la primera es la que importa:

1. **¿Se pierde evidencia?** Se cuenta lo que el alumno generó y se compara
   contra lo que el servidor devuelve en `GET /sessions/{id}`. Métrica
   `ae_evidencia_perdida`, con umbral **cero**: un examen sin su evidencia no
   sirve para nada.
2. **¿Cuánto tarda el drenaje?** Métrica `ae_replay_ms`, y `ae_replay_eventos`
   cuántos eventos trajo la ráfaga.

> ⚠️ **La verificación necesita un token de ADMIN**, no de coordinador. El detalle
> de la sesión es un endpoint de supervisión, y desde c-79 el coordinador está
> acotado a SUS materias: como estas sesiones son `modo: 'test'` (sin examen
> vinculado), la pertenencia no resuelve y devuelve 403 igual que el alumno. Sin
> ese token la corrida avisa por consola y marca la evidencia como no verificada
> — que no es lo mismo que perdida, pero tampoco se puede dar por buena.

## Avalancha LTI

`carga-activeexam.js` arranca con un `POST /auth/login` ya resuelto, así que no
toca el camino por el que entran los alumnos el día del examen: el link de
Moodle. Eso lo cubre `avalancha-lti.py`, que simula N alumnos haciendo click casi
a la vez sobre `/lti/login` → `/lti/launch`.

Registra una **plataforma falsa** en `lti_deployment_confiable` apuntando al JWKS
que sirve el propio script (el `jwks_uri` se guarda por deployment, así que no se
toca ninguna plataforma real) y la borra al terminar.

```bash
docker cp tools/carga/avalancha-lti.py activeexam-dev-backend-1:/app/
docker exec -e DATABASE_URL="postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring" \
  activeexam-dev-backend-1 python /app/avalancha-lti.py --alumnos 70
```

Lo que de verdad mide es el **canario**: un hilo aparte que pega a un endpoint
barato cada 200 ms durante toda la avalancha. Si el bucle de eventos se bloquea,
el canario lo ve aunque los launches terminen bien. Esa es la diferencia entre
"entrar es lento" (afecta a quien entra) y "el servidor se congeló" (afecta a
todos los que ya estaban rindiendo) — que es exactamente lo que pasaba con bcrypt
antes de arreglarlo.

### ⚠️ Sobre `CAPTURAS`

Viene en `0` a propósito. Una captura real pesa **~114 KB en base64** y la base
del plan free es **1 GB**: prenderlo contra producción la puede llenar. Medido, un
examen de 100 alumnos escribe ~325 MB de capturas.

Si lo prendés contra producción, **borrá las sesiones después**. Quedan en
`modo: 'test'` justamente para eso: `DELETE /api/v1/proctoring/sessions/{id}` es
admin-only y solo acepta sesiones de test.

## Umbrales

La corrida falla si no se cumplen:

- ingesta de evento **p95 < 500 ms** y **p99 < 1000 ms**
- menos de **1 %** de errores

## Dos cosas para no equivocarse

**El token vive 15 minutos.** El script hace un solo login en `setup()` a
propósito: si cada VU se logueara, estaríamos midiendo bcrypt (que es caro por
diseño) en lugar de la ingesta. Pero eso significa que una corrida de más de 15
minutos se va a llenar de 401. Para corridas largas hay que agregar refresh.

**No correrlo contra producción sin avisar.** Escribe sesiones y eventos reales.
Quedan en `modo: 'test'` justamente para poder borrarlas después
(`DELETE /sessions/{id}` es admin-only y solo acepta sesiones de test).

## Mirar los resultados en Grafana

El stack de desarrollo levanta Prometheus y Grafana con un panel ya cargado:

```bash
docker compose -f infra/docker-compose/docker-compose.dev.yml up -d
# Grafana: http://localhost:3001  (anónimo, sin login)
```

El dashboard "ActiveExam — Carga" muestra requests por segundo, latencia p95 y
p99 por endpoint, tasa de errores, y CPU y memoria del proceso. Los datos salen
de `/metrics` del backend, que existe desde el commit `0bb7c37`.

Los paneles están versionados en `infra/observability/grafana/dashboards/`. La
vez pasada se armaron a mano en la interfaz y se perdieron al recrear el
contenedor, porque Grafana no tenía volumen ni provisioning de dashboards. Ahora
tiene las dos cosas: si tocás un panel y lo querés conservar, exportalo a JSON y
guardalo en esa carpeta.
