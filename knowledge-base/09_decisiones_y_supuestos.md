# Decisiones y Supuestos

## Decisiones documentadas

Las 14 ADRs Tier 1 del discovery (deben aprobarse en Fase 0), seguidas de las **revisiones del análisis independiente A4** que ajustan algunas para el MVP.

### DD-01 (ADR-0001) — Nivel de proctoring L2.5
**Decisión**: adoptar el nivel L2.5 (análisis en cliente + verificación biométrica + anti-tampering pasivo).
**Contexto**: calibra expectativas y todas las decisiones posteriores.
**Alternativas consideradas**: L0/L1 (sin garantía probatoria), L2 puro (sin identidad fuerte), L3 (grabación completa, costo/privacidad), L4 (sincrónico, no escala a 700), L5 (lockdown nativo, otro proyecto).
**Justificación**: el costo incremental sobre L2 es modesto y cierra el hueco de identidad; garantía suficiente para el caso académico interno sin sobrecostos.
**Trade-offs aceptados**: acepta bypass por adversario sofisticado; ninguna sanción automática.

### DD-02 (ADR-0002) — Procesamiento en cliente (client-heavy)
**Decisión**: IA de visión en el navegador; el backend trata al cliente como sensor no confiable.
**Contexto**: viabilizar la escala a costo sostenible.
**Alternativa descartada**: inferencia centralizada (10–50× más cara).
**Trade-offs**: el backend solo ve los pixels en momentos puntuales; depende de la capacidad del dispositivo del estudiante.

### DD-03 (ADR-0003) — Verificación biométrica desde el MVP
**Decisión**: incluir biometría con liveness desde la Fase 1 (no diferida).
**Justificación**: sin identidad fuerte, toda la evidencia opera sobre un supuesto no validado.
**Alternativa descartada**: diferir biometría a fase posterior.

### DD-04 (ADR-0004) — Anti-tampering pasivo
**Decisión**: anti-tampering pasivo (CSP, SRI, fingerprint, heartbeats firmados, detección de DevTools/cámara virtual), **modo log, no abort**.
**Justificación**: eleva el costo del bypass sin pretender inviolabilidad; evita falsos positivos que aborten exámenes.
**Alternativa descartada**: lockdown nativo (sería L5, otro proyecto).

### DD-05 (ADR-0005) — TimescaleDB para eventos
**Decisión**: usar TimescaleDB (extensión de Postgres) para la tabla de eventos como hypertable.
**Justificación**: hypertables, compresión 10–20× y agregados continuos resuelven el patrón de escritura intensa sin introducir otra DB.
**Alternativa descartada**: PostgreSQL nativo (se degrada, DELETE masivos costosos) / NoSQL (rompe consistencia).
**Veredicto A4**: **Conservar** (excelente encaje).

### DD-06 (ADR-0006) — RabbitMQ para tareas críticas
**Decisión**: RabbitMQ con quorum queues (consenso Raft) para re-inferencia y firma de evidencia.
**Justificación**: durabilidad real; un mensaje confirmado no se pierde ante caída de nodo (su pérdida rompería la cadena de custodia).
**Alternativa descartada**: Redis como broker (durabilidad insuficiente).
**Veredicto A4**: **Revisar / simplificar** — es el punto más sobre-dimensionado para 700 concurrentes (ver DD-15).

### DD-07 (ADR-0007) — Cadena de custodia con Object Lock
**Decisión**: WORM (Object Lock modo Compliance) + firmas encadenadas + audit log inmutable.
**Justificación**: evidencia defendible matemáticamente; un perito externo valida la cadena.
**Alternativa descartada**: almacenamiento plano sin inmutabilidad.
**Veredicto A4**: **Conservar sin cambios**.

### DD-08 (ADR-0008) — Fan-out híbrido y sticky sessions
**Decisión**: Redis Pub/Sub para eventos no críticos + RabbitMQ durable para alertas críticas; sticky sessions para WebSockets.
**Justificación**: evita distribuir estado de WebSocket entre instancias.
**Alternativa descartada**: estado de WS distribuido (complejidad sin beneficio a esta escala).
**Veredicto A4**: **Revisar** — usar SSE para el panel (unidireccional) y backplane (Redis Pub/Sub o Postgres LISTEN/NOTIFY) para no acoplar el escalado (ver DD-16).

### DD-09 (ADR-0009) — Keycloak como IdP
**Decisión**: Keycloak (OAuth2/OIDC/SAML) para federación, MFA y gestión de roles.
**Justificación**: implementar auth a mano es catastrófico si falla (session fixation, CSRF, tokens).
**Alternativa descartada**: autenticación propia.
**Veredicto A4**: **Conservar**.

