## Why

Hoy la foto de perfil del alumno y el embedding biométrico de referencia (enrollment) no se persisten en el backend: quedan en `localStorage`, store Zustand o memoria, lo que imposibilita la verificación 1:1 real durante el examen. Con auth real operativa (c-55), los usuarios ya existen en la tabla `usuario`; el paso natural e imprescindible es cerrar este gap y persistir de verdad los artefactos biométricos de referencia en el backend, de forma segura y conforme a Ley 25.326.

## What Changes

- **Nuevo endpoint** `POST /api/v1/enrollment/foto-perfil` — recibe la captura del alumno (imagen), la sube al bucket **no-WORM** de MinIO/S3 (la foto de perfil es mutable/renovable, a diferencia de la evidencia de examen), y persiste la referencia en una nueva tabla `foto_referencia` ligada al `usuario_id` autenticado.
- **Nuevo endpoint** `POST /api/v1/enrollment/embedding-referencia` — recibe el embedding 128-d calculado client-side (face-api / MediaPipe), lo **cifra at-rest** con clave maestra del backend (Fernet/AES-256-GCM) antes de persistirlo en la tabla `embedding_referencia`, y devuelve un `referencia_id` opaco al cliente.
- **Modelo de datos**: dos nuevas tablas (`foto_referencia`, `embedding_referencia`) con migración Alembic en DOS PASOS, colgando de la rama slim (última revisión: 0006, c-55) y declarando `depends_on` con 0002 (que crea `usuario`).
- **Actualización del flujo de enrollment frontend** — `StudentProfile.tsx` y `EnrollmentBiometricStep.tsx` dejan de operar in-memory; llaman a los nuevos endpoints reales y persisten el `referencia_id` (no el embedding) en el store.
- **Límite de retención y eliminación al egreso** — campos `fecha_captura`, `fecha_expiracion`, flag `vigente`, y columna `eliminado_en` en `embedding_referencia`; política de eliminación documentada como stub de runbook (implementación de retención completa es C-19).

## Capabilities

### New Capabilities

- `enrollment-biometric-persistence`: Persistencia server-side de la foto de perfil y el embedding de referencia del alumno, incluyendo cifrado at-rest del embedding, subida de la foto a storage no-WORM, modelo de datos con metadatos de vigencia y retención, y endpoints de enrollment seguros.

### Modified Capabilities

- `student-profile-shell`: El orquestador de enrollment (`StudentProfile.tsx`) pasa de guardar en memoria/localStorage a consumir los nuevos endpoints reales. El flujo de fases no cambia; cambia el destino de persistencia.
- `exam-enrollment`: Las fases `foto_perfil` y `biometria` del enrollment pasan a tener persistencia real en el backend. Los contratos de las fases se mantienen; se agrega el `referencia_id` como dato de retorno.

## Impact

- **Backend**: nuevos módulos en `backend/app/domain/biometrics/`, `backend/app/application/enrollment/`, `backend/app/presentation/api/v1/enrollment/`; dos nuevas tablas; migración 0007; servicio de cifrado at-rest.
- **Frontend**: `frontend/src/screens/StudentProfile.tsx`, `frontend/src/screens/enrollment/EnrollmentBiometricStep.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/store.ts`.
- **Storage**: bucket de foto de perfil (no-WORM, mutable, cifrado at-rest) separado del bucket de evidencia (WORM, Compliance mode). Requiere política de bucket nueva en MinIO/S3.
- **Dependencias**: c-55 (auth real, tabla `usuario`) debe estar en main — ya lo está. c-09 (verificación 1:1) consume el embedding de referencia persistido; este change le da la referencia a consumir.
- **Legal**: embedding tratado como dato sensible (Ley 25.326, IN-04); consentimiento ya capturado en el flujo de enrollment; eliminación al egreso declarada en schema (ejecución en C-19).
