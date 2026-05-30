# Certificados TLS (local)

Nginx termina **TLS 1.3** (DD-10, `08` Seguridad). Para el stack LOCAL hace falta
un certificado self-signed en este directorio: `server.crt` + `server.key`.

**NO se versionan claves privadas** (estan en `.gitignore`). En produccion los
certificados los emite la PKI institucional / ACME, no se generan a mano.

## Generar el par self-signed para local (NO ejecutado por el agente)

```bash
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout infra/nginx/tls/server.key \
  -out infra/nginx/tls/server.crt \
  -days 365 \
  -subj "/CN=localhost"
```

Tras generarlo, `docker compose up nginx` negocia TLS 1.3 contra `https://localhost`.
