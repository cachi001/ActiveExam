# Design — C-06 `auth-rbac-keycloak`

> Design técnico de la **capa de autenticación y autorización**: federación Keycloak + JIT, validación local de JWT contra JWKS, RBAC contextual sobre 7 roles, MFA enforcement, y auth de handshakes WS/SSE. Depende de C-05 (Usuario, Asignación).

## Context

DD-09: Keycloak como IdP (OAuth2/OIDC/SAML) — implementar auth a mano es catastrófico. `08` §Seguridad: JWT validado **localmente** contra clave pública (JWKS cacheado), access 15–60 min, refresh rotativos, MFA obligatorio para roles con acceso a evidencia/administración (TOTP mín., WebAuthn recomendado), rate limiting en Keycloak y Nginx, TLS 1.3. `03` §RBAC: permisos **contextuales** sobre 7 roles (proctor solo exámenes asignados; revisor solo su jurisdicción); MFA para proctor/revisor/coordinador/admins; descarga de clip vía URL firmada con propósito en audit log. Flujo 1: login federado → JWT → refresh vía `/api/v1/auth/refresh`. Capacidad de auth: ~47 auth/min en el pico de inicio, cómodo para Keycloak (`14`).

**Constraints**:
- JWT se valida **localmente** (sin round-trip a Keycloak por request); JWKS **cacheado** con `JWT_AUDIENCE` verificado.
- Autorización **contextual**, no global: proctor ↔ Asignación (C-05); revisor ↔ jurisdicción.
- **MFA obligatorio** para acceso a evidencia/administración: TOTP mínimo, WebAuthn recomendado.
- Handshake **WS/SSE** valida JWT al conectar y **revalida periódicamente** (conexiones de larga vida).
- Usuario provisionado **JIT** al primer login federado (sin seed masivo, C-05).
- Rate limiting en Keycloak + Nginx; rutas públicas mínimas.

## Goals / Non-Goals

**Goals:**
- Federar con el directorio institucional vía Keycloak (OAuth2/OIDC/SAML) y provisionar el Usuario JIT.
- Validar JWT localmente contra JWKS cacheado; gestionar expiración (15–60 min) y refresh rotativo (`/api/v1/auth/refresh`).
- Implementar RBAC contextual sobre los 7 roles (proctor↔asignación, revisor↔jurisdicción).
- Exigir MFA (TOTP mín., WebAuthn recomendado) para roles con acceso a evidencia/administración.
- Autenticar el handshake WS/SSE con JWT y revalidarlo periódicamente.
- Aplicar rate limiting y definir las rutas públicas.

**Non-Goals:**
- NO implementar la lógica de negocio de los paneles, la ingesta ni la evidencia (otros changes) — aquí solo el contrato de auth/RBAC que consumen.
- NO emitir la clave de sesión rotativa del examen ni la firma HMAC de eventos (Flujo 2/3, changes de dominio).
- NO implementar la URL firmada de descarga de clips ni el bucket WORM (changes de evidencia) — aquí solo el requisito de MFA + propósito en audit log para el acceso.
- NO definir el liveness/biometría (Flujo 2, change de biometría).

## Decisions

### D1 — Identidad delegada a Keycloak; JIT provisioning del Usuario
**Decisión**: Keycloak federa con el directorio institucional (OAuth2/OIDC/SAML); el `Usuario` (C-05) se crea/actualiza al **primer login federado** (JIT), tomando identificador institucional, roles y atributos federados.
**Por qué**: DD-09 — auth a mano es catastrófico; JIT evita un seed masivo de usuarios (`04` §Usuario).
**Alternativa considerada**: autenticación propia → riesgo de session fixation/CSRF/tokens (DD-09).

### D2 — Validación local de JWT contra JWKS cacheado
**Decisión**: cada request valida el JWT **localmente** contra el JWKS cacheado de Keycloak (`KEYCLOAK_JWKS_URL`), verificando firma, expiración y `JWT_AUDIENCE`. Access tokens 15–60 min; refresh rotativos vía `POST /api/v1/auth/refresh`.
**Por qué**: sin round-trip a Keycloak por request, sostiene el tráfico y el pico de auth (`14`); refresh rotativo limita el blast radius de un token filtrado.
**Alternativa considerada**: introspección remota por request → latencia y carga sobre Keycloak innecesarias.

### D3 — RBAC contextual, no global, sobre 7 roles
**Decisión**: la autorización evalúa **contexto**, no solo rol: el proctor accede solo a exámenes en su `Asignación` (C-05); el revisor solo a sesiones de su jurisdicción. Cada acceso a evidencia exige propósito declarado persistido en audit log.
**Por qué**: `03` §RBAC — permisos contextuales; RBAC plano permitiría a un proctor ver exámenes ajenos o a un revisor cruzar jurisdicción (fuga de datos sensibles, Ley 25.326).
**Alternativa considerada**: RBAC plano (rol→permiso global) → viola el aislamiento contextual del dominio.

### D4 — MFA obligatorio para acceso a evidencia/administración
**Decisión**: MFA obligatorio (TOTP mínimo, WebAuthn recomendado) para proctor, revisor, coordinador y administradores; enforcement en Keycloak + verificación de que el token refleja el segundo factor.
**Por qué**: `03`/`08` — el acceso a evidencia sensible y a administración no puede depender de un solo factor.
**Alternativa considerada**: MFA opcional → deja la evidencia tras un único factor; inaceptable.

