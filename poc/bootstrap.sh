#!/usr/bin/env bash
# =============================================================================
# Bootstrap del harness de carga C-03 (DESCARTABLE) para un entorno FRESCO
# (GitHub Codespaces 8-core / cualquier VM Linux con Docker).
#
# POR QUE EXISTE: el desktop de desarrollo tiene 2 cores fisicos (AMD A6) -> no
# puede medir A4 al pico ~2.100 VU sin confundir el backplane con la saturacion
# de CPU (ver poc/README.md, hallazgo B5.1). El veredicto de escala se saca en un
# host con 8+ cores reales. Este script deja ese host listo de forma DETERMINISTA.
#
# QUE HACE (secuencia validada en vivo contra DB fresca):
#   1. Crea .env desde .env.example si no existe (en Codespaces .env esta gitignored).
#   2. Levanta el stack multi-instancia (build incluye psycopg2-binary -> alembic anda).
#   3. Espera a que una instancia FastAPI quede healthy via nginx-poc:8080.
#   4. Aplica migraciones por revision NOMBRADA: 0004 (cadena prod: tablas + hypertable
#      + CAGG) y 0006 (cola PoC). Nombrar la revision SORTEA el multi-head de alembic
#      (0005 'slim' y 0006 tienen down_revision=None). 0005 se saltea A PROPOSITO:
#      no esta aplicado en la DB de prod que funciona. El multi-head es deuda de las
#      migraciones de prod, a resolver en su propio change -- NO se toca aca.
#   5. Siembra N sesiones -> poc/k6/sessions.json + poc/k6/.exam_id.
#
# USO:
#   bash poc/bootstrap.sh            # 100 sesiones (default)
#   SESSIONS=200 bash poc/bootstrap.sh
#
# Despues de esto, correr el barrido (Bloque 5) -- ver poc/README.md seccion
# "Apuntar el harness a Nginx". El stack queda corriendo.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."   # raiz del repo

SESSIONS="${SESSIONS:-100}"
COMPOSE="docker compose --env-file .env \
  -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.poc.yml"

echo "==> [1/5] .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    .env creado desde .env.example (defaults dev)."
else
  echo "    .env ya existe -- se respeta."
fi

echo "==> [2/5] Levantando stack multi-instancia (build incluye psycopg2-binary)..."
$COMPOSE up -d --build

echo "==> [3/5] Esperando a que la API quede healthy via nginx-poc:8080..."
for i in $(seq 1 60); do
  if curl -sf -o /dev/null http://localhost:8080/api/v1/health/live; then
    echo "    API healthy (intento $i)."
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "    ERROR: la API no quedo healthy en 5 min. Revisar '$COMPOSE logs api'." >&2
    exit 1
  fi
  sleep 5
done

echo "==> [4/5] Migraciones (revision nombrada -> sortea multi-head; 0005 se saltea)..."
$COMPOSE exec -T api alembic upgrade 0004
$COMPOSE exec -T api alembic upgrade 0006

echo "==> [5/5] Seed de $SESSIONS sesiones..."
$COMPOSE cp poc/k6/seed.py api:/tmp/seed.py
$COMPOSE exec -T api python /tmp/seed.py --sessions "$SESSIONS" > poc/k6/sessions.json
python3 -c "import json;print(json.load(open('poc/k6/sessions.json'))[0]['exam_id'],end='')" > poc/k6/.exam_id

echo ""
echo "OK. Bootstrap completo."
echo "   sesiones: $(python3 -c "import json;print(len(json.load(open('poc/k6/sessions.json'))))")"
echo "   exam_id : $(cat poc/k6/.exam_id)"
echo ""
echo "Siguiente: barrido del Bloque 5 (ver poc/README.md). Ej. un escalon:"
echo "   docker run --rm --network proctoring_proctoring \\"
echo "     -v \"\$(pwd)/poc/k6:/scripts\" -w /scripts \\"
echo "     -e POC_JWT_SECRET=poc-secret-k6-do-not-use-in-prod \\"
echo "     -e BASE_WS=ws://nginx-poc:8080 \\"
echo "     grafana/k6 run --vus 100 --duration 60s /scripts/students.js"
