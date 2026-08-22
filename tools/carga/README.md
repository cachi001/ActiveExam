# Prueba de carga del backend real

Mide el backend que corre en producción (`main_activeexam`), no el del PoC C-03.

> **No confundir con `poc/k6/`.** Ese harness le pega a `/api/v1/events/ws` con un
> JWT de Keycloak: es el backend del PoC C-03, otra arquitectura, y su código está
> marcado como descartable. Este de acá apunta al sistema que está desplegado.

## Qué simula

El camino caliente de una rendición, por alumno:

1. `POST /api/v1/proctoring/sessions` (modo `test`)
2. `POST /api/v1/proctoring/sessions/{id}/events`, N por minuto
3. `PATCH /api/v1/proctoring/sessions/{id}/finalizar`

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
