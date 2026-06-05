# Preguntas Abiertas

## Inconsistencias detectadas

### IN-01 — SAD original vs. arquitectura recomendada (mensajería)
**Parte II (cap. 7–9) dice**: stack de mensajería = Redis (Pub/Sub + caché) + RabbitMQ (quorum, tareas críticas) + Celery; ADR-0006 lo formaliza.
**Apéndice A4.2 dice**: para 700 concurrentes ese triple stack está sobre-dimensionado; recomienda **Postgres como cola** (pg-boss / SKIP LOCKED) en el MVP y reservar RabbitMQ/NATS solo si una métrica demuestra que Postgres es el cuello de botella.
**Impacto**: define qué infraestructura se levanta en Fase 1. Afecta costo operacional, número de piezas a operar y time-to-market.
**Resolución propuesta**: adoptar la recomendación A4 (Postgres-como-cola) para el MVP y validar con una PoC de carga en Fase 0/1; mantener RabbitMQ como evolución documentada en ADR. **Decisión a confirmar por el equipo técnico.**

### IN-02 — Transporte: WebSockets+sticky en todo vs. SSE para el panel
**Cap. 9.3 / ADR-0008 dice**: WebSockets con sticky sessions en todos los canales.
**Apéndice A4.3 dice**: WebSocket solo para el estudiante (bidireccional); SSE + backplane para el panel (unidireccional), sin sticky sessions.
**Impacto**: acoplamiento del escalado y complejidad de transporte.
**Resolución propuesta**: SSE + backplane para el panel (DD-16); confirmar tras PoC.

### IN-03 — Motor de visión: MediaPipe acoplado vs. abstraído
**Cap. 7–8 dice**: MediaPipe como motor de visión.
**Apéndice A4.1 dice**: abstraer el motor para migrar a ONNX Runtime Web (Google deprecó partes de MediaPipe).
**Impacto**: lock-in tecnológico y esfuerzo de migración futura.
**Resolución propuesta**: MediaPipe en MVP detrás de una interfaz abstracta (DD-17).

### IN-04 — Embeddings: ¿dato sensible? (Argentina)
**Resolución AAIP 4/2019 (A1.3)**: en Argentina los datos biométricos son sensibles **solo** cuando pueden revelar información potencialmente discriminatoria — podría no calificar el embedding como sensible.
**RGPD / recomendación de diseño**: tratarlo como sensible por defecto.
**Impacto**: nivel de protección legal exigido, bases legales y DPIA.
**Resolución propuesta**: tratar como sensible por defecto ("responsabilidad reforzada"); el área legal formaliza la clasificación.

## Preguntas abiertas (priorizadas)

| Prioridad | Pregunta | Bloquea | Decisor |
|-----------|----------|---------|---------|
| Alta | ¿Se firma el Acuerdo de Nivel de Proctoring y se completa el DPIA antes de codificar? | Salida de Fase 0 (sin esto el proyecto no avanza) | Patrocinador + Legal/DPO |
| Alta | ¿Mensajería del MVP: Postgres-como-cola (A4) o RabbitMQ+Celery (SAD)? | Setup de infraestructura Fase 1 | Equipo técnico (post-PoC) |
| Alta | ¿La institución designa y capacita coordinación operativa y revisores antes de Fase 1? | Operación de la revisión humana (dependencia más subestimada) | Dirección académica + Coordinación |
| Alta | ¿Existe foto institucional de referencia de calidad para cada estudiante? | Verificación biométrica 1:1 | TI + institución |
| Alta | ¿Cuál es la lista canónica de rutas públicas (sin auth)? No está explícita en el discovery. | Diseño de seguridad / routers | Equipo técnico |
| Media | ¿Transporte del panel: SSE+backplane o WebSocket+sticky? | Arquitectura de tiempo real | Equipo técnico (post-PoC) |
| Media | ¿Valores concretos de umbrales (score, distancia coseno, N fotogramas, severidades)? El discovery los deja "configurables" sin fijar números. | Calibración Fase 1/2 | Dirección académica + equipo |
| Media | ¿Política de retención concreta por tipo de dato (capturas, embeddings, eventos, audit log, casos)? Se mencionan 30 días / 1 año / 7 años / 2 años en distintos contextos. | Implementación de retención automática | Legal/DPO + equipo |
| Media | ¿Algoritmo exacto de scoring (pesos por severidad, ventanas de correlación)? Descrito conceptualmente, no formalmente. | Implementación del scoring | Equipo + dirección académica |
| Media | ¿Hay población menor de 18 años? Requiere flujo de consentimiento parental y retención diferenciada. | Cumplimiento legal | Legal/DPO |
| Media | ¿Dimensiones del embedding (128–512) y algoritmo de extracción definitivo? "típicamente 128–512" en la fuente. | Verificación biométrica | Equipo técnico |
| Media | ¿Estructura de directorios y env vars definitivas? Inferidas en la KB, no especificadas. | Convenciones del repo | Equipo técnico |
| Baja | ¿Integración LMS concreta (qué LMS, LTI vs iframe vs flujo coordinado)? | Fase 2 | TI + dirección académica |
| Baja | ¿Esquema de multi-tenancy (aislamiento por DB, por schema, por fila)? | Fase 3 | Equipo técnico |
| Baja | ¿Seed data inicial concreto (roles, realms Keycloak, configuración por defecto)? No detallado. | Bootstrap del sistema | Equipo técnico |
| Baja | ¿Inscripción de la base ante la AAIP? Acción pendiente del área legal. | Cumplimiento Argentina | Legal/DPO |
| Baja | ¿Se ofrece efectivamente la vía alternativa de verificación sin biometría? Recomendada legalmente, no confirmada en el alcance. | Cumplimiento del consentimiento libre | Dirección académica + Legal |

## Cambios relevantes con impacto de gobernanza

### C-51 — Terminología: foto+embedding (tradeoff de liveness temporal server-side)

**C-51** consolida en la KB el modelo biométrico de enrollment como **foto de referencia (snapshot) + embedding**. Este modelo resuelve **identidad** (comparación 1:1: embedding del momento vs. embedding de la foto de referencia), pero **NO liveness temporal server-side**.

**El tradeoff concreto**: una foto plana no permite re-inferencia temporal (movimiento, parpadeo, profundidad en secuencia). El liveness que corre en el navegador (liveness híbrido: análisis pasivo + retos activos aleatorios) opera sobre el stream de video en vivo *sin persistirlo como clip*. Esa liveness check es **client-side** — y el cliente es sensor no confiable (regla dura #6 del proyecto).

El dominio `backend/app/domain/biometrics/liveness.py` existe para la verificación server-side de "rostro real, no foto plana", pero opera sobre el frame estático del momento (re-inferencia estática, no sobre una secuencia temporal). No puede detectar, por ejemplo, que el usuario presentó una foto impresa en lugar de su rostro en movimiento.

**Implicación para el DPIA (C-01)**: el Acuerdo de Nivel de Proctoring y el DPIA **deben registrar y justificar explícitamente** este tradeoff dentro del nivel L2.5 declarado. La justificación razonable es: el liveness client-side + verificación continua de embedding + revisión humana asíncrona constituyen la red de seguridad aceptada para L2.5. Si la institución requiere liveness temporal server-side garantizado, el nivel de proctoring y el modelo de evidencia deben revisarse (y el DPIA actualizarse).
