# Modelo de Datos

PostgreSQL opera con dos roles funcionales: **tablas transaccionales clásicas** para las entidades de dominio y la extensión **TimescaleDB** que convierte la tabla de eventos en una hypertable.

## Dominios

- **Identidad y acceso**: Usuario (provisionado just-in-time desde el IdP).
- **Configuración de examen**: Examen, Asignación proctor↔examen, Consentimiento.
- **Ciclo de vida de sesión**: Sesión (entidad central).
- **Biometría**: Embedding facial cifrado.
- **Telemetría**: Evento (series temporales / hypertable).
- **Evidencia y custodia**: Evidencia, Audit log, Caso disciplinario.

## ERD (Entity Relationship Diagram)

```
  ┌──────────┐        ┌──────────┐        ┌──────────────┐
  │ USUARIO  │1──────*│  SESIÓN  │*──────1│   EXAMEN     │
  │ id       │        │ id       │        │ id           │
  │ rol      │        │ user_id  │        │ nombre       │
  │ id_inst. │        │ exam_id  │        │ parámetros   │
  └────┬─────┘        │ estado   │        │ umbral_score │
       │              │ score    │        └──────┬───────┘
       │1             └────┬─────┘               │
       │                   │1                    │*
       │*             ┌────┴───────┐        ┌────┴────────┐
  ┌────┴──────┐       │  EVENTO    │        │ ASIGNACIÓN  │
  │ EMBEDDING │       │ (hypertable)│       │ proctor↔exam│
  │ (cifrado) │       │ session_id │        └─────────────┘
  └───────────┘       │ tipo·sev.  │
                      │ payload    │
                      └────┬───────┘
                           │1
                      ┌────┴───────┐        ┌──────────────┐
                      │ EVIDENCIA  │1──────*│ AUDIT_LOG    │
                      │ id·hashes  │        │ (append-only)│
                      │ firmas     │        │ hash_prev    │
                      │ uri_bucket │        └──────────────┘
                      └────┬───────┘
                           │1
                      ┌────┴────────┐
                      │ CASO_DISC.  │
                      │ estado·ref  │
                      └─────────────┘
```

Cardinalidades: Usuario 1—* Sesión; Examen 1—* Sesión; Usuario 1—* Embedding; Sesión 1—* Evento; Evento 1—* Evidencia; Evidencia 1—* Audit log; Evidencia 1—1 Caso disciplinario (cuando se deriva); Examen *—* Usuario(proctor) vía Asignación; Usuario 1—* Consentimiento.

## Entidades

### Usuario (transaccional, PostgreSQL)
- Atributos: `id`, identificador institucional, `rol(es)`, `email`, atributos federados.
- Relaciones: 1—* Sesión; 1—* Embedding; 1—* Consentimiento; *—* Examen (como proctor) vía Asignación.
- Notas: provisionado **just-in-time** desde el IdP (Keycloak/directorio institucional).

### Examen (transaccional)
- Atributos: `id`, `nombre`, parámetros de monitoreo, detectores activos, `umbral_de_score`, ventana temporal, política de retención.
- Relaciones: 1—* Sesión; *—* Proctor vía Asignación.
- Notas: configurado por el administrador de exámenes.

### Sesión (transaccional) — entidad central del ciclo de vida
- Atributos: `id`, `user_id`, `exam_id`, `estado` (iniciada / activa / finalizada / flaggeada / cerrada), `score`, clave de sesión (rotativa), timestamps.
- Relaciones: *—1 Usuario; *—1 Examen; 1—* Evento.
- Constraints: estado restringido al enum del ciclo de vida.

### Embedding (transaccional, dato biométrico)
- Atributos: `id`, `user_id`, vector **cifrado**, `versión`, `fecha`.
- Relaciones: *—1 Usuario.
- Constraints: cifrado at-rest; **eliminado al egreso del estudiante**.
- Notas: dato personal especialmente protegido (tratar como sensible por defecto — ver marco legal Argentina en `1A_legal_y_cumplimiento_argentina.md`).

### Evento (series temporales, TimescaleDB hypertable)
- Esquema: `id`, `session_id`, `exam_id` (denormalizado), `tipo`, `severidad`, `timestamp_cliente`, `timestamp_backend`, `payload` (JSON), `firma` (HMAC-SHA256 con clave de sesión), `schema_version`.
- Particionado: hypertable por día (chunks).
- Índices: `(session_id, timestamp)` y `(exam_id, timestamp)`.
- Compresión: chunks recientes (7 días) sin comprimir; 7 días–1 año comprimidos (~10×); >1 año exportados a Parquet en object storage y eliminados de la base activa.
- Continuous aggregates: eventos por sesión por minuto, score por sesión, sesiones activas por examen, distribución por tipo en la última hora.

### Evidencia (transaccional) — cadena de custodia completa
- Atributos: `id`, `session_id`, `uri_bucket`, `hash_cliente`, `firma_cliente`, `hash_backend`, `firma_maestra`, `output_reinferencia`, metadatos.
- Relaciones: *—1 Sesión (vía evento); 1—* Audit log; 1—1 Caso disciplinario (opcional).
- Constraints: binario en bucket WORM (Object Lock, modo Compliance); inmutable durante la retención.

### Audit log (transaccional, append-only)
- Atributos: `id`, `actor`, `timestamp`, `IP`, `user-agent`, `acción`, `evidencia_id`, `propósito`, `hash_entrada_anterior`.
- Constraints: **append-only**; trigger rechaza UPDATE/DELETE; cada entrada incluye el hash de la anterior ("blockchain rudimentaria" validada a diario); backups físicamente separados con destino write-only leídos por sistema de auditoría externo.

### Caso disciplinario (transaccional)
- Atributos: `id`, `session_id`, `estado`, referencias a evidencia, decisiones, vínculo a sistema externo.
- Notas: **extiende la retención** mientras esté abierto (hold).

### Consentimiento (transaccional, inmutable)
- Atributos: `id`, `user_id`, `exam_id`, `versión_texto`, `timestamp`, `hash`.
- Notas: registro inmutable de la sesión; acuse del consentimiento informado.

## Seed data inicial

El discovery no especifica un seed concreto. Datos mínimos inferidos para arrancar:

- **Roles** del sistema: estudiante, proctor, revisor académico, coordinador disciplinario, administrador de exámenes, administrador del sistema, auditor.
- **Realm/clientes de Keycloak** y federación con el directorio institucional configurada.
- **Configuración de retención** por defecto (políticas de retención y holds).
- **Foto institucional de referencia** por estudiante (prerrequisito gestionado por la institución vía proceso de registro previo — no es seed del sistema sino dependencia externa).

**Suposición:** los usuarios se crean por JIT provisioning al primer login federado, por lo que no hay seed masivo de usuarios. Ver `10_preguntas_abiertas.md`.