### DD-10 (ADR-0010) — FastAPI mono-hilo escalado horizontalmente
**Decisión**: una instancia = un proceso uvicorn de un solo hilo asíncrono; escalar horizontalmente detrás de Nginx (no multi-worker dentro de la instancia).
**Justificación**: métricas por proceso interpretables, fallas aisladas, migración trivial a K8s (1 instancia ≈ 1 pod).
**Alternativa descartada**: multi-worker dentro de la instancia.

### DD-11 (ADR-0011) — Despliegue inicial con Docker Compose
**Decisión**: arrancar con Docker Compose; código twelve-factor desde el día uno.
**Justificación**: time-to-market del piloto; migrar a K8s sin reescritura.
**Alternativa descartada**: Kubernetes desde el inicio (sobrecarga prematura).
**Veredicto A4**: **Conservar** (pragmatismo correcto).

### DD-12 (ADR-0012) — Observabilidad de primera clase
**Decisión**: Prometheus/Loki/Tempo/Grafana desde Fase 0.
**Justificación**: una función no observable no se considera lista.
**Alternativa descartada**: observabilidad como fase posterior.

### DD-13 (ADR-0013) — Privacidad por diseño
**Decisión**: minimización (sin video continuo), retención configurable, derechos del titular nativos.
**Alternativa descartada**: recolección amplia "por si acaso".

### DD-14 (ADR-0014) — Acuerdo de Nivel de Proctoring contractual
**Decisión**: firmar el Acuerdo de Nivel de Proctoring antes de desarrollar; sin él, el proyecto no pasa de Fase 0.
**Justificación**: la mejor protección contra el fracaso por expectativas mal calibradas.
**Alternativa descartada**: threat model solo como sección técnica que pocos leen.

### DD-15 (Revisión A4) — Simplificar la mensajería: Postgres como cola en el MVP
**Decisión**: para el MVP, usar **Postgres como cola** (pg-boss / SKIP LOCKED + LISTEN/NOTIFY) en lugar de RabbitMQ + Celery + (opcionalmente) Redis. Mantener Redis solo si el fan-out en tiempo real lo exige (medido). Reservar RabbitMQ/NATS para fase posterior **solo si** el monitoreo demuestra que Postgres es el cuello de botella.
**Contexto**: tres piezas de mensajería para 700 concurrentes es complejidad operacional alta para un equipo acotado.
**Alternativas**: A) Postgres-como-cola (muy baja complejidad, durabilidad ACID — **recomendada MVP**); B) Redis Streams + BullMQ; C) RabbitMQ quorum + Celery (SAD original); D) NATS JetStream.
**Justificación**: reduce costo operacional, riesgo y time-to-market sin sacrificar durabilidad de la evidencia.
**Trade-offs**: menor techo de throughput que un broker dedicado; mitigado por instrumentación y ruta de evolución documentada en ADRs.

### DD-16 (Revisión A4) — Transporte: SSE para el panel + backplane
**Decisión**: WebSocket bidireccional solo para el canal del estudiante (eventos/heartbeats/comandos); **SSE** (server-sent events) para el panel del proctor/revisor (unidireccional, reconecta solo); backplane (Redis Pub/Sub o Postgres LISTEN/NOTIFY) para distribuir eventos entre instancias y eliminar la dependencia de sticky sessions.
**Justificación**: menos acoplamiento de escalado y menos fragilidad del "hash que concentra conexiones".

### DD-17 (Revisión A4) — Abstraer el motor de visión
**Decisión**: usar MediaPipe para el MVP (time-to-market) pero detrás de una **interfaz abstracta** para poder migrar a **ONNX Runtime Web** (open standard, WebGPU creciente, control total del pipeline) sin reescribir el resto.
**Contexto**: Google ha reorganizado/deprecado partes de MediaPipe repetidamente.
**Veredicto A4 sobre MediaPipe**: **Revisar** (mantener, pero con la abstracción).

### DD-18 (Revisión A4) — Liveness escalonado
**Decisión**: MVP → liveness **híbrido propio** (pasivo + 1–2 retos activos aleatorios) en el navegador + re-inferencia server-side + detección de cámara virtual. Fase 2 → modelo de liveness pasivo open-source self-hosted (tipo Silent-Face-Anti-Spoofing / DeePixBiS) sobre el clip. Fase 3 → SDK comercial certificado ISO/IEC 30107-3 Nivel 2+ **solo si** se eleva el nivel de impacto.
**Justificación**: ningún liveness en navegador es inmune a inyección de cámara/deepfakes; la red de seguridad real es verificación continua + revisión humana. Estándar de referencia: ISO/IEC 30107-3 (métricas APCER/BPCER).

