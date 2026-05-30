"""Adaptador de persistencia: PostgreSQL/TimescaleDB via SQLAlchemy.

El engine async y los repositorios concretos se cablean con el dominio (C-05).
En C-04 solo existe el contrato de conexion (DATABASE_URL por entorno) y el
smoke de conectividad (tests 5.3).
"""
