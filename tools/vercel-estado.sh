#!/usr/bin/env bash
# Estado de los deploys de Vercel, desde la terminal.
#
# Existe para no tener que abrir el navegador cada vez que hay que responder
# "¿el frontend en producción ya tiene el último commit?".
#
# El token NO vive en el repo (el repo es público). Se lee de:
#   C:/Users/Emiliano/.claude/secrets/vercel.env
# que tiene VERCEL_TOKEN, VERCEL_PROJECT y VERCEL_TEAM. Está acotado al proyecto
# active-exam y vence a los 90 días (creado el 26/8/2026).
#
#   bash tools/vercel-estado.sh          # últimos 5 deploys
#   bash tools/vercel-estado.sh 10       # últimos 10
set -euo pipefail

ENV_FILE="${VERCEL_ENV_FILE:-C:/Users/Emiliano/.claude/secrets/vercel.env}"
if [ -f "$ENV_FILE" ]; then
  set -a; . "$ENV_FILE"; set +a
fi
: "${VERCEL_TOKEN:?falta VERCEL_TOKEN (ver $ENV_FILE)}"
: "${VERCEL_PROJECT:=active-exam}"
: "${VERCEL_TEAM:=emilianos-projects-0cf14c87}"

LIMITE="${1:-5}"
DOCKER="/c/Users/Emiliano/AppData/Local/Programs/DockerDesktop/resources/bin/docker"
[ -x "$DOCKER" ] || DOCKER=docker

api() {
  MSYS_NO_PATHCONV=1 "$DOCKER" run --rm curlimages/curl:latest -s \
    -H "Authorization: Bearer $VERCEL_TOKEN" "$1"
}

echo "=== Últimos $LIMITE deploys de $VERCEL_PROJECT ==="
api "https://api.vercel.com/v6/deployments?projectId=$VERCEL_PROJECT&teamId=$VERCEL_TEAM&limit=$LIMITE" \
  | python -c '
import json,sys,datetime
d=json.load(sys.stdin)
for x in d.get("deployments", []):
    cuando=datetime.datetime.fromtimestamp(x["created"]/1000).strftime("%d/%m %H:%M")
    meta=x.get("meta") or {}
    sha=(meta.get("githubCommitSha") or "")[:7]
    rama=meta.get("githubCommitRef","?")
    msg=(meta.get("githubCommitMessage") or "").splitlines()[0][:52]
    prod="PROD " if x.get("target")=="production" else "     "
    estado=x["readyState"]
    print("  %s%-9s %s  %-8s %-20s %s" % (prod, estado, cuando, sha, rama, msg))
'

echo
echo "=== Commit local vs el desplegado en producción ==="
LOCAL=$(git -C "$(dirname "$0")/.." rev-parse --short HEAD 2>/dev/null || echo "?")
echo "  local HEAD: $LOCAL"
api "https://api.vercel.com/v6/deployments?projectId=$VERCEL_PROJECT&teamId=$VERCEL_TEAM&target=production&limit=1" \
  | python -c '
import json,sys
d=json.load(sys.stdin).get("deployments") or []
if d:
    m=d[0].get("meta") or {}
    sha=(m.get("githubCommitSha") or "?")[:7]
    print("  produccion: %s  (%s)" % (sha, d[0]["readyState"]))
'

cat <<'NOTA'

Ojo al verificar "si el frontend tiene el código nuevo": NO alcanza con mirar el
hash de assets/index-*.js. Ese es solo el arranque (~56 KB) y no cambia aunque sí
cambien las pantallas, que viajan en fragmentos aparte (code splitting de Vite).
Buscar el símbolo nuevo en TODOS los fragmentos, no en el entrypoint.
NOTA
