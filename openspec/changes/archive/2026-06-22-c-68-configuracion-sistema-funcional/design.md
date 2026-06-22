## Context

La plataforma tiene una pantalla de **Configuración del Sistema** con 4 pestañas (`Configuracion.tsx`), pero solo *Scoring* persiste; las demás guardan con toast mock. Y aunque `evento_score_config` (scoring) está persistido y seedeado, **el backend no lo consume**: el score final usa `_PESO_SEVERIDAD_DEFAULT` hardcodeado. Resultado: la config es una vidriera, no una fuente de verdad.

Paralelamente, el **consentimiento de perfil** vive en `localStorage` (`ae_demo_enrollment`), sin persistencia server-side — un problema legal duro (Ley 25.326). Esta deuda fue diferida explícitamente para "la mejora de USUARIOS"; este change la salda.

**Restricciones duras del proyecto** (de `CLAUDE.md`):
- L2.5: el score PRIORIZA, nunca sanciona; decisión humana terminal.
- Consentimiento = dato sensible (Ley 25.326): demostrable, versionado, revocable, atado a `usuario_id`, eliminado al egreso.
- Cliente = sensor no confiable; la config autoritativa vive **server-side**.
- Dos arquitecturas de modelos: **full** (`main.py`) y **slim** (`main_slim.py`, Railway prod). Prod hoy = 11 tablas, **sin `consentimiento` ni config global**. Operación de prod: `railway run --service Postgres -- node tools/db/query.js`.
- Pydantic `extra='forbid'`; snake_case Python; PascalCase React; tests sin mocks de DB (DB real/efímera); Alembic destructivo en dos pasos.

**Stakeholders**: `admin_sistema` (edita config), `admin_examenes` (overrides por examen, fuera de scope salvo lectura), estudiante (otorga/revoca consentimiento), DPO (clasificación del consentimiento, c-01).

## Goals / Non-Goals

**Goals**
1. La Configuración del Sistema es la **fuente de verdad persistida** de scoring + umbrales + detectores + retención + consentimiento.
2. **TEST DETECCIÓN y los exámenes consumen la config actualizada** (no constantes hardcodeadas).
3. El **consentimiento de perfil se persiste** server-side: demostrable, versionado, revocable, atado al usuario.
4. La UI de admin muestra **"números más fáciles"** sin perder la autoridad de los valores internos.
5. Toda edición de config queda **auditada y versionada**.

**Non-Goals**
- NO crear overrides de config **por examen** (la tabla `ExamenModel.parametros` ya existe; conectarla es un change futuro). Este change fija los **defaults globales**.
- NO unificar `main.py`/`main_slim.py` en un solo factory con env flag (deuda separada).
- NO migrar el acuse **por examen** (`consentimiento` full-only) a slim — este change agrega el consentimiento **de perfil**, ortogonal al acuse por examen.
- NO introducir veredicto/sanción automática (L2.5 inviolable).
- NO tocar cola/transporte/tiempo real (no depende de c-03).

## Decisions

### D1 — Modelo de datos: tablas tipadas, no blob key-value
**Decisión**: mantener **tablas tipadas**. Scoring sigue en `evento_score_config`. Se agrega `configuracion_sistema` con columnas tipadas para los defaults globales hoy mock-only:
- Umbrales de detección: `face_absent_ms` (int), `multiple_faces_frames` (int), `gaze_deviation_threshold` (numeric 0–1), `gaze_sustained_ms` (int), `gaze_fixation_tolerance` (numeric 0–1).
- `umbral_cola_revision` (int, 0–100), `detectores_activos` (text[] o jsonb de TipoEvento), `retencion_dias_default` (int).
- `consent_version_vigente` (varchar) — puntero a la versión de texto de consentimiento actual.
- `version` (int, monotónica), `updated_at`, `updated_by`.

Se usa **una sola fila singleton** (PK fija, p.ej. `id='global'`) para los defaults globales; el versionado se lleva con `version` + filas de auditoría en `audit_log` (snapshot before/after).

**Alternativa descartada**: tabla genérica `config(key, value jsonb)`. Rechazada porque pierde validación de tipos, dificulta migraciones y queries, y el dominio ya tiene un conjunto **cerrado y conocido** de parámetros. El costo de tipar es bajo y la trazabilidad es mejor.

### D2 — Versionado y auditoría
**Decisión**: cada edición incrementa `configuracion_sistema.version` (monotónica) y escribe una fila inmutable en `audit_log` con `actor`, `accion='config_update'`, `before`, `after`. La `version` actúa como **ETag** para que los clientes detecten config rancia. Edición restringida a `admin_sistema` con **MFA** vía `require_roles(Rol.ADMIN_SISTEMA)` + `require_mfa`.

