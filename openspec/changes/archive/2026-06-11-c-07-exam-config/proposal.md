# Proposal — C-07 `exam-config`

> **Naturaleza del change**: primer change de dominio del ciclo pre-monitoreo (FASE 1, governance **MEDIO**). Produce los endpoints de administración que **configuran un examen antes de que cualquier estudiante lo inicie**. Es el prerrequisito de todo el flujo de examen: sin un examen configurado, con estudiantes habilitados y foto de referencia cargada, ni el consentimiento (C-08) ni la verificación biométrica 1:1 (C-09) tienen contra qué operar.

## Why

El ciclo de vida del examen (Flujo 0) arranca con **[PRE-EXAMEN] Admin configura examen → asigna estudiantes → carga foto institucional → define parámetros**. Hoy no existe ningún mecanismo para crear esa configuración. Toda la cadena downstream depende de datos que este change produce:

- **C-09 (biometría 1:1)** compara el rostro del estudiante contra una **foto institucional de referencia** que alguien tuvo que cargar o marcar como precomputada. Sin ese prerrequisito (SU-01), la verificación 1:1 **no opera** (Flujo 2, caso de error: "Sin foto institucional de referencia → la verificación 1:1 no opera").
- **RN-EX-03** exige que **solo los estudiantes habilitados/asignados** puedan iniciar la sesión. Ese gate de habilitación se define aquí.
- El **umbral de score**, los **detectores activos y sus umbrales** y la **política de retención** son parámetros por-examen que el scoring (C-13), el motor de visión (C-11) y la retención (C-19) consumen. Si no se configuran por examen, esos changes no tienen su parámetro de entrada.
- **Operaciones** (RN-EX-02) necesita la **calendarización con anticipación** para saber cuándo el sistema estará bajo SLA estricto (el pico multi-examen del NFR de 1.000 sostenido / ~2.100 pico se planifica desde aquí).

La configuración es **admin-only** (RBAC contextual, MFA — RN-AU-05, RN-AU-07): es una superficie de administración sensible que define qué se monitorea y de quién. Construirla sin enforcement de rol sería una falla de control de acceso desde la raíz del ciclo.

## What Changes

Este change agrega la capacidad de **administrar la configuración de un examen** sobre las entidades ya modeladas en C-05 (`Examen`, `Asignación` proctor↔examen) y la autorización de C-06 (RBAC contextual, MFA, JWT). No introduce entidades nuevas ni cambia el modelo de datos; **usa** el modelo existente.

- **CRUD de `Examen`** (admin de exámenes): nombre, ventana temporal (inicio/fin), `umbral_de_score`, política de retención, **detectores activos + sus umbrales** (RN-EX-01). Validación de parámetros (ventana temporal coherente, umbral en rango, detectores conocidos).
- **Asignación de estudiantes habilitados**: gestionar la lista de estudiantes que pueden iniciar el examen; **solo ellos** lo inician (RN-EX-03). Listado de habilitados consultable.
- **Asignación proctor↔examen**: vincular proctores a un examen (entidad `Asignación`), que C-06 consume para el permiso contextual "un proctor observa solo exámenes asignados" (RN-AU-07).
- **Carga de la foto institucional de referencia** (o marcado como **precomputada**): prerrequisito de la verificación 1:1 de C-09 (SU-01). El binario se trata como dato sensible (alimenta un embedding biométrico); se sube por la misma vía de storage por URL firmada que el resto de evidencia (no pasa por el backend), o se marca el examen/estudiante como "referencia precomputada" si la institución ya tiene el embedding.
- **Calendarización visible para operaciones** (RN-EX-02): la ventana temporal y el cupo de estudiantes habilitados quedan consultables con anticipación.

**Enforcement de acceso**: todos los endpoints son **admin-only** con MFA (RN-AU-05); un rol no-admin recibe 403. Se apoya en el RBAC contextual de C-06 (no lo reimplementa).

## Capabilities

> Las capabilities modelan el comportamiento de configuración pre-examen. Cada requisito SHALL es verificable por un test de API (CRUD, RBAC, validación, listado).

### New Capabilities

- `exam-configuration`: CRUD de `Examen` con sus parámetros de monitoreo (nombre, ventana temporal, umbral de score, política de retención, detectores activos + umbrales), validación de parámetros y calendarización visible para operaciones.
- `student-enablement`: gestión de la lista de estudiantes habilitados por examen — solo los habilitados pueden iniciar (RN-EX-03) — y consulta del listado.
- `proctor-assignment`: asignación proctor↔examen (entidad `Asignación`) que habilita el permiso contextual de C-06.
- `reference-photo-management`: carga de la foto institucional de referencia por estudiante/examen, o marcado como referencia precomputada — prerrequisito de la verificación 1:1 (SU-01).
- `exam-config-access-control`: enforcement admin-only + MFA sobre toda la superficie de configuración (RN-AU-05, RN-AU-07).

### Modified Capabilities

<!-- Ninguna. Este change no modifica specs de dominio previas (C-01/C-02/C-03 son governance/PoC y no dejan specs de dominio en openspec/specs/). -->

(Ninguna — no existen specs de dominio previas en `openspec/specs/` que este change modifique.)

## Impact

- **Bloquea**: C-08 (consentimiento — necesita un examen configurado contra el cual consentir) y, por transitividad, C-09 (biometría — necesita la foto de referencia que este change carga).
- **Dependencias entrantes**: `C-06` (auth-rbac-keycloak — provee el RBAC contextual, MFA y validación de JWT sobre los que se apoya el enforcement admin-only). C-06 a su vez depende de C-05 (modelos) y C-04 (foundation).
- **Datos que produce** (consumidos downstream):
  - Foto/embedding de referencia → **C-09** (comparación 1:1).
  - Lista de estudiantes habilitados → gate de inicio de sesión (C-09/C-10).
  - Asignación proctor↔examen → permiso contextual del panel (C-15) y de la supervisión (C-06).
  - `umbral_de_score` → **C-13** (decisión de encolado a revisión).
  - Detectores activos + umbrales → **C-11** (reglas de transición configurables por institución).
  - Política de retención → **C-19** (retención automática + holds).
  - Ventana temporal / calendarización → planificación operativa del pico (NFR 1.000/~2.100).
- **Actores afectados**: administrador de exámenes (opera el CRUD), operaciones/coordinador (consume la calendarización), proctor (recibe asignación), estudiante (queda habilitado o no).
- **Privacidad por diseño**: la foto de referencia es un dato biométrico sensible por defecto (Ley 25.326, IN-04); se almacena cifrado at-rest y su finalidad queda acotada a la verificación de identidad (RN-CO-04). Este change **no** habilita su reutilización para ningún otro fin.
