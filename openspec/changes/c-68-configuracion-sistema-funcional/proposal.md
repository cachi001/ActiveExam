## Why

La pantalla **"Configuración del Sistema"** (`Configuracion.tsx`, 4 pestañas) hoy es mayormente **cosmética**: solo la pestaña *Scoring* persiste contra el backend (`/scoring/config`). Las pestañas *Proctoring*, *Detección* y *Consentimiento* **guardan con un toast mock** y nunca tocan la base. Peor aún, **el scoring persistido tampoco se consume server-side**: el cálculo del score final usa pesos hardcodeados (`_PESO_SEVERIDAD_DEFAULT` en `risk_score.py`), de modo que **editar la config NO cambia el resultado de los exámenes** — exactamente lo contrario de lo que el dueño necesita ("que TEST DETECCIÓN y los EXÁMENES usen LA CONFIGURACIÓN DEL SISTEMA ACTUALIZADA").

Además, el **consentimiento de perfil del usuario NO se persiste server-side** (vive en `localStorage` demo `ae_demo_enrollment`). Esto es un **incumplimiento de la Ley 25.326**: el consentimiento debe ser **demostrable, versionado, revocable y atado al `usuario_id`**. Esta es la deuda diferida ("Camino B") que el dueño postergó "para cuando mejoremos la parte de USUARIOS" — y este change ES esa etapa.

## What Changes

- **Configuración del Sistema funcional y persistida** como fuente de verdad server-side: scoring (ya existe), **umbrales de detección**, **umbral de cola de revisión**, **detectores activos**, **retención default** y **parámetros de consentimiento** pasan a una tabla tipada `configuracion_sistema` versionada (hoy mock-only).
- **Endpoint de config efectiva** `GET /api/v1/config/effective` con número de versión/ETag: una sola lectura autoritativa (pesos + umbrales + umbral + detectores + versión de consentimiento) que consumen TEST DETECCIÓN y los exámenes.
- **Consumo server-side de la config (cierra GAP #1)**: `SessionFinalizationService` y el scoring de proctoring leen pesos/umbrales **vivos desde la BD**, no mapas hardcodeados. **L2.5 intacto**: el score PRIORIZA, nunca sanciona.
- **[CRÍTICO] Persistencia del consentimiento de perfil (cierra GAP #2, Ley 25.326)**: nueva tabla `consentimiento_perfil` atada a `usuario_id` (versión, hash, timestamp, estado otorgado/revocado/via_alternativa), con endpoints reales POST/GET/revoke; reemplaza el path `localStorage`. Eliminación al egreso (atada a retención/DSR).
- **"Números más fáciles"**: capa de presentación que mapea unidades internas (ms, 0–1) a una escala intuitiva (segundos, sensibilidad baja/media/alta) para el usuario no técnico. Los valores autoritativos siguen server-side.
- **Mejoras de admin**: las 3 pestañas mock se cablean a endpoints reales; validación, textos de ayuda, claridad; versionado/auditoría de cada cambio de config (reusa `audit_log`).
- **Migraciones Alembic en DOS pasos** que contemplan **la rama SLIM (Railway prod) y la full** — prod NO tiene tabla `consentimiento` ni config global hoy.

## Capabilities

### New Capabilities
- `system-configuration`: tabla tipada `configuracion_sistema` (global, versionada), endpoint de config efectiva con versión/ETag, edición con RBAC+MFA y auditoría inmutable de cada cambio.
- `config-driven-scoring`: el cálculo de score server-side (finalización + proctoring) lee pesos y umbrales vivos desde la config persistida en vez de constantes hardcodeadas.
- `effective-config-consumption`: TEST DETECCIÓN y los exámenes cargan la config efectiva al inicio (reemplazo del `DEFAULT_CONFIG` hardcodeado como baseline) con invalidación de caché al editar.
- `profile-consent-persistence`: **[CRÍTICO]** persistencia server-side del consentimiento de perfil por usuario — demostrable, versionado, revocable, atado a `usuario_id`, eliminado al egreso (Ley 25.326).
- `config-friendly-scale`: capa de presentación "números más fáciles" que mapea unidades internas a una escala intuitiva en la UI de admin.

### Modified Capabilities
- `session-finalization`: la consolidación SHALL usar los pesos vivos de la config persistida (no `_PESO_SEVERIDAD_DEFAULT`).
- `incremental-risk-score`: el scoring incremental/server-side SHALL ponderar por la config persistida vigente.
- `state-transition-rules`: los umbrales de transición SHALL ser leíbles desde la config server-side (hoy solo constantes de frontend).
- `admin-detection-test-harness`: el harness SHALL poder cargar la config efectiva real como baseline (en vez de `DEFAULT_CONFIG` hardcodeado).
- `exam-config-access-control`: la edición de la configuración global SHALL restringirse a `admin_sistema` con MFA y quedar auditada.
- `affirmative-consent-capture`: el acuse afirmativo de perfil SHALL persistirse server-side (no `localStorage`).

## Impact

- **Backend**: nueva tabla `configuracion_sistema` + `consentimiento_perfil`; nuevo router `config/` (effective + edición); modificación de `application/scoring/finalization.py`, `application/proctoring/scoring.py`, `risk_score.py` para leer config viva; nuevo router/endpoints de consentimiento de perfil; reuso de `audit_log` para auditoría de config. Schemas Pydantic `extra='forbid'`.
- **Migraciones**: Alembic en dos pasos sobre la **rama slim** (0013→…) y la full; prod Railway requiere las dos tablas nuevas.
- **Frontend**: `SeccionProctoring.tsx`, `SeccionDeteccion.tsx`, `SeccionConsentimiento.tsx` cableadas a endpoints reales; `Consent.tsx` deja de usar `localStorage`; `useExamProctoring.ts` y `useDetectionHarness.ts` leen la config efectiva; generalización de `resetScoringWeightsCache()`; capa de mapeo "números más fáciles".
- **Gobernanza**: el grupo de consentimiento es **CRÍTICO** (auth/privacidad) — requiere aprobación humana explícita antes de `/opsx:apply`. Atado a c-01 (DPIA) para formalizar la clasificación del consentimiento como dato sensible (no bloquea el propose).
- **L2.5**: ningún cambio introduce sanción automática; el score sigue priorizando la cola de revisión humana.
