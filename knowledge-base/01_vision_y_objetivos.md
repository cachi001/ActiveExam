# Visión y Objetivos

## Propósito del sistema

Plataforma propia (self-hosted) de proctoring para supervisión asistida por IA de evaluaciones universitarias remotas, que permite a una institución sostener su oferta evaluativa a distancia con integridad académica defendible, costos sostenibles y soberanía de datos.

El sistema cubre el ciclo completo de una evaluación supervisada: configuración pre-examen, verificación de identidad biométrica, monitoreo continuo en el navegador del estudiante, generación de eventos y evidencia con cadena de custodia criptográfica, supervisión humana en vivo y revisión humana asíncrona posterior con derivación a proceso disciplinario cuando corresponde. La filosofía rectora es la "honestidad arquitectónica": el sistema detecta comportamientos anómalos con calidad razonable y produce evidencia defendible, pero **nunca** sanciona automáticamente ni pretende prevenir el fraude de forma absoluta. Nivel de proctoring adoptado: **L2.5** (análisis en cliente + verificación biométrica + anti-tampering pasivo).

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|-------|--------------------|-----------------------|
| Estudiante | Rendir sin fricción ni ansiedad | Claridad sobre qué se monitorea; respeto a privacidad/derechos; soporte si algo falla; no ser acusado injustamente |
| Proctor en vivo | Atender solo lo que requiere atención (no observar a 700 personas) | Panel priorizado por riesgo, alertas accionables, capacidad de intervenir y cerrar sesiones |
| Revisor académico | Decidir con criterio y evidencia sólida sobre sesiones flaggeadas | Línea de tiempo, capturas firmadas, re-inferencia y audit log en una sola vista |
| Coordinador operativo | Que los exámenes corran sin incidentes y la cola de revisión no se acumule | Asignar proctors, monitorear backlog, escalar a TI |
| Oficial de protección de datos (DPO) | Que el tratamiento sea legal y los derechos del titular se cumplan | DPIA, registro de solicitudes, retención automática, eliminación verificable |
| Administrador del sistema | Disponibilidad y recuperabilidad | Observabilidad rica, runbooks, despliegues seguros, backups probados |
| Administrador de exámenes | Configurar exámenes correctamente | Definir parámetros de monitoreo, asignar estudiantes, cargar foto de referencia |
| Institución (patrocinador) | Resolver el dolor a costo predecible, sin riesgo reputacional | Activo institucional reutilizable; soberanía; opción de expansión multi-institucional |

## Alcance v1.0 (MVP — Fase 1)

El sistema SÍ hace:

- Configuración pre-examen: el admin crea exámenes, asigna estudiantes habilitados, define parámetros de monitoreo (umbrales, detectores activos) y carga la foto institucional de referencia.
- Autenticación federada con credenciales institucionales (Keycloak, SAML/LDAP).
- Consentimiento informado versionado, con acuse persistido (timestamp + hash).
- Verificación biométrica de identidad: captura de foto (snapshot) → liveness → embedding facial → comparación 1:1 contra foto institucional; hasta 2 reintentos; al 3.º fallo escala a proctor.
- Verificación silenciosa continua del rostro contra el embedding inicial durante el examen.
- Detección de comportamiento en el navegador: rostro ausente, múltiples rostros, dirección de mirada, postura, cambio de pestaña/pérdida de foco, monitores adicionales.
- Generación de eventos estructurados versionados, con severidad y firma.
- Captura de evidencia (screenshots) ante eventos severos, con hash + firma del cliente y subida por URL firmada.
- Cadena de custodia: re-hash y firma backend, re-inferencia server-side, firma maestra, audit log inmutable.
- Cálculo incremental de score de riesgo (ponderado por severidad, frecuencia y persistencia).
- Panel de supervisión en vivo (proctor): estado de sesiones, alertas en tiempo real, mensajería al estudiante, observaciones, cierre forzado.
- Cola de revisión asíncrona ordenada por score, con vista de contexto y decisiones terminales (descartar / escalar / derivar a disciplina).
- Derechos del titular (acceso, rectificación, eliminación, portabilidad) y retención automática con holds por casos abiertos.
- Observabilidad, seguridad y privacidad desde el día uno; runbooks operacionales.

## Fuera de alcance

El sistema NO:

- **Opera el examen mismo**: la interfaz de preguntas/respuestas es del LMS institucional; el proctoring se integra (iframe/LTI/flujo coordinado) pero no se acopla a un LMS concreto.
- **Califica las respuestas**: la corrección y la nota son del LMS o del docente.
- **Toma decisiones disciplinarias**: flaggea, documenta y pone a disposición; la sanción es **siempre humana**.
- **Transmite video continuo** al servidor: los pixels permanecen en el dispositivo salvo capturas puntuales.
- **Instala software** en la máquina del estudiante: corre íntegramente en el navegador (limita el anti-tampering al nivel L2.5).
- **Detecta medios externos no observables**: una segunda computadora, un celular fuera de cuadro o un cómplice susurrando no se capturan directamente (solo heurísticamente y post-examen).
- **Sirve para certificaciones de alto impacto**: L2.5 corresponde a evaluaciones académicas internas de impacto medio.
- **Incluye servicios humanos del proveedor**: proctors, revisores y coordinadores son personal de la institución.

### Features diferidas (Fase 2/3)
- Análisis de audio (voces múltiples) — Fase 2.
- Integración LMS específica (LTI/embedding) — Fase 2.
- Reportes y analytics avanzados — Fase 2.
- Multi-tenancy (aislamiento por institución) — Fase 3.

## Métricas de éxito

| Dimensión | KPI | Definición de éxito |
|-----------|-----|---------------------|
| Producto / detección | Tasa de falsos positivos post-revisión | Tendencia decreciente tras calibración (Fase 2) |
| Producto / detección | Cobertura de vectores en alcance | Eventos generados para los vectores declarados detectables |
| Producto / detección | Precisión de verificación biométrica | Falsos rechazos por debajo de umbral aceptable |
| Operación | Disponibilidad en ventana de examen | ≥ 99,9% |
| Operación | Incidentes graves por trimestre | Por debajo del umbral acordado |
| Operación | Backlog de revisión humana | Sin acumulación sostenida; sesiones revisadas en plazo |
| Negocio | Costo por estudiante evaluado | Decreciente y por debajo de la alternativa comercial |
| Experiencia | Satisfacción del estudiante | Fricción y ansiedad percibidas bajas |
| Legitimidad | Casos disciplinarios sostenidos al apelarse | Alta proporción confirmada; evidencia no impugnada con éxito |
| Privacidad | Incidentes de privacidad | Cero |

**La pregunta que define el éxito**: al cabo de un año de operación productiva, ¿puede la institución sostener su programa de evaluaciones remotas con confianza, a volumen significativo, sin incidentes de privacidad y con casos disciplinarios que se sostienen cuando se apelan?
