## Context

El flujo de enrollment del alumno (`StudentProfile.tsx`) captura la foto de perfil y el embedding biométrico de referencia (128-d, calculado client-side con face-api/MediaPipe), pero los persiste únicamente en el store Zustand y en `localStorage` (`activeexam_bio_ref`). En modo demo, `api.guardarFotoPerfil` y `api.guardarReferenciaBiometrica` son in-memory: **ningún artefacto biométrico llega al backend**.

Con c-55 mergeado, los usuarios ya existen en la tabla `usuario` (rama slim, revisión 0006). El backend ya tiene:
- Re-inferencia server-side: `mediapipe_adapter.py`, `ReinferenceVisionEngine`.
- Verificación 1:1 (examen): `VerifyIdentityService`, `comparar_identidad` (distancia coseno), router `/biometrics/verify`.
- Presigned URLs: `storage.presign` / `presign_service`.

Lo que **falta** es la persistencia de los artefactos de enrollment: foto de perfil en storage y embedding de referencia en la base de datos, cifrado at-rest.

**Constraints técnicos del proyecto:**
- Pydantic `model_config = ConfigDict(extra='forbid')` en todos los schemas.
- Migraciones Alembic en dos pasos (expand/contract). Rama slim activa, última revisión: 0006 (c-55). La nueva migración cuelga de 0006; declara `depends_on` con 0002 (que crea `usuario`) — patrón establecido por 0006.
- Tests sin mocks de DB (testcontainers / DB efímera).
- Embedding = dato sensible por defecto (Ley 25.326, IN-04, `13_legal_y_cumplimiento_argentina.md`): cifrado at-rest, finalidad acotada, eliminación al egreso.
- Cliente = sensor no confiable (RN-GLB-01): el backend no debe confiar en el embedding calculado client-side para la verificación (eso lo maneja C-09/re-inferencia). Este change persiste el embedding de enrollment para que C-09 lo pueda leer y comparar; la re-inferencia durante el examen ya está en otro módulo.
- La foto de perfil es **mutable/renovable** (no evidencia inmutable): bucket no-WORM, separado del bucket de evidencia (WORM, Compliance mode).

**Stakeholders**: alumno (se enrolla), backend C-09 (consume embedding de referencia), DPO (audita el tratamiento), equipo de retención C-19 (ejecutará la eliminación al egreso).

## Goals / Non-Goals

**Goals:**
- Endpoint `POST /api/v1/enrollment/foto-perfil`: subida de foto de perfil al bucket no-WORM de MinIO/S3; persistencia de metadatos en `foto_referencia` (DB).
- Endpoint `POST /api/v1/enrollment/embedding-referencia`: recibe embedding 128-d, lo cifra at-rest con clave maestra (Fernet/AES-256-GCM), persiste en `embedding_referencia` (DB) con metadatos de vigencia y retención.
- Migración Alembic 0007 en dos pasos: crear `foto_referencia` y `embedding_referencia`.
- Frontend: `StudentProfile.tsx` y `EnrollmentBiometricStep.tsx` llaman a los nuevos endpoints reales; el store persiste el `referencia_id` (opaco) en lugar del embedding crudo.
- Cifrado at-rest del embedding: el backend descifra en memoria solo cuando lo necesita (para la comparación 1:1 de C-09).
- Campos de retención en schema: `fecha_captura`, `fecha_expiracion`, `vigente`, `eliminado_en` — stub de retención (ejecución en C-19).

**Non-Goals:**
- NO implementar la verificación 1:1 durante el examen (ya existe en C-09).
- NO implementar la re-inferencia del embedding de enrollment server-side — la KB (C-09 D2) establece que la captura de referencia se computa client-side con face-api y el backend la persiste cifrada; la re-inferencia aplica durante el examen. Ver Open Questions para la tensión documentada.
- NO implementar la ejecución de la política de retención/eliminación al egreso (eso es C-19).
- NO implementar la gestión de usuarios (página de admin, alta masiva) — es change futuro.
- NO duplicar ni modificar el bucket de evidencia WORM existente.
- NO cambiar el flujo de consentimiento (ya capturado en enrollment, C-08).

## Decisions

### D1 — Foto de perfil: storage no-WORM + referencia en DB

