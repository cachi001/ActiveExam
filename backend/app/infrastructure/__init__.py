"""Capa de infraestructura: adaptadores concretos detras de puertos.

Submodulos:

- ``persistence``: PostgreSQL/TimescaleDB (SQLAlchemy).
- ``messaging``: cola/transporte/backplane. La pieza concreta la DECIDE C-03
  (hipotesis por omision A4: Postgres-como-cola). El adaptador es swappable.
- ``storage``: object storage MinIO/S3.
- ``auth``: validacion de tokens contra Keycloak (real en C-06).
"""