**Alternativa descartada**: tabla histórica `configuracion_sistema_historial` dedicada. Innecesaria: `audit_log` ya es inmutable y es el lugar canónico de trazabilidad; evita duplicar mecanismo.

### D3 — Endpoint de config efectiva + caché
**Decisión**: `GET /api/v1/config/effective` (cualquier usuario autenticado) retorna el objeto autoritativo completo: `{ version, scoring_weights, thresholds, umbral_cola_revision, detectores_activos, consent_version_vigente }` con header/campo `version` como ETag. TEST DETECCIÓN y los exámenes leen ESTO al inicio. La invalidación de caché en el cliente generaliza el `resetScoringWeightsCache()` existente a un `resetEffectiveConfigCache()`. El backend puede cachear en memoria con invalidación por `version`.

El **harness sigue air-gapped para la captura** (no manda eventos al backend), pero **SÍ puede cargar la config efectiva real** como baseline en lugar del `DEFAULT_CONFIG` hardcodeado — así "TEST DETECCIÓN usa la config actualizada".

**Alternativa descartada**: que cada consumidor llame a `/scoring/weights` + endpoints sueltos por separado. Rechazada: múltiples round-trips, sin versión coherente, difícil detectar staleness.

### D4 — Consumo server-side (cierra GAP #1)
**Decisión**: introducir un `ConfigService` (o repo) que carga la config efectiva desde la BD. `SessionFinalizationService.consolidar()` y `application/proctoring/scoring.py:calcular_score()` **inyectan los pesos vivos** desde ese servicio en vez de `_PESO_SEVERIDAD_DEFAULT` / `PESOS_SEVERIDAD`. El fallback hardcodeado se mantiene SOLO como red de seguridad si la config no está disponible (degradación graceful, RN-GLB-03), nunca como fuente normal. **L2.5**: el score sigue siendo prioridad para la cola, jamás veredicto.

**Snapshot de config por sesión**: para reproducibilidad forense, la consolidación SHALL registrar la `version` de config usada en el cálculo (en el resultado/score), de modo que un cambio posterior de config no altere el score de sesiones ya finalizadas. "La config actualizada aplica a sesiones **nuevas**" (coherente con el copy actual de la UI).

### D5 — Persistencia del consentimiento de perfil (CRÍTICO, cierra GAP #2)
**Decisión**: nueva tabla `consentimiento_perfil` en **full Y slim**:
- `id` (uuid PK), `usuario_id` (FK usuario, NOT NULL, indexado), `version_texto` (varchar), `hash_texto` (varchar 64, SHA-256 del texto consentido), `timestamp` (timestamptz), `estado` (enum: `otorgado` | `revocado` | `via_alternativa`), `hash_registro` (SHA-256 de `usuario_id|version_texto|timestamp|estado` para integridad).
- **Append-only**: revocar/re-otorgar inserta una nueva fila; el estado vigente es la fila más reciente por `usuario_id`. Esto preserva la **demostrabilidad histórica** (Ley 25.326).
- Endpoints: `POST /api/v1/consent/profile` (otorgar), `GET /api/v1/consent/profile` (estado vigente del usuario), `POST /api/v1/consent/profile/revoke` (revocar). `affirmative_action` explícito (sin default, igual que el acuse por examen, D2 de consent existente).
- Reemplaza `registrarConsentimientoPerfil` (demo) y el path `localStorage ae_demo_enrollment`.
- **Eliminación al egreso**: hook atado al motor de retención/DSR existente (c-17/c-19) — el consentimiento de perfil se elimina al egreso del estudiante, igual que el embedding.

**Alternativa descartada**: extender la tabla `consentimiento` (per-examen, full-only) con `exam_id` nullable. Rechazada: mezcla dos semánticas (perfil vs examen), y `consentimiento` no existe en slim/prod. Tabla separada es más limpia y migra a slim sin arrastrar el acuse por examen.

### D6 — "Números más fáciles" (capa de presentación)
**Decisión**: el mapeo vive **en el frontend** (capa de presentación), los valores autoritativos siguen server-side en unidades internas. Tabla de mapeo:

| Parámetro interno | Unidad interna | Representación UI |
|---|---|---|
| `face_absent_ms` | ms | **segundos** (3000 → "3 s") |
| `gaze_sustained_ms` | ms | **segundos** |
| `gaze_deviation_threshold` | 0–1 | **sensibilidad 1–5** o baja/media/alta |
| `gaze_fixation_tolerance` | 0–1 | **sensibilidad 1–5** o baja/media/alta |
| `multiple_faces_frames` | frames | **"N detecciones seguidas"** |
| `peso` (scoring) | 0–100 | "importancia" 0–100 (ya intuitivo) |
| `umbral_cola_revision` | 0–100 | "% para entrar a revisión" |

