# Plataforma de Proctoring para Evaluaciones Remotas — Base de Conocimiento

Base de conocimiento canónica generada a partir del documento de discovery del proyecto (`docs/Discovery_Proctoring_Evaluaciones_Remotas.pdf`, 89 páginas).

## Índice de Archivos

### Canónicos (obligatorios)

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance v1.0, fuera de alcance, métricas de éxito |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack tecnológico, arquitectura general (SAD y recomendada), integraciones, API |
| [03_actores_y_roles.md](03_actores_y_roles.md) | Actores, personas, matriz RBAC contextual, rutas públicas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | Entidades, ERD, relaciones, hypertable de eventos, seed data |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | Reglas codificadas por dominio (RN-AU, RN-BIO, RN-EV, RN-SC, RN-CC, RN-RV, RN-DSR…) |
| [06_funcionalidades.md](06_funcionalidades.md) | Historias de usuario por épica (FR-01…FR-18, UC-01…UC-06) |
| [07_flujos_principales.md](07_flujos_principales.md) | Flujos extremo a extremo con diagramas de secuencia |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, estructura de directorios, seguridad, env vars, dimensionamiento |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | ADR-0001…0014 + revisiones A4 (DD-15…DD-19), supuestos inferidos |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | Inconsistencias (SAD vs A4) y preguntas abiertas priorizadas |

### Extras (complementan, no reemplazan)

| Archivo | Contenido |
|---------|-----------|
| [11_ia_y_vision.md](11_ia_y_vision.md) | Detectores MediaPipe, eventos discretos, re-inferencia, limitaciones, ONNX |
| [12_biometria_y_liveness.md](12_biometria_y_liveness.md) | Verificación 1:1, liveness (pasivo/activo/híbrido), ISO 30107-3, deepfakes/inyección |
| [13_legal_y_cumplimiento_argentina.md](13_legal_y_cumplimiento_argentina.md) | Ley 25.326, AAIP, embeddings sensibles, bases legales, DPIA, caso SRFP |
| [14_observabilidad_y_devops.md](14_observabilidad_y_devops.md) | Tres pilares, SLI/SLO, runbooks, capacity model, CI/CD, backups/DR, pruebas |
| [15_roadmap_y_riesgos.md](15_roadmap_y_riesgos.md) | Roadmap por fases, registro de riesgos, recomendaciones, gestión del cambio |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md), dominios IA/biometría en [11](11_ia_y_vision.md) y [12](12_biometria_y_liveness.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md), [09](09_decisiones_y_supuestos.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Operar → [14](14_observabilidad_y_devops.md), planificar → [15](15_roadmap_y_riesgos.md)
7. Cumplir → [13](13_legal_y_cumplimiento_argentina.md)
8. **Antes de codificar** → [10](10_preguntas_abiertas.md) (resolver inconsistencias SAD vs. A4)

## Resumen Ejecutivo

Plataforma propia **self-hosted** de proctoring **nivel L2.5** (análisis en navegador + verificación biométrica + anti-tampering pasivo) para supervisar evaluaciones universitarias remotas a escala de **700 estudiantes concurrentes** (hasta ~2.100 en picos), con **soberanía de datos** completa. La arquitectura desplaza la IA de visión al navegador (MediaPipe), trata al cliente como sensor no confiable verificado por el backend (FastAPI + PostgreSQL/TimescaleDB), produce **evidencia con cadena de custodia criptográfica** (WORM + firmas encadenadas + audit log inmutable), y **nunca sanciona automáticamente**: toda decisión disciplinaria pasa por revisión humana asíncrona (5–15% de sesiones). El discovery incluye un análisis independiente (A4) que recomienda **empezar simple** (Postgres-como-cola + SSE en el MVP) e incrementar complejidad solo cuando una métrica lo justifique. El principal riesgo no es técnico sino organizacional: sostener la capacidad de revisión humana.

> **Nota crítica**: la fuente contiene dos arquitecturas — el SAD original (RabbitMQ+Redis+Celery, WebSockets+sticky) y la recomendada A4 (Postgres-como-cola, SSE, motor de visión abstraído). El MVP debe seguir la recomendada A4; resolver antes las inconsistencias IN-01…IN-04 de [10_preguntas_abiertas.md](10_preguntas_abiertas.md).
