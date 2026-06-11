# Design — C-07 `exam-config`

> Design técnico de la superficie de administración del examen. Construye endpoints REST sobre las entidades de C-05 (`Examen`, `Asignación`) y la autorización de C-06, siguiendo la arquitectura Clean/Hexagonal del proyecto (domain / application / infrastructure / presentation). No introduce entidades nuevas: orquesta las existentes.

## Context

El proyecto Proctoring (React + FastAPI + PostgreSQL/TimescaleDB + Keycloak + MinIO/S3, Clean/Hexagonal) llega a C-07 con las fundaciones listas: foundation-setup (C-04), core-models (C-05) y auth-rbac-keycloak (C-06). Las entidades `Examen`, `Asignación` proctor↔examen, `Usuario` y `Embedding` ya existen como modelos transaccionales; el RBAC contextual, MFA y la validación de JWT ya están operativos.

C-07 es la **puerta de entrada del ciclo de vida del examen** (Flujo 0, paso [PRE-EXAMEN]). Su salida configura todo lo downstream: la foto de referencia que C-09 compara 1:1, la lista de habilitados que gatea el inicio, el umbral de score que C-13 usa para encolar a revisión, los detectores activos que C-11 traduce a reglas de transición, la política de retención que C-19 aplica, y la calendarización que operaciones planifica contra el pico (NFR 1.000 sostenido / ~2.100 pico).

**Constraints**:
- **Admin-only + MFA**: toda la superficie es de administración sensible (RN-AU-05). El enforcement se delega a C-06; este change lo **exige y verifica**, no lo reimplementa.
- **No reabrir el modelo de datos**: C-05 ya definió `Examen` y `Asignación`. C-07 usa esos puertos/repositorios; si falta un atributo, es un hallazgo para C-05, no un modelo nuevo aquí.
- **La foto de referencia es dato biométrico sensible** (Ley 25.326, IN-04): cifrada at-rest, finalidad acotada (RN-CO-04), subida directa al storage por URL firmada (no pasa por el backend, RN-CC-04), nunca reutilizable.
- **Validación estricta de parámetros**: ventana temporal coherente (fin > inicio), umbral de score en rango, detectores activos restringidos al catálogo conocido, política de retención válida.

**Stakeholders**: administrador de exámenes (opera), operaciones/coordinador (planifica), equipo de C-08/C-09 (consumen la configuración).

## Goals / Non-Goals

**Goals:**
- CRUD completo de `Examen` con validación de parámetros (US-001 CA-1, CA-2).
- Gestión de la lista de estudiantes habilitados; solo ellos inician (CA-3, RN-EX-03).
- Asignación proctor↔examen que C-06 consume para el permiso contextual.
- Carga de la foto institucional de referencia o marcado como precomputada (CA-4, SU-01).
- Calendarización consultable con anticipación para operaciones (CA-5, RN-EX-02).
- Enforcement admin-only + MFA verificado por test (RBAC).

**Non-Goals:**
- NO implementar el inicio de sesión ni la verificación biométrica (C-09): aquí solo se **habilita** quién puede iniciar y se **carga** la referencia.
- NO definir las reglas de transición de los detectores (C-11): aquí solo se persisten **qué detectores están activos y sus umbrales**.
- NO calcular score (C-13) ni aplicar retención (C-19): aquí solo se **configuran** el umbral y la política.
- NO reimplementar RBAC/MFA/JWT (C-06): se consumen.
- NO modificar el modelo de datos (C-05).

## Decisions

### D1 — Apoyarse en el RBAC contextual de C-06, no reimplementarlo
**Decisión**: cada endpoint declara el rol requerido (`admin de exámenes`) y exige MFA mediante el guard/dependency de C-06; un rol no-admin recibe 403 sin lógica de autorización propia en C-07.
**Por qué**: la autorización es una capability transversal que ya vive en C-06 (DD-09). Duplicarla en C-07 fragmentaría la política de acceso y crearía drift. Single source of truth de autorización.
**Alternativa considerada**: checks de rol ad-hoc por endpoint → drift de política, difícil de auditar.

### D2 — La foto de referencia sube directo al storage por URL firmada; el backend solo registra metadata
**Decisión**: el binario de la foto institucional se sube directo a MinIO/S3 mediante URL firmada (presigned), igual que toda evidencia (RN-CC-04). El backend persiste solo la referencia (uri_bucket, hash) y, donde aplique, dispara el cómputo del embedding cifrado. Alternativamente, el examen/estudiante se marca como **referencia precomputada** si la institución ya provee el embedding.
**Por qué**: minimiza la superficie del backend ante binarios, evita cuello de botella, y mantiene el binario biométrico bajo la misma cadena de custodia y cifrado at-rest que el resto. El cliente es sensor no confiable (RN-GLB-01): el backend valida el hash, no confía en el upload.
**Alternativa considerada**: subida multipart al backend → cuello de botella + binario sensible transitando el backend sin necesidad.

### D3 — Estados explícitos del examen para que operaciones planifique la ventana
**Decisión**: el examen tiene una ventana temporal (inicio/fin) y una calendarización consultable; un examen no puede iniciarse fuera de su ventana. La calendarización se expone a operaciones con anticipación (endpoint de listado por fecha/estado).
**Por qué**: RN-EX-02 — operaciones necesita saber cuándo el sistema estará bajo SLA estricto para dimensionar el pico (SU-06). Sin ventana explícita, el inicio de sesión no tiene gate temporal.
**Alternativa considerada**: examen siempre abierto → no hay forma de planificar capacidad ni de cerrar el inicio.

