# Funcionalidades

> El discovery declara **122 historias en 16 épicas**, sintetizadas en 18 requerimientos funcionales (FR-01…FR-18) y 6 casos de uso (UC-01…UC-06). Aquí se organizan por épica con historias de usuario derivadas de esos FR/UC. Las épicas con menos detalle en la fuente se marcan con **Suposición** donde se infiere la historia.

## Épica 1: Configuración pre-examen (FR-01)

### US-001 — Crear y configurar un examen
**Como** administrador de exámenes
**Quiero** crear un examen, asignar estudiantes habilitados, definir parámetros de monitoreo y cargar la foto de referencia
**Para** que la sesión de supervisión opere con la configuración correcta

**Criterios de aceptación**:
- [ ] CA-1: Puedo crear un examen con nombre, ventana temporal, umbral de score y política de retención.
- [ ] CA-2: Puedo definir qué detectores están activos y sus umbrales.
- [ ] CA-3: Puedo asignar la lista de estudiantes habilitados (solo ellos pueden iniciar).
- [ ] CA-4: Puedo cargar la foto institucional de referencia si no estaba precomputada.
- [ ] CA-5: La calendarización queda visible con anticipación para operaciones.

**Reglas relacionadas**: RN-EX-01, RN-EX-02, RN-EX-03

## Épica 2: Autenticación federada (FR-02)

### US-002 — Ingresar con credenciales institucionales
**Como** estudiante
**Quiero** autenticarme con mis credenciales institucionales habituales
**Para** acceder al examen sin crear cuentas nuevas

**Criterios de aceptación**:
- [ ] CA-1: Ingreso vía Keycloak (SAML/LDAP) y recibo un JWT.
- [ ] CA-2: Soy redirigido al examen habilitado.
- [ ] CA-3: La app valida que mi dispositivo cumple el perfil mínimo; si no, recibo instrucciones claras o se escala a proctor.

**Reglas relacionadas**: RN-AU-01, RN-AU-02, RN-AU-03, RN-GLB-02

## Épica 3: Consentimiento informado (FR-03)

### US-003 — Consentir el tratamiento antes del examen
**Como** estudiante
**Quiero** entender qué se monitorea y consentir explícitamente
**Para** rendir con transparencia y ejercer mis derechos

**Criterios de aceptación**:
- [ ] CA-1: Veo una pantalla dedicada con lenguaje claro (qué se recolecta, cómo, dónde, por cuánto, mis derechos).
- [ ] CA-2: El consentimiento requiere acción afirmativa (sin casillas premarcadas).
- [ ] CA-3: El acuse se persiste con timestamp y hash (registro inmutable).
- [ ] CA-4: Existe una vía alternativa sin biometría si no consiento.

**Reglas relacionadas**: RN-CO-01, RN-CO-02, RN-CO-05

## Épica 4: Verificación biométrica de identidad (FR-04, UC-01)

### US-004 — Verificar mi identidad al inicio
**Como** estudiante
**Quiero** verificar que soy yo mediante biometría
**Para** habilitar el examen

**Criterios de aceptación**:
- [ ] CA-1: Capturo una foto (snapshot) con instrucciones claras.
- [ ] CA-2: El sistema confirma liveness (parpadeo, micro-movimientos, profundidad 3D).
- [ ] CA-3: Se calcula el embedding y se compara 1:1 (distancia coseno) contra la foto institucional.
- [ ] CA-4: Si la distancia < umbral, se habilita el examen y se emite la clave de sesión.
- [ ] CA-5: Hasta 2 reintentos; al 3.º fallo se genera evento crítico y se escala a proctor (no abort).
- [ ] CA-6: La foto y el embedding se persisten con cadena de custodia.

**Reglas relacionadas**: RN-BIO-01…RN-BIO-07, RN-CC-02

## Épica 5: Verificación silenciosa continua (FR-05)

### US-005 — Detectar cambio de identidad durante el examen
**Como** sistema (en nombre de la integridad)
**Quiero** comparar periódicamente el rostro contra el embedding inicial
**Para** detectar suplantación durante el examen

**Criterios de aceptación**:
- [ ] CA-1: Cada inferencia compara el embedding actual contra el inicial.
- [ ] CA-2: Una desviación significativa dispara un evento crítico de "posible cambio de identidad" con atención inmediata del proctor.