### D5 — Auth de handshake WS/SSE con revalidación periódica
**Decisión**: el handshake de WebSocket (estudiante) y SSE (panel) valida el JWT al conectar y **revalida periódicamente** durante la conexión; un handshake sin token válido se rechaza.
**Por qué**: `03` §Suposición — una conexión de larga vida no puede confiar para siempre en el token inicial; un token revocado/expirado debe cortar el canal.
**Alternativa considerada**: validar solo en el handshake inicial → una conexión persiste tras la expiración/revocación del token.

### D6 — Rate limiting y rutas públicas mínimas
**Decisión**: rate limiting en Keycloak (login) y Nginx (API); rutas públicas mínimas — login institucional (redirección a Keycloak) y estáticos del frontend; `POST /api/v1/auth/refresh` opera con token (no estrictamente pública); todo el resto de la API y los canales exigen JWT.
**Por qué**: `08` §Seguridad (anti fuerza bruta) y `03` §Rutas públicas (superficie pública mínima).
**Alternativa considerada**: sin rate limiting → expuesto a fuerza bruta; rutas públicas amplias → superficie de ataque mayor.

## Modelo de autorización (resumen `03` §RBAC)

| Rol | Recurso | Contexto / Restricción | MFA |
|-----|---------|------------------------|-----|
| Estudiante | Su propia sesión / sus datos (DSR) | Solo su sesión; sin evidencia ajena | — |
| Proctor | Sesiones de exámenes **asignados** | Solo exámenes en su Asignación | Sí |
| Revisor académico | Cola de revisión de **su jurisdicción** | Solo su jurisdicción; cada apertura auditada con propósito | Sí |
| Coordinador operativo | Asignaciones, cola, backlog | Escala a TI | Sí |
| Admin de exámenes | Exámenes, parámetros, asignaciones | — | Sí |
| Admin del sistema | Config técnica, despliegues, backups | Acceso elevado | Sí |
| Auditor | Audit log, registros, evidencia (lectura) | Solo lectura | Sí |

> **El sistema nunca sanciona automáticamente** (L2.5): la decisión disciplinaria final es humana; este change solo controla el acceso a los recursos, no decide casos.

## Risks / Trade-offs

- **[RBAC plano en vez de contextual: proctor ve exámenes ajenos / revisor cruza jurisdicción]** → Mitigación: D3 + tests de aislamiento por rol contextual (proctor sobre examen no asignado → 403; revisor fuera de jurisdicción → 403).
- **[MFA opcional para acceso a evidencia/administración]** → Mitigación: D4 + test de MFA enforcement (rol con acceso a evidencia sin segundo factor → rechazado).
- **[JWT mal validado / JWKS no cacheado / audiencia no verificada]** → Mitigación: D2 + tests de validación de firma, expiración, audiencia y refresh.
- **[Conexión WS/SSE persiste tras expiración/revocación del token]** → Mitigación: D5 + test de rechazo de handshake sin token y de corte por revalidación periódica.
- **[Fuerza bruta sobre login]** → Mitigación: D6 — rate limiting en Keycloak + Nginx.
- **Trade-off aceptado**: la validación local de JWT implica que la revocación no es instantánea hasta la expiración del access token (15–60 min); mitigado por tokens cortos, refresh rotativo y revalidación periódica en canales de larga vida.

## Migration Plan

1. Configurar el realm/clientes de Keycloak y la federación con el directorio institucional (sobre el Keycloak que levantó C-04).
2. Implementar el JIT provisioning del Usuario (C-05) al primer login federado.
3. Implementar la validación local de JWT (JWKS cacheado, audiencia, expiración) y `POST /api/v1/auth/refresh` con refresh rotativo.
4. Implementar el RBAC contextual (proctor↔Asignación, revisor↔jurisdicción) y el MFA enforcement.
5. Implementar la auth de handshake WS/SSE con revalidación periódica; rate limiting y rutas públicas.
6. Tests: validación JWT, expiración/refresh, aislamiento por rol contextual, MFA enforcement, rechazo de handshake sin token.
7. **Criterio de salida**: auth federada + JIT + RBAC contextual + MFA + handshake seguro verificados ⇒ endpoints y canales protegidos pueden exponerse.

**Rollback**: deshabilitar la integración de auth deja el sistema sin superficie protegida expuesta (no hay endpoints de dominio aún que dependan de ella en producción); se revierte la configuración del realm sin pérdida de datos.

## Open Questions

- Lista **canónica** de rutas públicas → `03` §Rutas públicas la marca como no especificada en la fuente; este change fija la lista mínima (login + estáticos) y la documenta; `10_preguntas_abiertas.md` la rastrea.
- Definición operativa de "jurisdicción" del revisor (cómo se mapea a sesiones) → se modela como atributo/scope del Usuario; el detalle de mapeo lo fija administración.
- ¿WebAuthn obligatorio o recomendado por rol? → `03`/`08`: TOTP mínimo obligatorio, WebAuthn recomendado; la política por rol la define seguridad.