### D4 — Validación de parámetros en la capa de aplicación, no en la presentación
**Decisión**: la coherencia de ventana temporal, rango del umbral de score, catálogo de detectores conocidos y validez de la política de retención se valida en el caso de uso (application layer), devolviendo 422 con detalle; la presentación solo deserializa.
**Por qué**: las reglas de negocio (RN-EX-01) viven en el dominio/aplicación en Clean/Hexagonal; validarlas solo en el schema de FastAPI las acoplaría a la presentación y las haría inconsistentes ante otra interfaz.
**Alternativa considerada**: validación solo en Pydantic → reglas de negocio atrapadas en la capa de presentación.

## Arquitectura (capas Clean/Hexagonal)

```
presentation/ (FastAPI routers — admin-only, MFA via guard de C-06)
   POST   /api/v1/exams                      crear examen
   GET    /api/v1/exams           ?from&to&status  listar / calendarización
   GET    /api/v1/exams/{id}                 detalle
   PATCH  /api/v1/exams/{id}                 actualizar parámetros
   DELETE /api/v1/exams/{id}                 baja (si no inició)
   PUT    /api/v1/exams/{id}/students        set lista de habilitados
   GET    /api/v1/exams/{id}/students        listar habilitados
   PUT    /api/v1/exams/{id}/proctors        asignar proctores (Asignación)
   POST   /api/v1/exams/{id}/reference-photo presign URL o marcar precomputada
        │
        ▼
application/ (casos de uso — validación de parámetros, D4)
   CreateExam · UpdateExam · SetEnabledStudents · AssignProctors ·
   RegisterReferencePhoto · ListExamsForOperations
        │
        ▼
domain/ (entidades de C-05: Examen, Asignación; reglas RN-EX)
        │
        ▼
infrastructure/ (repositorios de C-05; storage presign de MinIO/S3; cifrado at-rest)
```

> Autorización (admin-only + MFA) inyectada como dependency desde C-06 en cada router. Validación de parámetros (D4) en los casos de uso.

## Mapa de requisitos → reglas/criterios

| Capability | Regla / Criterio | Verificación |
|------------|------------------|--------------|
| `exam-configuration` | RN-EX-01, US-001 CA-1/CA-2 | CRUD + validación de parámetros (422 ante inválidos) |
| `student-enablement` | RN-EX-03, US-001 CA-3 | set/list de habilitados; solo habilitados pueden iniciar |
| `proctor-assignment` | RN-AU-07 | `Asignación` creada; C-06 la consume para permiso contextual |
| `reference-photo-management` | SU-01, US-001 CA-4 | presign URL o marcado precomputada; cifrado at-rest |
| `exam-config-access-control` | RN-AU-05, RN-AU-07 | admin recibe 200; no-admin recibe 403; sin MFA recibe 403 |
| `exam-configuration` (calendarización) | RN-EX-02, US-001 CA-5 | listado por fecha/estado visible para operaciones |

## Risks / Trade-offs

- **[Foto de referencia ausente al llegar a C-09]** → Mitigación: el examen no se considera listo para iniciar si exige verificación biométrica y no hay referencia cargada ni marcada como precomputada; el listado de operaciones expone ese estado.
- **[Binario biométrico subido al backend por error]** → Mitigación: D2 — subida directa por URL firmada; el backend solo registra metadata y valida hash (RN-GLB-01, RN-CC-04).
- **[Drift de autorización entre C-06 y C-07]** → Mitigación: D1 — C-07 no implementa autorización; consume el guard de C-06.
- **[Parámetros inválidos llegan a downstream (umbral fuera de rango, detector desconocido)]** → Mitigación: D4 — validación en el caso de uso, 422 con detalle, antes de persistir.
- **Trade-off aceptado**: C-07 no valida que la referencia sea una "foto limpia" (calidad biométrica); eso es responsabilidad del proceso de registro previo de la institución (dependencia externa, ver `12_biometria_y_liveness.md`).

## Migration Plan

1. Implementar casos de uso y routers sobre los repositorios de C-05; inyectar el guard admin-only+MFA de C-06.
2. Implementar el presign de la foto de referencia contra MinIO/S3 (reutiliza la config de storage de C-04) + marcado precomputada.
3. Tests: CRUD, validación de parámetros (422), RBAC admin-only (403 para no-admin y sin-MFA), set/list de habilitados, asignación de proctores, registro de referencia, calendarización.
4. **Criterio de salida**: `openspec validate --strict` ✓ y los tests del scope verdes → desbloquea C-08.

**Rollback**: al ser CRUD admin sobre entidades existentes, una baja de examen (sin sesiones iniciadas) es reversible; no hay migración destructiva de esquema (el esquema vive en C-05).

## Open Questions

- ¿La carga de la foto de referencia es por estudiante (1 por habilitado) o se asume siempre precomputada por la institución? → la KB la trata como prerrequisito gestionado por la institución (SU-01); C-07 soporta ambas vías (cargar o marcar precomputada).
- ¿Población menor de 18 con consentimiento parental diferenciado? → se decide en C-01 (gate legal); C-07 no lo bloquea pero la marca del examen puede reflejarlo si C-01 lo exige.
