# Roadmap y Riesgos

Complementa `01_vision_y_objetivos.md` (alcance por fases) y `10_preguntas_abiertas.md`.

## Roadmap por fases

Duración total estimada hasta operación sostenida: **12–18 meses**. No se avanza sin cumplir los criterios de salida.

| Fase | Duración | Objetivos y entregables | Criterios de salida |
|------|----------|-------------------------|---------------------|
| **Fase 0 — Fundaciones** | 4–8 semanas | No produce software: firma del Acuerdo de Nivel de Proctoring, DPIA por legal, aprobación de los 14 ADRs (Tier 1), setup de infraestructura de dev (repo, CI/CD, registry), conformación y onboarding del equipo, contratos y SLAs | Documentos firmados, ADRs aprobados, infra de dev funcional, equipo onboarded, primer sprint planeado |
| **Fase 1 — MVP** | 3–5 meses | Ciclo completo de un examen: auth federada, verificación biométrica con liveness desde el inicio, pipeline MediaPipe con eventos básicos, WebSockets + TimescaleDB + heartbeats firmados, cadena de custodia completa, panel de proctor mínimo, flujo de revisión humana, observabilidad básica, seguridad y privacidad, runbooks | Funcionalidades testeadas, métricas de calidad cumplidas, documentación operacional, on-call capacitado, **piloto controlado exitoso con examen real** |
| **Fase 2 — Refinamiento** | 2–4 meses | Corrección de hallazgos del piloto, features diferidas (audio, detección avanzada de tampering, integración LMS específica, paneles sofisticados, liveness pasivo open-source), calibración de modelos con datos reales, endurecimiento operacional | Estabilidad sostenida (incidentes graves bajo umbral/trimestre), métricas en línea con proyecciones, satisfacción medida, documentación actualizada |
| **Fase 3 — Escala y evolución** | Indefinida (operación regular) | Migración a Kubernetes, preparación multi-tenancy, capacidades avanzadas, integraciones adicionales, expansión geográfica | SLA cumplido, costos por institución en línea, capacidad de incorporar nuevas instituciones en plazos razonables |

### Tecnología por fase
- **Fase 1**: MediaPipe en navegador (GPU), liveness híbrido propio, re-inferencia server-side, detección de cámara virtual, cadena de custodia completa, stack de backend + observabilidad base. (Recomendación A4: Postgres-como-cola + SSE para el panel.)
- **Fase 2**: liveness pasivo open-source self-hosted, análisis de audio, evaluación de WebGPU, calibración de umbrales con datos reales, integración LMS, (eventual) Redis como backplane/caché, ONNX Runtime Web, réplica de lectura de Postgres.
- **Fase 3**: Kubernetes con autoescalado, mensajería dedicada (RabbitMQ quorum/NATS) solo si Postgres-como-cola es cuello demostrado, multi-tenancy, SDK de liveness certificado PAD Nivel 2+ si sube el nivel de impacto.

## Registro de riesgos (selección R-001…R-030 / O / L)

| ID | Riesgo | Prob. | Impacto | Mitigación | Estado |
|----|--------|-------|---------|-----------|--------|
| R-001 | Bypass por estudiante técnico medio | Media-alta | Medio | Anti-tampering pasivo, análisis estadístico de sesiones "demasiado limpias", cláusula contractual | Aceptado |
| R-002 | En disputa se argumenta evidencia razonable, no prueba absoluta | Alta | Medio | Cadena de custodia formal, capacitación de revisores | Aceptado |
| R-003 | Falsos positivos por hardware de baja calidad | Media | Alto* | Detección de capacidad mínima, umbrales conservadores, escalación a proctor | Mitigado |
| R-006 | Hardware insuficiente para Face Mesh + Pose simultáneos | Media | Medio | Detección de capacidad, degradación graceful, fallback a Face Detection | Mitigado |
| R-010 | Liveness bypaseable con video pregrabado | Baja | Medio | Verificación continua + revisión humana | Aceptado |
| R-026 | Compromiso de la clave maestra de firma | Baja | Crítico | Rotación anual, archivo seguro de claves previas, plan de respuesta | Mitigado |
| O-001 | On-call insuficientemente capacitado en incidente crítico | Media | Alto | Capacitación obligatoria, simulacros, runbooks, doble cobertura en picos | En mitigación |
| O-003 | Capacidad insuficiente de revisión humana | Media | Alto | Estimación temprana de carga, capacitación, monitoreo de backlog | Acción del cliente |
| L-001 | Cambio regulatorio en protección de datos | Baja | Alto | Monitoreo del marco, revisión legal anual, adaptabilidad de retención | Aceptado/monitoreo |
| L-002 | Caso disciplinario que llega a la justicia ordinaria | Baja | Alto | Cadena de custodia robusta, capacidad de peritaje, asesoría legal | Mitigado |
| L-004 | Brecha entre expectativas del cliente y capacidades reales | Media | Alto | Acuerdo de Nivel de Proctoring, comunicación regular, ajuste de expectativas | Mitigado |

\* Alto sobre el estudiante individual afectado, bajo en agregado.

### Dimensiones de riesgo
- **Técnicos**: manipulación del cliente, hardware insuficiente, dependencia de versiones de MediaPipe, complejidad del stack de mensajería, WebSocket fan-out.
- **Operativos**: on-call no capacitado, pérdida de personal clave, **capacidad de revisión humana (el más subestimado)**, desactualización de dependencias, drift de configuración.
- **Legales y éticos**: tratamiento de datos biométricos, derecho al olvido vs. retención forense, transferencias internacionales, transparencia.
- **Académicos y de adopción**: resistencia estudiantil, percepción de vigilancia excesiva, falsos positivos que afectan a inocentes, sostenibilidad del compromiso institucional.

## Recomendaciones clave (cierre estratégico)

1. **No saltar la Fase 0**: firmar el Acuerdo de Nivel de Proctoring y completar el DPIA antes de escribir código.
2. **Designar y capacitar coordinación operativa y revisores antes de la Fase 1** (dependencia más subestimada).
3. **Validar el capacity model** contra datos reales al cierre del piloto y trimestralmente el primer año.
4. **Comunicar a la comunidad estudiantil** con transparencia qué se monitorea y qué no.
5. **Mantener el threat model como contrato vivo**: cualquier intento de usar el sistema para evaluaciones de mayor impacto dispara su revisión formal.

> El factor de riesgo dominante **no es tecnológico sino organizacional**: el compromiso institucional sostenido (en especial la capacidad de revisión humana).

## Gestión del cambio y adopción

- **Capacitación por rol**: coordinación operativa, proctors en vivo, revisores académicos, on-call/TI, administradores de examen.
- **Comunicación a estudiantes**: transparencia proactiva antes del primer examen; publicar requisitos de dispositivo; explicar consentimiento y derechos; involucrar a representaciones estudiantiles; mostrar los límites deliberados (sin video continuo, sin lockdown, sin sanción automática).
- **Despliegue gradual**: piloto controlado → expansión escalonada (validando capacity model en cada salto) → operación sostenida con SLAs → revisión continua al cierre de cada fase.