**Decisión**: la foto de perfil se sube a un bucket MinIO/S3 **separado del bucket de evidencia** (no-WORM, no Object Lock), con cifrado at-rest del lado del servidor (SSE-S3 o SSE-KMS según la configuración MinIO). La tabla `foto_referencia` persiste solo los metadatos (URI del objeto, hash SHA-256 del contenido, `usuario_id`, timestamps).

**Por qué**: la foto de perfil es mutable (el alumno puede renovarla antes de un examen) — Object Lock / Compliance mode sería inadecuado. Separarla del bucket de evidencia evita mezclar datos de finalidad distinta (un artefacto de identidad previa vs. evidencia de examen con cadena de custodia completa). El hash SHA-256 del contenido permite verificar integridad sin requerir Object Lock.

**Alternativa considerada**: guardar la foto en la DB (BLOB/bytea). Descartada: aumenta significativamente el tamaño de la DB, complica backups, no escala.

---

### D2 — Embedding cifrado at-rest con Fernet (clave maestra del backend)

**Decisión**: el embedding 128-d se serializa como JSON (`[float, ...]`), se cifra con **Fernet** (`cryptography` package, AES-128-CBC + HMAC-SHA256) usando una clave maestra rotable (`EMBEDDING_ENCRYPTION_KEY`, 32 bytes en base64-urlsafe, inyectada desde Vault / env var). El ciphertext se almacena en la columna `embedding_cifrado` (TEXT) de la tabla `embedding_referencia`.

**Por qué**: Fernet provee cifrado autenticado (integridad + confidencialidad) con una API simple y sin necesidad de gestionar IV por separado. La clave maestra rotable permite reencriptar todos los embeddings ante un compromiso. Es coherente con la recomendación de "cifrado at-rest" para dato sensible (IN-04, Ley 25.326).

**Alternativa considerada**: AES-256-GCM directo (más control, más código, mayor riesgo de error en la gestión del nonce). Fernet es suficiente para MVP y reduce la superficie de error.

**Alternativa considerada**: cifrado a nivel de columna con pgcrypto (PGP_SYM_ENCRYPT). Descartada: requiere gestionar la clave dentro de SQL, complica las queries y la rotación.

---

### D3 — El endpoint recibe el embedding client-side; NO re-infiere en enrollment

**Decisión**: `POST /api/v1/enrollment/embedding-referencia` recibe el embedding 128-d calculado por el cliente (face-api / MediaPipe). El backend **no re-infiere** el embedding a partir de la foto en el momento del enrollment; confía en que el consentimiento + liveness ya fueron validados client-side en ese paso.

**Tensión documentada (Open Question OQ-1)**: esto parece contradecir RN-GLB-01 ("cliente = sensor no confiable"). La resolución es que **la re-inferencia aplica durante el EXAMEN** (C-09 D2), no durante el enrollment. El enrollment es un proceso supervisado donde el alumno captura una foto de referencia con instrucciones claras, y el consentimiento fue registrado en C-08. La referencia de enrollment no se usa para habilitar el examen directamente — C-09 re-infiere server-side sobre el clip del examen y compara contra esta referencia. Si la referencia es de mala calidad (foto adulterada), eso produce falso no-match en C-09, que escala a un proctor humano. El sistema no sanciona automáticamente (L2.5).

**Alternativa considerada**: re-inferir el embedding server-side a partir de la foto de perfil en el momento del enrollment. Esta es una mejora de seguridad válida para una fase posterior (Fase 2), pero requiere que el backend tenga un modelo de embedding equivalente al del cliente (face-api → MediaPipe → mismo espacio vectorial). Agregar esta complejidad en el MVP, cuando ya hay re-inferencia en C-09 como red de seguridad, es sobrediseño. Se documenta como mejora futura.

---

### D4 — Modelo de datos: dos tablas separadas (`foto_referencia`, `embedding_referencia`)

**Decisión**: dos tablas en lugar de una sola tabla unificada. `foto_referencia` tiene ciclo de vida independiente (mutable, puede renovarse). `embedding_referencia` tiene su propio ciclo de vigencia y retención (con `fecha_expiracion` y `eliminado_en`). Ambas tienen FK a `usuario`.

