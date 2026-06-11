# Proposal — C-06 `auth-rbac-keycloak`

> **Naturaleza del change**: autenticación federada y autorización contextual, governance **CRÍTICO**. Es la **puerta de entrada de seguridad** del sistema: nadie toca una sesión, una evidencia o un panel sin pasar por aquí. Un hueco (un JWT mal validado, un proctor que ve exámenes que no le asignaron, un revisor que cruza su jurisdicción, MFA opcional para acceso a evidencia) compromete toda la cadena de custodia y el cumplimiento legal. Depende de C-05 (entidad `Usuario` para el JIT provisioning).

## Why

Implementar autenticación a mano es catastrófico si falla (session fixation, CSRF, manejo de tokens — DD-09); por eso el dominio delega identidad a **Keycloak** (OAuth2/OIDC/SAML) y federa con el directorio institucional. Pero la autorización del proctoring tiene una exigencia que va más allá de "tener un rol": los permisos **no son globales, son contextuales** (`03` §RBAC):

- Un **proctor** ve **solo los exámenes que le fueron asignados** (vía la entidad Asignación de C-05), no todos.
- Un **revisor académico** opera **solo sobre su jurisdicción**, no sobre cualquier sesión flaggeada.

Si esto se implementa como RBAC plano (rol → permiso global), un proctor podría observar exámenes ajenos y un revisor cruzar jurisdicciones — una fuga de datos sensibles bajo la Ley 25.326. La autorización debe ser **contextual** sobre los 7 roles funcionales (`03`).

Además, el acceso a evidencia y administración exige **MFA obligatorio** (TOTP mínimo, WebAuthn recomendado — `03`, `08` §Seguridad), y el JWT debe **validarse localmente** contra el JWKS cacheado (sin round-trip a Keycloak en cada request, para sostener el pico de ~47 auth/min y el tráfico general), con access tokens de 15–60 min y refresh rotativos. Los canales de tiempo real (WS del estudiante, SSE del panel) no quedan fuera: el **handshake se valida con JWT y se revalida periódicamente** (`03` §Suposición, Flujo 1), porque una conexión de larga vida no puede confiar para siempre en un token emitido al inicio.

Este change convierte "tenemos a Keycloak corriendo (C-04) y la entidad Usuario (C-05)" en "el sistema autentica federadamente, provisiona usuarios JIT, y autoriza contextualmente con MFA donde el dominio lo exige".

## What Changes

- **Federación Keycloak** (OAuth2/OIDC/SAML) con el directorio institucional, y **JIT provisioning**: el `Usuario` (C-05) se crea/actualiza al **primer login federado**, sin seed masivo (`04` §Usuario, Flujo 1).
- **Validación local de JWT** contra **JWKS cacheado** (clave pública de Keycloak), con `JWT_AUDIENCE` verificado; **access tokens 15–60 min**; **refresh tokens rotativos**; endpoint **`POST /api/v1/auth/refresh`** (`08` §Seguridad, `03` §Rutas públicas).
- **RBAC contextual** sobre los **7 roles** (estudiante, proctor, revisor académico, coordinador, admin de exámenes, admin del sistema, auditor — `03`): el **proctor** accede solo a exámenes asignados (vía Asignación); el **revisor** solo a su jurisdicción; cada acceso a evidencia se audita con propósito declarado.
- **MFA obligatorio** para roles con acceso a evidencia/administración (proctor, revisor, coordinador, administradores): **TOTP mínimo, WebAuthn recomendado** (`03`, `08`).
- **Validación de handshake WS/SSE** con JWT al conectar y **revalidación periódica** durante la vida de la conexión (`03` §Suposición).
- **Rate limiting** en Keycloak y Nginx (anti fuerza bruta, `08` §Seguridad) y definición de las **rutas públicas** (login institucional, estáticos del frontend; `/api/v1/auth/refresh` opera con token, no es estrictamente pública — `03` §Rutas públicas).
- **Tests**: validación de JWT, expiración/refresh, **aislamiento por rol contextual** (proctor no ve exámenes ajenos, revisor no cruza jurisdicción), **MFA enforcement**, y **rechazo de handshake WS/SSE sin token**.

## Capabilities

> Estas capabilities modelan la **autenticación federada y la autorización contextual** del sistema. Su Done es: el JWT se valida localmente, el usuario se provisiona JIT, el RBAC contextual aísla por asignación/jurisdicción, el MFA se exige donde corresponde, y los canales de tiempo real rechazan handshakes sin token.

### New Capabilities

- `keycloak-federation-jit`: federación Keycloak (OAuth2/OIDC/SAML) y JIT provisioning del Usuario al primer login federado (DD-09, `04` §Usuario).
- `jwt-validation-refresh`: validación local de JWT contra JWKS cacheado, access 15–60 min, refresh rotativo y `POST /api/v1/auth/refresh`.
- `contextual-rbac`: RBAC con permisos contextuales sobre 7 roles — proctor solo exámenes asignados, revisor solo su jurisdicción (`03` §RBAC).
- `mfa-enforcement`: MFA obligatorio (TOTP mín., WebAuthn recomendado) para roles con acceso a evidencia/administración (`03`, `08`).
- `realtime-handshake-auth`: validación de handshake WS/SSE con JWT y revalidación periódica, más rate limiting y rutas públicas (`03`, `08`).

### Modified Capabilities

<!-- Ninguna. No existen specs de dominio previas en openspec/specs/ que este change modifique. -->

(Ninguna — este change crea la capa de auth/RBAC; no modifica requisitos previos.)

## Impact

- **Dependencias entrantes**: **C-05** (entidad `Usuario` y la relación `Asignación` proctor↔examen, necesarias para el JIT provisioning y el RBAC contextual del proctor) y **C-04** (Keycloak corriendo en el compose, Nginx para rate limiting, contrato de `KEYCLOAK_*`/`JWT_AUDIENCE`).
- **Bloquea**: todo change que exponga endpoints o canales protegidos (ingesta de eventos, paneles, evidencia, revisión) — sin auth/RBAC no pueden exponer nada de forma segura.
- **Decisiones que consume**: DD-09 (Keycloak como IdP), `08` §Seguridad (MFA, rate limiting, TLS), la entidad Usuario y Asignación de C-05.
- **Decisiones que produce** (consumidas downstream): el contrato de validación de JWT (que todo endpoint y handshake usa), el modelo de autorización contextual (que la ingesta, el panel y la evidencia aplican), y la lista de rutas públicas.
- **Actores/sistemas afectados**: todos los roles (`03`) — el estudiante autentica y consiente, el proctor/revisor acceden con MFA y contexto, el auditor lee. El IdP institucional (federación) y Nginx (rate limiting/TLS).
- **Riesgo principal**: RBAC plano en vez de contextual (proctor ve exámenes ajenos / revisor cruza jurisdicción) o MFA opcional para acceso a evidencia — ambos serían fugas de datos sensibles bajo Ley 25.326. Mitigado por tests de aislamiento por rol contextual y de MFA enforcement.
