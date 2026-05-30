# Imagen del backend FastAPI. Mono-hilo (DD-10): un proceso uvicorn, un hilo
# asincrono por instancia. El escalado es horizontal (replicas detras de Nginx),
# NO multi-worker dentro de la imagen.
#
# Secretos (DD-5 / `08` Gestion de secretos): NUNCA se copian a la imagen. Se
# inyectan en runtime via Vault en tmpfs efimero. Este Dockerfile no contiene
# ningun valor sensible.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias primero (capa cacheable).
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# Codigo de la app y migraciones.
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

# Usuario no-root (minimo privilegio).
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Mono-hilo: UN worker, UN proceso. El escalado lo hace el orquestador (replicas).
# No-shell form para senales correctas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