```
foto_referencia
  id              UUID PK
  usuario_id      UUID FK → usuario(id) ON DELETE CASCADE
  uri_storage     TEXT NOT NULL         -- ruta/key en MinIO/S3
  hash_sha256     TEXT NOT NULL         -- integridad del objeto
  bucket          TEXT NOT NULL         -- nombre del bucket (no-WORM)
  vigente         BOOLEAN NOT NULL DEFAULT TRUE
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()

embedding_referencia
  id              UUID PK
  usuario_id      UUID FK → usuario(id) ON DELETE CASCADE
  embedding_cifrado TEXT NOT NULL       -- Fernet ciphertext
  algoritmo       TEXT NOT NULL DEFAULT 'face-api-128d'  -- trazabilidad
  fecha_captura   TIMESTAMPTZ NOT NULL DEFAULT now()
  fecha_expiracion TIMESTAMPTZ          -- NULL = no expira aún
  vigente         BOOLEAN NOT NULL DEFAULT TRUE
  eliminado_en    TIMESTAMPTZ           -- NULL = no eliminado
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

**Por qué separadas**: permite renovar la foto sin invalidar el embedding (o viceversa), modelar la retención de forma diferenciada y mantener la trazabilidad del algoritmo usado.

---

### D5 — Migración Alembic 0007 en DOS PASOS; rama slim; `depends_on` con 0002

**Decisión**: la migración 0007 cuelga de 0006 (c-55, última de la rama slim). Dado que `foto_referencia` y `embedding_referencia` tienen FK a `usuario`, que fue creada en 0002 (rama principal), se declara `depends_on = ['0002']` en el encabezado de Alembic — mismo patrón que usó 0006.

**Dos pasos**:
- Paso 1 (esta migración, no destructivo): `CREATE TABLE foto_referencia`, `CREATE TABLE embedding_referencia` con todas las columnas en su estado final inicial (columnas nuevas, sin cambio destructivo sobre tablas existentes). No hay `NOT NULL` sobre columnas existentes.
- Paso 2: no aplica en este change (las tablas son nuevas). Si en el futuro se agrega una restricción `NOT NULL` sobre datos existentes, se haría en un segundo paso separado.

---

### D6 — Frontend: el store persiste `referencia_id`, no el embedding crudo

**Decisión**: tras el enrollment exitoso, el frontend recibe un `referencia_id` (UUID opaco) del backend y lo persiste en el store Zustand. El embedding crudo 128-d NO se persiste en localStorage. El store elimina el campo `activeexam_bio_ref` del localStorage (o lo deja vacío).

**Por qué**: el embedding en localStorage es un riesgo de privacidad innecesario una vez que está persistido en el backend. El `referencia_id` es suficiente para que C-09 sepa qué referencia usar en la verificación.

---

### D7 — Bucket de foto de perfil separado del bucket de evidencia

**Decisión**: usar un bucket dedicado (e.g., `activeexam-perfil`) con cifrado at-rest SSE-S3 pero **sin Object Lock** (WORM). El bucket de evidencia (`activeexam-evidencia`) conserva Object Lock / Compliance mode intacto.

**Por qué**: mezclar artefactos de finalidad distinta en el mismo bucket (con Object Lock) impediría renovar o eliminar la foto de perfil al egreso, violando el derecho de supresión (Ley 25.326).

## Risks / Trade-offs

- **[Riesgo] Embedding client-side no re-inferido en enrollment** → El backend confía en el vector calculado por el cliente. Un cliente parcheado podría enviar un embedding arbitrario en el enrollment, que luego no matchea con nadie. Mitigación: C-09 re-infiere server-side durante el examen y compara contra esta referencia; un embedding adulterado produce no-match y escala a proctor humano (L2.5). El sistema no sanciona automáticamente. Riesgo residual documentado en OQ-1.

- **[Riesgo] Clave de cifrado `EMBEDDING_ENCRYPTION_KEY` filtrada** → Todos los embeddings almacenados serían descifrables. Mitigación: clave inyectada desde Vault / tmpfs efímero (nunca en código ni imagen Docker); rotación de clave como runbook operacional. Riesgo residual aceptado y documentado.

- **[Trade-off] Fernet (AES-128) vs AES-256-GCM** → Fernet usa AES-128, no AES-256. Para datos biométricos en Argentina, AES-128 es suficiente (no hay requisito normativo explícito de 256). La simplicidad de Fernet reduce la superficie de error en la gestión del IV/nonce. Revisable en Fase 2 si el DPIA lo exige.

- **[Riesgo] Foto de perfil en storage no-WORM** → Un actor con acceso al storage podría reemplazar la foto. Mitigación: el hash SHA-256 almacenado en DB permite detectar la alteración; el acceso al bucket está restringido por IAM (solo el backend escribe/lee). La foto de perfil no es evidencia inmutable; la inmutabilidad de la evidencia de examen sigue en el bucket WORM separado.

- **[Trade-off] Sin re-inferencia del embedding en enrollment (MVP)** → Es una debilidad de seguridad consciente, documentada y mitigada por C-09. La mejora (re-inferencia server-side en enrollment) es factible en Fase 2 cuando el backend tenga el modelo de embedding equivalente.

## Migration Plan

1. **Backend — Migración 0007**: crear `foto_referencia` y `embedding_referencia` (Paso 1, no destructivo). Deployable sin downtime.
2. **Backend — Servicio de cifrado**: implementar `EmbeddingEncryptionService` (Fernet) con clave desde env var `EMBEDDING_ENCRYPTION_KEY`.
3. **Backend — Endpoints de enrollment**: implementar `POST /api/v1/enrollment/foto-perfil` y `POST /api/v1/enrollment/embedding-referencia` con sus schemas Pydantic (`extra='forbid'`), application services y repositorios.
4. **Backend — Bucket de perfil**: configurar bucket `activeexam-perfil` en MinIO/S3 (sin Object Lock, con SSE-S3).
5. **Frontend — api.ts**: reemplazar las implementaciones in-memory de `guardarFotoPerfil` y `guardarReferenciaBiometrica` con llamadas HTTP reales a los nuevos endpoints.
6. **Frontend — store.ts**: eliminar el guardado del embedding crudo en localStorage; persistir `referencia_id`.
7. **Frontend — EnrollmentBiometricStep.tsx y StudentProfile.tsx**: adaptar para consumir el `referencia_id` de retorno.
8. **Tests**: tests de integración con DB efímera / testcontainers — endpoint foto (upload, persistencia metadatos), endpoint embedding (cifrado, persistencia, descifrado correcto), migración (upgrade/downgrade), servicio de cifrado (round-trip).
9. **Rollback**: las tablas nuevas son aditivas; hacer downgrade de la migración 0007 restaura el estado anterior sin afectar datos existentes. En el frontend, revertir `api.ts` al comportamiento in-memory.

## Open Questions

**OQ-1 — Tensión con RN-GLB-01 en enrollment vs examen**: la regla "cliente = sensor no confiable" se aplica con re-inferencia server-side en C-09 (durante el examen). En este change (enrollment), el backend persiste el embedding client-side SIN re-inferirlo. ¿El DPIA requiere que el embedding de referencia también sea re-inferido server-side? Decisión: documentar el gap, aceptar para MVP (la red de seguridad es C-09), evaluar en Fase 2. **No resolver inventando — requiere validación del DPO.**

**OQ-2 — Foto de referencia institucional vs foto de enrollment**: la KB menciona "foto institucional de referencia por estudiante (prerrequisito gestionado por la institución vía proceso de registro previo)". ¿La foto capturada en enrollment reemplaza o complementa la foto institucional? Este change asume que la foto capturada en enrollment IS la foto de referencia (no hay foto institucional previa en el sistema). Si la institución provee una foto institucional separada, el diseño de la tabla `foto_referencia` soporta múltiples registros por `usuario_id` (con campo `vigente`), pero el flujo de ingestión de la foto institucional es fuera del scope de este change.

**OQ-3 — Expiración del embedding**: ¿cada cuánto tiempo expira el embedding de referencia y se requiere re-enrollment? La KB no lo especifica. El campo `fecha_expiracion` es nullable (no expira por defecto). La política concreta de expiración es decisión del Acuerdo de Nivel de Proctoring (C-01) y se configura en Fase 2.
