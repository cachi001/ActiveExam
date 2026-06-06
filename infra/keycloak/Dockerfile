# Keycloak para Railway (auth real en producción) — multi-stage oficial.
#
# - La augmentation pesada (`kc.sh build`) corre en BUILD time → arranque liviano
#   (`start --optimized`), sin OOM.
# - Keycloak escucha en el puerto que Railway inyecta ($PORT), no en 8080 fijo,
#   para que Railway pueda alcanzarlo (sino: 502 / reinicio en loop).
# - Las opciones BUILD-TIME (db, health, http-enabled) van en el builder; las
#   RUNTIME (hostname, proxy, http-port, credenciales DB) en el stage final.
#
# Variables en Railway (servicio Keycloak):
#   KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD
#   KC_DB_URL / KC_DB_USERNAME / KC_DB_PASSWORD   (referencia a Postgres-A0pj)
#   KC_HOSTNAME = https://<tu-keycloak>.up.railway.app   (recomendado para el issuer)

# --- Stage 1: build optimizado (opciones build-time) ---
FROM quay.io/keycloak/keycloak:26.0.7 AS builder
# Solo opciones BUILD-TIME: --db y --health-enabled. (--http-enabled y --cache son
# RUNTIME → van por ENV / CMD start, NO acá.)
RUN /opt/keycloak/bin/kc.sh build --db=postgres --health-enabled=true

# --- Stage 2: runtime liviano ---
FROM quay.io/keycloak/keycloak:26.0.7
COPY --from=builder /opt/keycloak/ /opt/keycloak/
COPY proctoring-realm.json /opt/keycloak/data/import/proctoring-realm.json

ENV KC_HTTP_ENABLED=true \
    KC_PROXY_HEADERS=xforwarded \
    KC_HOSTNAME_STRICT=false

# Puerto 8080 fijo (= Target Port del dominio Railway). --cache=local (RUNTIME):
# un solo nodo, sin cluster JGroups que reiniciaba en loop.
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized", "--import-realm", "--http-port=8080", "--cache=local"]