### DD-19 (Revisión A4) — Principio rector de escalado
**Decisión**: "Empezá con la arquitectura más simple que cumpla los NFR, instrumentá todo, y agregá complejidad solo cuando una métrica lo demuestre necesario." Validar con una PoC en Fase 0/1 que mida Postgres-como-cola y SSE bajo carga de 700 concurrentes.
**Trade-offs**: si la PoC muestra límites, las opciones del SAD original (RabbitMQ, WebSockets) siguen sobre la mesa como evolución documentada, no como retrabajo.

### DD-20 (Decisión de integración) — Integración con LMS vía LTI 1.3, sin acoplar a un LMS concreto
**Decisión**: la integración con el sistema de evaluación institucional (Moodle, Canvas, Blackboard, D2L, Sakai…) se hace mediante **LTI 1.3** (1EdTech/IMS Global), NO con un plugin específico de un LMS. El LMS **opera el examen**; el proctoring se integra **alrededor** (lanzamiento LTI → handshake de identidad y contexto → proctoring envolviendo la actividad del examen). Identidad del lanzamiento encaja con el OIDC de Keycloak (DD-09); roster vía **NRPS** (Names and Roles Provisioning Service); retorno de resultado/score vía **AGS** (Assignment and Grade Services).
**Contexto**: la visión declara fuera de alcance "operar el examen mismo" — la interfaz de preguntas/respuestas y la nota son del LMS/docente; el proctoring NO se acopla a un LMS concreto (`01_vision_y_objetivos.md` §Fuera de alcance; `02_descripcion_general.md` §Integraciones; FR-17, Épica 18).
**Justificación**: LTI 1.3 es el estándar universal — UN solo desarrollo integra con cualquier LMS compatible. Es la respuesta directa al requisito de **adaptación fácil a cualquier entidad académica**. Un plugin `quizaccess` de Moodle daría integración más profunda pero con lock-in a Moodle.
**Alcance temporal**: la implementación es **Fase 2** (FR-17 / `C-49`), depende de los gates C-01 (DPIA) + C-02 (revisores) + del MVP operativo (no se integra un proctoring que aún no existe). **Accionable desde el MVP**: diseñar la superficie de API "LTI-ready" — endpoint/webhook de retorno de resultado (AGS), provisioning de roster (NRPS) y mapeo de claims→roles (hoy huecos: la API REST y el flujo de lanzamiento son propios, sin handoff externo).
**Alternativas consideradas**: A) **LTI 1.3** (universal — recomendada); B) plugin Moodle `quizaccess` (profundo pero solo Moodle); C) iframe embedding sin estándar (frágil); D) flujo coordinado custom por LMS (no escala).
**Trade-offs**: implementar un Tool Provider LTI 1.3 (OIDC login, deep linking, AGS, NRPS) es más trabajo inicial que un iframe, pero se amortiza en la primera segunda institución.

### DD-21 (Decisión de cliente) — Cliente del alumno = web app, no extensión/app nativa (extensión como mejora forense opcional de Fase 3)
**Decisión**: el cliente del alumno sigue siendo una **web app** en navegador (React + Vite + MediaPipe en Web Worker). NO se adopta una extensión de Chrome ni una app nativa como cliente del alumno. La separación alumno ↔ resto de roles ya la provee el RBAC contextual (`03_actores_y_roles.md`), no requiere extensión.
**Contexto**: se evaluó mover el cliente del alumno a una extensión de Chrome (o un híbrido extensión+web). Hallazgos del análisis: (1) una extensión **no sube el nivel de proctoring fundamental** — el cliente sigue siendo **sensor no confiable** (DD-02, RN-GLB-01), sigue confinada al sandbox del navegador y **no ve el SO** (`chrome.processes` solo ve procesos del navegador): no detecta segundo monitor, celular ni apps de escritorio; (2) agrega costo real de **distribución** (force-install exige equipos gestionados AD/Workspace; la universidad no controla las laptops personales → queda instalación voluntaria), **lock-in a Chrome/Chromium** (se pierde multi-navegador) y **carga legal** (instalar software en la máquina del alumno eleva la vara de consentimiento y cambia la proporcionalidad del DPIA — C-01); (3) **no resuelve la integración con el LMS**, que es server-side (ver DD-20).
**Justificación**: coherente con DD-01 (el lockdown nativo L5 es "otro proyecto"), DD-02 (cliente no confiable) y DD-19 (no agregar complejidad sin métrica que lo exija). Una extensión mejoraría **observabilidad forense, no seguridad fundamental**.
**Ruta futura (Fase 3, condicional)**: si una institución puede mandar Chrome en **equipos gestionados** y una métrica justifica más señal forense, se puede sumar una **extensión OPCIONAL como complemento aditivo** (no reemplazo) de la web app — patrón de degradación elegante: sin extensión rinde igual por web, con extensión suma visibilidad cross-tab/historial para la revisión humana. Vencer segundo-monitor/celular/IA-escritorio requiere lockdown nativo (L5), fuera de scope.