**Reglas relacionadas**: RN-BIO-06, RN-EV-04

## Épica 6: Detección de comportamiento (FR-06, UC-02)

### US-006 — Detectar comportamientos anómalos en el navegador
**Como** sistema
**Quiero** detectar rostro ausente, múltiples rostros, mirada, postura, pestaña/foco y monitores adicionales
**Para** generar señales que alimenten el score y la revisión

**Criterios de aceptación**:
- [ ] CA-1: Las señales continuas se convierten en eventos discretos vía reglas de transición (umbrales temporales, fotogramas consecutivos).
- [ ] CA-2: Múltiples rostros (≥2 durante N fotogramas) emite evento de severidad alta, captura evidencia y alerta al proctor en < 500 ms.
- [ ] CA-3: La mirada desviada normal no genera evento; sí lo hace un patrón sostenido hacia un punto fijo.
- [ ] CA-4: Las reglas de transición son configurables por la institución.

**Reglas relacionadas**: RN-EV-01…RN-EV-06

## Épica 7: Generación de eventos (FR-07)

### US-007 — Emitir eventos estructurados firmados
**Como** sistema
**Quiero** producir eventos versionados con severidad y firma
**Para** reconstruir con exactitud qué ocurrió, meses después

**Criterios de aceptación**:
- [ ] CA-1: Cada evento incluye id, session_id, exam_id, tipo, severidad, ts_client, ts_backend, payload JSON y firma.
- [ ] CA-2: El esquema es versionado con compatibilidad hacia atrás.
- [ ] CA-3: El backend valida la firma de cada evento antes de persistir.

**Reglas relacionadas**: RN-EV-05, RN-GLB-01

## Épica 8: Captura de evidencia (FR-08)

### US-008 — Capturar y subir evidencia ante eventos severos
**Como** sistema
**Quiero** capturar una captura (screenshot) ante eventos severos, hashearla y firmarla, y subirla por URL firmada
**Para** producir evidencia defendible sin sobrecargar el backend

**Criterios de aceptación**:
- [ ] CA-1: Un evento severo dispara una captura (screenshot) con hash SHA-256 + firma HMAC del cliente.
- [ ] CA-2: La subida usa URL firmada directo al storage.
- [ ] CA-3: La foto de referencia biométrica sigue la misma cadena de custodia.

**Reglas relacionadas**: RN-CC-01, RN-CC-02, RN-CC-04

## Épica 9: Cadena de custodia (FR-09, UC-06)

### US-009 — Garantizar evidencia defendible y verificable
**Como** revisor / institución
**Quiero** que la evidencia tenga re-hash, re-inferencia, firma maestra y audit log inmutable
**Para** sostener la evidencia ante una apelación

**Criterios de aceptación**:
- [ ] CA-1: El backend re-hashea y firma; un worker firma con clave maestra (RSA-2048/Ed25519).
- [ ] CA-2: Una discrepancia de hash genera evento crítico de "evidencia corrupta o manipulada".
- [ ] CA-3: Ante apelación, se genera un certificado de verificación que un perito externo valida independientemente.
- [ ] CA-4: El audit log es append-only con hashes encadenados.

**Reglas relacionadas**: RN-CC-02, RN-CC-03, RN-CC-07

## Épica 10: Cálculo de score de riesgo (FR-10)

### US-010 — Calcular un score incremental ordenable
**Como** sistema
**Quiero** ponderar eventos por severidad, frecuencia y persistencia
**Para** priorizar la cola de revisión sin emitir un veredicto

**Criterios de aceptación**:
- [ ] CA-1: El score se actualiza incrementalmente (continuous aggregate de TimescaleDB, al minuto).
- [ ] CA-2: Eventos correlacionados pesan más que la suma de sus partes.
- [ ] CA-3: Al cierre, el score final decide si la sesión entra a la cola.

**Reglas relacionadas**: RN-SC-01…RN-SC-05

## Épica 11: Supervisión en vivo (FR-11)

### US-011 — Supervisar exámenes en curso priorizando por riesgo
**Como** proctor en vivo
**Quiero** ver estado de sesiones, alertas en tiempo real, mensajear al estudiante y cerrar sesiones
**Para** atender solo lo que requiere atención

