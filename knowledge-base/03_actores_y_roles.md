# Actores y Roles

## Actores del sistema

Los roles reflejan el ciclo de vida del examen y la disciplina. Hay siete roles funcionales más actores de gobernanza/stakeholder.

| Actor / Rol | Descripción | Cómo interactúa |
|-------------|-------------|-----------------|
| Estudiante | Quien rinde el examen desde su navegador | Autentica, consiente, verifica identidad, rinde con el detector corriendo localmente; ejerce derechos del titular |
| Proctor en vivo | Personal académico que supervisa exámenes en curso | Panel en vivo priorizado por riesgo; mensajería al estudiante, observaciones, cierre forzado |
| Revisor académico | Revisa sesiones flaggeadas después del examen | Toma sesiones de su jurisdicción; ve contexto completo; emite decisión terminal |
| Coordinador disciplinario / operativo | Opera el programa de proctoring | Asigna proctors, gestiona la cola, escala a TI, lee métricas operacionales |
| Administrador de exámenes | Configura los exámenes | Crea exámenes, define parámetros de monitoreo, asigna estudiantes, carga foto de referencia |
| Administrador del sistema | Opera la plataforma técnicamente | Observabilidad, runbooks, despliegues, backups, recuperación |
| Auditor | Solo lectura, incluido el audit log | Acceso de lectura para control independiente |
| **Stakeholders de gobernanza** | Patrocinadores (rectorado), dirección académica, área legal/DPO, TI, equipo de implementación | No operan el sistema día a día; deciden políticas, aprueban, proveen infraestructura (ver gobernanza abajo) |

### Personas de referencia (del discovery)
- **Sofía (22)** — Estudiante: rinde sin fricción ni ansiedad.
- **Martín (35)** — Proctor en vivo: atiende solo lo que requiere atención.
- **Lucía (44)** — Revisora académica: decide con criterio y evidencia.
- **Diego (39)** — Coordinador operativo: exámenes sin incidentes, cola sin acumular.
- **Ana (50)** — Oficial de protección de datos (DPO): tratamiento legal, derechos del titular.
- **Pablo (33)** — Administrador del sistema: disponibilidad y recuperabilidad.

## RBAC — Matriz de permisos

Los permisos **no son globales sino contextuales**: un proctor observa exámenes específicos asignados; un revisor tiene jurisdicción sobre su área. La descarga de una captura requiere URL firmada que expira en 15 min; ciertos accesos exigen **propósito declarado** persistido en el audit log. **MFA obligatorio** para todos los roles con acceso a evidencia o administración (proctor, revisor, coordinador, administradores).

| Rol | Recurso | Permisos | Restricciones |
|-----|---------|----------|---------------|
| Estudiante | Su propia sesión | C (iniciar), R (estado propio) | Solo su sesión; sin acceso a evidencia ajena |
| Estudiante | Sus datos personales (DSR) | R, U (rectificar), D (eliminar), portar | Sin casos abiertos para eliminar |
| Proctor | Sesiones de exámenes asignados | R, U (observaciones, mensajes, cierre forzado) | Solo exámenes asignados; MFA |
| Proctor | Evidencia de sesiones asignadas | R (captura vía URL firmada 15 min) | Acceso auditado con propósito |
| Revisor académico | Cola de revisión de su jurisdicción | R, U (decisión terminal) | Solo su jurisdicción; cada apertura auditada; MFA |
| Revisor académico | Evidencia + contexto de sesión flaggeada | R | Acceso auditado con propósito declarado |
| Coordinador operativo | Asignación de proctors, cola, backlog | C, R, U | Escala a TI; MFA |
| Admin de exámenes | Exámenes, parámetros, asignación de estudiantes, foto referencia | C, R, U, D | MFA |
| Admin del sistema | Configuración técnica, despliegues, backups | C, R, U, D | MFA; acceso elevado |
| Auditor | Audit log, registros, evidencia (lectura) | R | Solo lectura, incluido audit log |
| Caso disciplinario | Coordinador disciplinario (revisor deriva) | C, R, U | Decisión final siempre humana |

### Decisión disciplinaria (resumen RACI operativo)
- **Revisión de sesiones flaggeadas**: Responsable = Revisor; Aprobador = Coordinador operativo.
- **Decisión disciplinaria final**: Aprobador/Responsable = Dirección académica. **El sistema nunca sanciona automáticamente.**

## Rutas públicas

El discovery no enumera explícitamente rutas sin autenticación. Inferidas:

- Pantalla de login institucional (redirección a Keycloak) — el flujo de autenticación es público hasta obtener el JWT.
- `POST /api/v1/auth/refresh` opera con token (no es estrictamente pública).
- Recursos estáticos del frontend servidos por Nginx (HTML/JS/CSS, modelos de MediaPipe cargados de forma diferida).

**Suposición:** todo el resto de la API REST y los canales WebSocket exigen JWT válido (validado en cada request HTTP y en el handshake WS + revalidación periódica). El consentimiento informado y la verificación biométrica ocurren **después** del login, por lo que no son rutas públicas. Ver `10_preguntas_abiertas.md` (lista canónica de rutas públicas no especificada en la fuente).