## Supuestos inferidos

### SU-01 — Fotos institucionales de referencia disponibles
**Supuesto**: la institución dispone de fotos de calidad razonable de cada estudiante.
**Origen**: B7.1 Supuestos del discovery.
**Riesgo si es falso**: sin foto de referencia la verificación 1:1 no opera; requiere proceso de registro previo.
**Cómo validar**: auditar el directorio institucional de fotos antes de Fase 1.

### SU-02 — Dispositivos cumplen el perfil mínimo
**Supuesto**: los estudiantes acceden con cámara, mic, navegador moderno y ≥10/2 Mbps.
**Origen**: B7.1 / A3.3.
**Riesgo si es falso**: falsos positivos por hardware insuficiente; necesidad de degradación o escalación.
**Cómo validar**: telemetría de capacidad desde el día uno; comunicar requisitos a la comunidad.

### SU-03 — Capacidad de revisión humana sostenida
**Supuesto**: la institución sostiene revisión humana del 5–15% de las sesiones.
**Origen**: 4.3 / B7.1 / 13.9 (el supuesto más subestimado).
**Riesgo si es falso**: la evidencia se acumula sin revisión; el sistema falla en su propósito.
**Cómo validar**: designar y capacitar revisores antes de Fase 1; monitorear backlog.

### SU-04 — Equipo de operaciones con conocimiento básico de stack
**Supuesto**: el equipo tiene o adquiere conocimiento de Docker, Prometheus/Grafana y PostgreSQL.
**Origen**: B7.1.
**Riesgo si es falso**: incidentes mal gestionados durante ventanas críticas.
**Cómo validar**: capacitación obligatoria, simulacros, runbooks.

### SU-05 — Marco legal del país de la institución
**Supuesto**: el marco legal aplicable es el del país de la institución y de la mayoría de los estudiantes (Argentina, Ley 25.326).
**Origen**: B7.1 / A1.
**Riesgo si es falso**: estudiantes en UE/Brasil requieren análisis legal específico (GDPR/LGPD).
**Cómo validar**: identificar jurisdicciones de la cohorte; completar el DPIA.

### SU-06 — Capacity model (NFR de capacidad revisado)
**NFR confirmado (mayo 2026)**: el objetivo operacional sostenido es **1.000 concurrentes** (elevado desde los 700 del discovery original), con **~2.100 en pico multi-examen**. El discovery estimaba 700 concurrentes / 1–1,5k inserts/s / ~5k pico; el equipo eleva el sostenido a 1.000.
**Supuesto remanente**: el escalado de inserts respecto del sostenido es ~lineal (~1.000 inserts/s sostenido, ~5.000 pico) — a validar.
**Origen**: B7.1 / 15.1, revisado por el equipo.
**Riesgo si es falso**: re-dimensionamiento; el dimensionamiento de `08_arquitectura_propuesta.md` se calculó sobre 700 y debe revalidarse contra 1.000 sostenido / 2.100 pico.
**Cómo validar**: monitoreo desde el día uno + **PoC de carga clavada al pico (~2.100 / ~5.000 inserts/s)**, no al sostenido (ver `DD-19` y `14_observabilidad_y_devops.md`).

### SU-07 — Estructura de directorios y env vars
**Supuesto**: el árbol de carpetas y las variables de entorno de `08_arquitectura_propuesta.md` son inferidos (no especificados en la fuente).
**Origen**: inferencia del stack y la arquitectura por capas.
**Riesgo si es falso**: convenciones distintas en implementación.
**Cómo validar**: fijar convenciones en el primer sprint y reflejarlas en el README del repo.

### SU-08 — Embedding tratado como dato sensible por defecto
**Supuesto**: aunque la interpretación local (Resolución AAIP 4/2019) podría no calificarlo siempre como "sensible", se trata como sensible por defecto.
**Origen**: A1.3 (recomendación de diseño).
**Riesgo si es falso**: sobre-protección de bajo costo; el riesgo real es el contrario (sub-proteger).
**Cómo validar**: el área legal formaliza la clasificación y completa el DPIA.
