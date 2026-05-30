"""Sub-paquete de auth de DOMINIO (PURO).

Modela las reglas de autenticacion/autorizacion que son DECISIONES DE NEGOCIO y
no dependen de framework ni de infraestructura (C-06):

- ``roles``: los 7 roles funcionales (`03` §RBAC) y que rol exige MFA.
- ``identity``: el principal autenticado (claims ya validados) como value object puro.
- ``authorization``: el RBAC CONTEXTUAL (proctor↔asignacion, revisor↔jurisdiccion)
  y el MFA enforcement, expresados como funciones puras sobre el principal + contexto.

La VALIDACION CRIPTOGRAFICA del JWT (firma RS256, JWKS) y la federacion Keycloak
viven en ``app.infrastructure.auth`` (dependen de libs/red): el dominio solo
consume el resultado ya validado (los claims) y decide la autorizacion.

Regla dura D1/test_architecture: este paquete NO importa fastapi/sqlalchemy/infra.
"""

from __future__ import annotations
