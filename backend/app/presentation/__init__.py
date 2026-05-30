"""Capa de presentacion: routers FastAPI (REST /api/v1), WS/SSE, healthchecks.

En C-04 solo vive el router base con healthchecks (liveness/readiness) que Nginx
usa para sacar instancias caidas del pool (DD-10). Los endpoints de dominio y los
handlers WS/SSE llegan en changes posteriores.
"""