La conversión ida/vuelta se hace en un módulo `frontend/src/config/` puro (patrón `institution-config`), con tests. La UI nunca envía la escala amigable cruda: convierte a unidad interna antes de POST/PATCH.

### D7 — ¿Partir o no el change?
**Recomendación**: **UN change grande con grupos de tasks**, PERO con el **grupo de consentimiento (D5) marcado CRÍTICO y bloqueado por aprobación humana** antes de codear (gobernanza auth/privacidad). 

**Tradeoff**: partirlo en un sub-change `profile-consent-persistence` aislado da un gate legal más duro y un PR más chico de revisar; el costo es coordinar dos changes que comparten la migración slim y la UI de Configuración. Dado que el dueño lo pidió como "un change grande" y los grupos comparten infraestructura (migración slim, pantalla de Configuración, audit_log), **recomiendo mantenerlo unido** y usar el flag CRÍTICO + checkpoint de aprobación en `tasks.md` como gate. Si el dueño prefiere un gate legal formal, se separa el Grupo 3 a su propio change.

## Risks / Trade-offs

- **[Riesgo] Migración slim sobre Railway prod (datos reales)** → Migración Alembic en **dos pasos** (no destructiva primero), probada en DB efímera; `consentimiento_perfil` y `configuracion_sistema` son **tablas nuevas** (additive, bajo riesgo). Verificar con `railway run --service Postgres -- node tools/db/query.js` post-deploy.
- **[Riesgo] Cambiar config a mitad de un examen activo altera scores** → Snapshot de `version` por sesión (D4); la config nueva aplica solo a **sesiones nuevas** (RN-GLB-04: deploys fuera de ventana de examen).
- **[Riesgo] El fallback hardcodeado enmascara una config no leída** → El fallback emite un evento/log de degradación; tests verifican que con config presente se usan los valores vivos (no el fallback).
- **[Riesgo] Consentimiento mal modelado = incumplimiento legal** → Append-only + hash + estado + atado a `usuario_id`; revisión humana/DPO (c-01) antes de `/opsx:apply`. **Grupo CRÍTICO.**
- **[Trade-off] Singleton de config global vs multi-tenant** → Hoy single-institution (UTN FRM); un solo registro global alcanza. Multi-tenant es deuda futura.
- **[Riesgo] L2.5 violado por accidente** → Ninguna ruta nueva emite veredicto; el score solo prioriza la cola. Test explícito de que no hay auto-sanción.

## Migration Plan

1. **Paso 1 (additive)**: migración Alembic que crea `configuracion_sistema` (con fila singleton seedeada con los DEFAULT_CONFIG actuales) y `consentimiento_perfil`, en la **rama slim** (sigue 0013→…) y la full. Sin DROP/ALTER destructivo.
2. **Backend**: `ConfigService`, router `/config/effective` + edición, router consentimiento de perfil, cableado de finalización/scoring a config viva.
3. **Frontend**: cablear las 3 pestañas mock, reemplazar `localStorage` por endpoints, capa de números fáciles, lectura de config efectiva en harness/examen.
4. **Verificación prod (slim/Railway)**: confirmar las dos tablas nuevas vía `tools/db/query.js`; smoke test de edición de config → nueva sesión refleja el cambio.
5. **Rollback**: como las tablas son additive, rollback = revertir el código que las consume + (si necesario) migración down que las elimina (paso 2 destructivo separado, fuera de ventana de examen).

## Open Questions

1. **[Para el dueño/DPO]** ¿Se separa el Grupo 3 (consentimiento de perfil) a su propio change con gate legal formal, o se mantiene unido con checkpoint de aprobación? (Recomendación: unido — D7.)
2. **[Legal/c-01]** ¿La clasificación del consentimiento de perfil como dato sensible y su política de eliminación al egreso ya están cubiertas por el DPIA (c-01), o este change debe esperar esa firma? (No bloquea el propose; sí el apply del Grupo 3.)
3. **[Producto]** ¿El `admin_examenes` debe poder editar la config **global**, o solo `admin_sistema`? (Default propuesto: solo `admin_sistema` edita global; `admin_examenes` edita overrides por examen — fuera de scope.)
4. **[UX]** Para la escala "números más fáciles" de sensibilidad, ¿1–5 o baja/media/alta? (Default propuesto: baja/media/alta por simplicidad para el no técnico.)
5. **[Datos]** ¿Migrar los consentimientos de perfil hoy en `localStorage` de usuarios existentes, o se re-piden? (Default propuesto: re-pedir — el localStorage demo no es fuente legal válida.)
