## Context

El flujo del alumno tiene 6 pasos: Login → Consent → Biometría (paso 3) → Sala Espera → Examen (paso 5) → Cierre (paso 6). La sesión de proctoring se crea hoy dentro de `useExamProctoring` (paso 5), pero la verificación biométrica ocurre en el paso 3. Resultado: `proctoringSessionId` es siempre `null` cuando el alumno completa la biometría.

Adicionalmente, el payload de evento enviado por `handleEvent` incluye el campo `screenshot_sha256_cliente` (hash SHA-256 calculado client-side para la cadena de custodia), pero el schema Pydantic `IngestEventoIn` tiene `extra='forbid'` y rechaza ese campo con 422. El catch traga el error → 0 filas en `proctoring_event`. El endpoint de finalización no existe → `finalizada_en = null` siempre.

**Restricciones**: no hay cambios de esquema de DB (todas las columnas ya existen). El módulo slim en Railway se mantiene sin Auth para endpoints de proctoring (D7 — alcance demo, sin Keycloak). Tests deben correr contra `app.main_slim` con `postgres:16-alpine`.

## Goals / Non-Goals

**Goals:**
- Los eventos detectados durante el examen se persisten en `proctoring_event` (0 → N filas).
- La verificación biométrica se persiste en `proctoring_biometria` (0 → 1 fila por sesión).
- `finalizada_en` se setea al cerrar el examen desde `Cierre.tsx`.
- `Cierre.tsx` muestra conteos reales leídos del backend, no del store Zustand local.
- El campo `screenshot_sha256_cliente` del cliente pasa al backend y se almacena (cadena de custodia).

**Non-Goals:**
- No se modifica el esquema de DB ni se agregan migraciones.
- No se agrega Auth/JWT a los endpoints de proctoring slim (queda para cuando se implemente Keycloak).
- No se cambia la lógica del motor de visión ni los detectores.
- No se implementa deduplicación de eventos en el backend (el buffer client-side ya garantiza idempotencia).

## Decisions

### D1 — Cuándo crear la sesión de proctoring: al inicio del flujo, antes del paso biométrico

**Problema**: la sesión se crea hoy en `useExamProctoring` (paso 5 — examen en vivo), pero la biometría es el paso 3. El `proctoringSessionId` es null durante la biometría.

**Opción A (elegida)**: crear la sesión de proctoring al cargar el flujo del alumno (en `ExamenLayout` o en el primer paso donde se sabe el `exam_id`), guardarla en el store Zustand, y pasarla a todos los pasos siguientes.
- Ventaja: un único punto de creación; la sesión existe para biometría, examen y cierre.
- Desventaja: la sesión puede quedar huérfana si el alumno abandona antes del examen.

**Opción B descartada**: persistir la biometría cuando se crea la sesión (en `useExamProctoring`) y rellenar `session_id` retroactivamente.
- Descartada: requeriría almacenar la biometría en el store y re-enviarla, lo que complica el ciclo de vida y duplica la lógica de envío.

**Opción C descartada**: crear la sesión en `Biometria.tsx` localmente.
- Descartada: `Biometria.tsx` no conoce el `exam_id` ni el `modo` completo; fragmentaría la responsabilidad.

**Decisión**: Opción A. El punto de creación anticipada es el `ExamenLayout` (o el hook que lo envuelve) al resolver `examenActivo` del store. La sesión se crea con `modo='examen'` y `exam_id=examen.id`. Si la sesión ya existe en el store (re-render), no se crea de nuevo.

---

### D2 — `screenshot_sha256_cliente`: agregar al schema `IngestEventoIn`

El cliente calcula SHA-256 del frame para la primera capa de cadena de custodia (C-49, D5). El backend ya almacena `screenshot_sha256` (hash del screenshot que calcula el servidor). Agregar `screenshot_sha256_cliente: str | None = None` a `IngestEventoIn` permite al backend recibir el hash del cliente y compararlo con el propio para detectar manipulaciones.

**Alternativa descartada**: strip del campo en `api.ts` antes de enviar.
- Descartada: pierde la información de cadena de custodia del cliente. El campo es valioso para el revisor humano.

**Decisión**: agregar `screenshot_sha256_cliente: str | None = None` a `IngestEventoIn` y pasarlo al servicio de ingestión para que lo persista en `ProctoringEventModel` (columna a agregar si no existe) o lo ignore si no hay columna — verificar primero.

