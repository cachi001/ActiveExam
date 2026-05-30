"""Dominio PURO del contrato de evento de telemetria (C-10).

- ``schema``: tipos y severidades del dominio (RN-EV-04), contrato versionado con
  compatibilidad hacia atras (RN-EV-05), validacion de campos obligatorios.
- ``signature``: validacion de la firma HMAC del evento/heartbeat contra la clave
  de sesion ANTES de persistir (RN-GLB-01, zero trust); reusa la primitiva HMAC de
  ``app.domain.biometrics.custody``.

PUREZA (D1): sin SQLAlchemy/FastAPI; ``hashlib``/``hmac`` son stdlib permitidas. El
transporte (WebSocket), la persistencia (hypertable) y el backplane viven en
infraestructura, detras de puertos.
"""
