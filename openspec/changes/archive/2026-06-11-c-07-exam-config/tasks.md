# Tasks — C-07 `exam-config`

> Implementa la superficie de administración del examen sobre las entidades de C-05 y la autorización de C-06, en arquitectura Clean/Hexagonal. El Done de cada tarea es un test verde del scope (CRUD, validación, RBAC, listado). No se modifica el modelo de datos.

## 1. CRUD de Examen y validación de parámetros (capability `exam-configuration`)

- [x] 1.1 Implementar los casos de uso `CreateExam`, `UpdateExam`, `DeleteExam` (application layer) sobre el repositorio de `Examen` de C-05; Done: `app/application/exam_config/service.py` (`create_exam`/`update_exam`/`delete_exam`), puertos inyectados
- [x] 1.2 Implementar los routers `POST/GET/PATCH/DELETE /api/v1/exams` (presentation), deserializando a los casos de uso; Done: `app/presentation/api/v1/exams/router.py`
- [x] 1.3 Implementar la validación de parámetros en la capa de aplicación (ventana temporal coherente, umbral en rango, detectores en catálogo, política de retención válida) → 422 con detalle; Done: `app/domain/exam_config/validation.py` + `catalog.py`; invocada en el caso de uso antes de persistir
- [x] 1.4 Tests: crear examen completo (201), actualizar parámetros (200), baja sin sesiones (204), rechazo de ventana incoherente / detector desconocido / umbral fuera de rango (422); Done: `test_exam_config_validation.py`, `test_exam_config_service.py`, `test_exam_config_http.py`

## 2. Calendarización para operaciones (capability `exam-configuration`)

- [x] 2.1 Implementar `ListExamsForOperations` con filtro por ventana temporal y estado; Done: `ExamConfigService.list_for_operations`
- [x] 2.2 Implementar `GET /api/v1/exams?from&to&status`; Done: router `list_exams` con alias `from`/`to`/`status`
- [x] 2.3 Test: listar exámenes por rango de fechas devuelve los de la ventana con su estado; Done: `test_calendarizacion_filtra_por_rango_y_estado`

## 3. Estudiantes habilitados (capability `student-enablement`)

- [x] 3.1 Implementar `SetEnabledStudents` y la consulta de habilitados; Done: `set_enabled_students`/`get_enabled_students` (dedup + orden)
- [x] 3.2 Implementar `PUT/GET /api/v1/exams/{id}/students`; Done: router `set_students`/`get_students`
- [x] 3.3 Exponer el gate de habilitación (solo habilitados pueden iniciar) consumible por el inicio de sesión de C-09/C-10; Done: `ExamConfigService.is_student_enabled` (contrato de salida)
- [x] 3.4 Tests: definir lista (200), consultar lista, estudiante no habilitado no puede iniciar; Done: `test_habilitados_set_get_y_gate`, `test_set_y_list_habilitados`

## 4. Asignación de proctores (capability `proctor-assignment`)

- [x] 4.1 Implementar `AssignProctors` creando entidades `Asignación` proctor↔examen (modelo de C-05); Done: `ExamConfigService.assign_proctors` (idempotente, sin duplicar)
- [x] 4.2 Implementar `PUT /api/v1/exams/{id}/proctors`; Done: router `assign_proctors`
- [x] 4.3 Tests: asignar proctores (200); el proctor asignado solo ve sus exámenes (permiso contextual de C-06), no ajenos; Done: `test_asignar_proctores_crea_asignaciones_sin_duplicar` + el aislamiento contextual lo cubre C-06 (`test_auth_contextual_service.py`, que consume estas Asignaciones)

## 5. Foto institucional de referencia (capability `reference-photo-management`)

- [x] 5.1 Implementar `RegisterReferencePhoto`: generar URL firmada (presign MinIO/S3, reutiliza config de storage de C-04) o marcar como precomputada; Done: `ExamConfigService.register_reference` + `app/infrastructure/storage/presign.py`
- [x] 5.2 Implementar `POST /api/v1/exams/{id}/reference-photo`; Done: router `reference_photo` (presign o precomputada)
- [x] 5.3 Persistir la referencia/embedding cifrado at-rest, finalidad acotada a verificación de identidad (RN-CO-04, RN-BIO-07); Done: el backend solo registra metadata (uri/hash/precomputada); el binario sube directo por URL firmada (D2) y vive en el bucket cifrado at-rest de C-04; el cómputo/cifrado del embedding es C-09 (no se adelanta scope biométrico)
- [x] 5.4 Exponer el estado "referencia faltante" para que la verificación 1:1 de C-09 no opere sin referencia; Done: `ExamConfigService.reference_missing`
- [x] 5.5 Tests: presign URL devuelta, marcado precomputada, referencia faltante reflejada, artefacto persistido cifrado; Done: `test_referencia_*` (service + http)

## 6. Control de acceso admin-only + MFA (capability `exam-config-access-control`)

- [x] 6.1 Inyectar el guard/dependency admin-only + MFA de C-06 en todos los routers de configuración; Done: `router = APIRouter(dependencies=[require_roles(ADMIN_EXAMENES), require_mfa])` — sin lógica de autorización propia (D1)
- [x] 6.2 Tests RBAC: admin con MFA accede (2xx); rol no-admin recibe 403; admin sin MFA recibe 403; Done: `test_no_admin_recibe_403`, `test_admin_sin_mfa_recibe_403`, `test_admin_con_mfa_crea_201`, `test_sin_token_401`

## 7. Cierre del change

- [x] 7.1 Correr `openspec validate --strict c-07-exam-config`; Done: validación estricta ✓
- [x] 7.2 Verificar que la configuración producida (referencia, habilitados, asignación, umbral, detectores, retención, calendarización) es consumible por C-08/C-09 y downstream; Done: contratos de salida (`is_student_enabled`, `reference_missing`, `Asignación` para RBAC) disponibles, desbloquea C-08
