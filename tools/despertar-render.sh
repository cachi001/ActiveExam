#!/usr/bin/env bash
# Despierta el backend en Render antes de un examen (c-78 §18.2).
#
# El plan free duerme el servicio tras un rato sin tráfico. El costo de eso NO es
# "el primer alumno espera": es que **ese ingreso se pierde**. El launch LTI desde
# Moodle llega como POST, el alumno ve la pantalla de arranque del hosting, y al
# recargar el navegador reintenta el POST y Render responde 422. El alumno queda
# afuera sin entender por qué, justo cuando empieza el examen.
#
# Correr esto unos minutos antes de abrir el examen. Pega hasta que el servicio
# conteste y dice cuánto tardó en despertar.
#
#   bash tools/despertar-render.sh                    # default: producción
#   bash tools/despertar-render.sh https://otra-url   # otra instancia
#
# El endpoint elegido (`/exam-content/periodos`) es público, no toca la base más
# que para devolver una lista fija y no ensucia ninguna métrica de examen.
set -euo pipefail

BASE="${1:-https://actibeexam.onrender.com}"
ENDPOINT="$BASE/api/v1/exam-content/periodos"
INTENTOS="${DESPERTAR_INTENTOS:-30}"
ESPERA="${DESPERTAR_ESPERA:-10}"

printf 'Despertando %s\n' "$BASE"
inicio=$(date +%s)

for i in $(seq 1 "$INTENTOS"); do
  # Sin `|| echo`: cuando curl falla ya escribe "000" en stdout, y el echo extra
  # lo duplicaba ("HTTP 000000").
  codigo=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$ENDPOINT" || true)
  ahora=$(date +%s)
  transcurrido=$(( ahora - inicio ))

  if [ "$codigo" = "200" ]; then
    # Un segundo request mide el servicio YA despierto: si el primero tardó, lo
    # que interesa saber es que el siguiente alumno no va a esperar lo mismo.
    latencia=$(curl -s -o /dev/null -w '%{time_total}' --max-time 30 "$ENDPOINT" || echo "?")
    printf 'DESPIERTO tras %ss (intento %s). Siguiente request: %ss.\n' \
      "$transcurrido" "$i" "$latencia"
    exit 0
  fi

  printf '  intento %s: HTTP %s (%ss)\n' "$i" "$codigo" "$transcurrido"
  sleep "$ESPERA"
done

printf 'NO DESPERTO tras %s intentos. Revisar el dashboard de Render antes de abrir el examen.\n' \
  "$INTENTOS" >&2
exit 1
