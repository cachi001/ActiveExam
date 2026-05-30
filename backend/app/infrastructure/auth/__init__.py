"""Adaptador de autenticacion: validacion de JWT contra Keycloak (JWKS).

Auth REAL (validacion de tokens, RBAC contextual) es scope de C-06. En C-04
solo corre el contenedor Keycloak y se fija el contrato de env vars KEYCLOAK_*.
"""