> ⚠️ **Verificar en apply**: si `ProctoringEventModel` tiene columna `screenshot_sha256_cliente`. Si no existe, hay dos opciones: (a) ignorar el campo en el servicio (no persistir), (b) agregar la columna con migración. Preferir (a) para no generar migración — el campo no bloquea el 422 si se ignora en el servicio; lo importante es que el schema lo acepte.

---

### D3 — Endpoint de finalización: `PATCH /sessions/{id}/finalizar`

No existe hoy. Se necesita para setear `finalizada_en = now()` en la sesión.

**Shape**:
```
PATCH /proctoring/sessions/{session_id}/finalizar
→ 200: { "id": "...", "finalizada_en": "..." }
→ 404: sesión no encontrada
```

Sin body (la finalización no requiere datos adicionales). Idempotente: si `finalizada_en` ya está seteado, responde 200 sin modificar.

---

### D4 — `Cierre.tsx` lee conteos del backend

Hoy lee `anomaliasVivo` del store Zustand (que nunca se puebla porque `handleEvent` no llama `pushAnomalia()`). Dos opciones:
- **Opción A (elegida)**: `Cierre.tsx` hace `GET /proctoring/sessions/{id}` al montar para obtener `total_eventos`, `score` y `biometria` del backend — fuente de verdad real.
- **Opción B descartada**: llamar `pushAnomalia()` en `handleEvent`. Implica mantener sincronizado el store con el backend, duplicando estado.

**Decisión**: Opción A. El `proctoringSessionId` del store permite hacer el GET. Si el GET falla (red), mostrar "—" para no bloquear la pantalla. El `scorePropio` del store sigue siendo la estimación local del score para mostrar en tiempo real durante el examen; `Cierre.tsx` reemplaza ese valor con el del backend al cargar.

---

### D5 — Error logging en handleEvent

El catch silencioso (`} catch { }`) dificulta el diagnóstico en prod. Cambio mínimo: `console.error('[proctoring] POST evento falló:', err)` sin alterar el comportamiento de resiliencia (el buffer sigue reteniendo el evento para drain).

## Risks / Trade-offs

- **[Riesgo] Sesión huérfana**: si el alumno abandona el flujo después de la creación anticipada de la sesión pero antes del examen, queda una sesión sin eventos en la DB. Mitigación: `listar_sesiones` filtra o muestra las sesiones vacías — son visibles para el revisor. No es un problema crítico para el MVP.
- **[Riesgo] Race condition en Cierre.tsx**: el GET puede no encontrar la sesión si la finalización PATCH aún no comprometió. Mitigación: el PATCH se llama primero, luego el GET — el orden garantiza que la sesión existe.
- **[Riesgo] `screenshot_sha256_cliente` sin columna en DB**: si la columna no existe en `ProctoringEventModel`, el campo se acepta en el schema pero no se persiste. Acepta el campo → no hay 422 → los eventos sí se persisten. El hash del cliente se pierde para comparación, pero la cadena de custodia del servidor sigue intacta. Mitigación documentada en D2.
- **[Trade-off] Creación anticipada vs. sesión por examen**: crear la sesión en `ExamenLayout` significa que múltiples renders del layout no deben crear múltiples sesiones. Se protege con una condición `if (!proctoringSessionId)` antes de llamar `api.crearSesionProctoring`.

## Migration Plan

1. Backend: agregar `screenshot_sha256_cliente` a `IngestEventoIn` + `finalizar_sesion` en repo + endpoint PATCH + respuesta schema.
2. Frontend: actualizar `api.ts` (agregar `finalizarSesionProctoring`) + mover creación de sesión a `ExamenLayout` + `Cierre.tsx` usa GET + log en catch de handleEvent.
3. Tests: test del endpoint finalizar + test del campo `screenshot_sha256_cliente` aceptado.
4. Deploy: sin migraciones. El change es backward-compatible con la DB existente.

## Open Questions

- ¿`ProctoringEventModel` tiene columna `screenshot_sha256_cliente`? Verificar en `backend/app/infrastructure/persistence/models/proctoring.py`. Si no existe, el implementador debe decidir: ignorar el campo en el servicio (sin migración) o agregar migración.
- ¿El `ExamenLayout` existe como componente o es un wrapper en el router? Verificar `frontend/src/` para encontrar el punto de entrada del flujo del alumno.
