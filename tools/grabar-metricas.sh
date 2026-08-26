#!/usr/bin/env bash
# Graba las métricas de producción durante un examen (c-78 §16.3b).
#
# Render free no corre un Prometheus al lado, así que la serie de `/metrics` vive
# solo en la memoria del proceso y se pierde en cada reinicio. Esto la guarda en un
# archivo, para poder mirar después qué pasó durante el examen.
#
# Arrancarlo ANTES de que entren los alumnos y cortarlo con Ctrl+C al terminar: ahí
# imprime el resumen (pico de req/s, pico de memoria, errores 5xx, reinicios).
#
#   bash tools/grabar-metricas.sh                       # producción, cada 15 s
#   bash tools/grabar-metricas.sh 30 examen-final.jsonl # cada 30 s, a ese archivo
#
# El token NO vive en el repo (el repo es público). Se lee de METRICS_TOKEN o de
# C:/Users/Emiliano/.claude/secrets/render.env — el mismo valor que está cargado en
# las variables de entorno de Render.
set -euo pipefail

ENV_FILE="${RENDER_ENV_FILE:-C:/Users/Emiliano/.claude/secrets/render.env}"
if [ -f "$ENV_FILE" ]; then
  set -a; . "$ENV_FILE"; set +a
fi
: "${METRICS_TOKEN:?falta METRICS_TOKEN (ponelo en el entorno o en $ENV_FILE)}"

BASE="${RENDER_URL:-https://actibeexam.onrender.com}"
CADA="${1:-15}"
SALIDA="${2:-metricas-$(date +%Y%m%d-%H%M).jsonl}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec python "$RAIZ/backend/app/observability/grabador_metricas.py" \
  "$BASE" "$METRICS_TOKEN" --cada "$CADA" --salida "$SALIDA"