**Criterios de aceptación**:
- [ ] CA-1: El panel prioriza por score de riesgo.
- [ ] CA-2: Las alertas críticas llegan en < 500 ms.
- [ ] CA-3: Puedo enviar mensajes al estudiante, registrar observaciones y forzar el cierre.
- [ ] CA-4: Solo veo exámenes asignados (permisos contextuales); MFA obligatorio.

**Reglas relacionadas**: RN-AU-05, RN-AU-07, RN-EV-04

## Épica 12: Cola de revisión asíncrona (FR-12, UC-04)

### US-012 — Revisar sesiones flaggeadas con contexto completo
**Como** revisor académico
**Quiero** abrir sesiones ordenadas por score con toda la evidencia y contexto
**Para** decidir con criterio y dejar traza

**Criterios de aceptación**:
- [ ] CA-1: La cola se ordena por score descendente; solo veo mi jurisdicción.
- [ ] CA-2: Cada acceso a evidencia se registra en el audit log con propósito declarado.
- [ ] CA-3: Veo línea de tiempo, capturas firmadas, observaciones del proctor, re-inferencia y audit log.
- [ ] CA-4: Emito una de tres decisiones: descartar / escalar / derivar a disciplina.
- [ ] CA-5: La decisión y su fundamento se persisten vinculados a la evidencia (inmutable).

**Reglas relacionadas**: RN-RV-01…RN-RV-07

## Épica 13: Derechos del titular (FR-13, UC-05)

### US-013 — Ejercer derechos sobre mis datos
**Como** estudiante
**Quiero** acceder, rectificar, eliminar y portar mis datos desde la app
**Para** ejercer mis derechos como titular

**Criterios de aceptación**:
- [ ] CA-1: Sin casos abiertos, una solicitud de eliminación borra binarios y embeddings y anonimiza registros, dejando un residual sin datos personales.
- [ ] CA-2: La respuesta es en plazo legal y verificable en auditoría.
- [ ] CA-3: Dispongo de acceso, rectificación y portabilidad.

**Reglas relacionadas**: RN-DSR-01, RN-DSR-03, RN-DSR-04

## Épica 14: Retención automática (FR-14)

### US-014 — Aplicar políticas de retención con holds
**Como** oficial de protección de datos
**Quiero** que las políticas de retención y eliminación se apliquen automáticamente con holds por casos abiertos
**Para** cumplir la normativa sin acción manual

**Criterios de aceptación**:
- [ ] CA-1: La retención configurada se aplica automáticamente.
- [ ] CA-2: Los casos abiertos extienden la retención (hold).

**Reglas relacionadas**: RN-DSR-02

## Épica 15: Resiliencia de red (UC-03)

### US-015 — Resistir cortes de conectividad sin pérdida
**Como** estudiante con conexión inestable
**Quiero** que mis eventos se bufferen y reenvíen al reconectar
**Para** no perder evidencia ni ser penalizado injustamente

**Criterios de aceptación**:
- [ ] CA-1: Cortes < 5 min no generan pérdida; los eventos del buffer se reenvían en orden sin duplicación.
- [ ] CA-2: Cortes > 5 min generan evento crítico al reconectar.

**Reglas relacionadas**: RN-HB-02, RN-HB-03, RN-HB-04, RN-HB-05

## Épica 16: Reportes y analytics (FR-15) — Fase 2

### US-016 — Generar reportes post-examen
**Como** coordinador / dirección académica
**Quiero** reportes por examen y por estudiante, distribuciones, exports y métricas de calidad del detector
**Para** detectar outliers y medir la calidad del sistema

**Criterios de aceptación**:
- [ ] CA-1: Reportes por examen y por estudiante con distribución estadística para detectar outliers.
- [ ] CA-2: Exports y sumario institucional.

**Reglas relacionadas**: RN-SC-04

## Épica 17 (Fase 2): Análisis de audio (FR-16)
**Suposición:** detección de voces múltiples, diferida por privacidad.

## Épica 18 (Fase 2): Integración LMS (FR-17)
**Suposición:** embedding/LTI/flujo coordinado con el sistema de evaluación institucional.

## Épica 19 (Fase 3): Multi-tenancy (FR-18)
**Suposición:** aislamiento por institución para oferta como servicio.
