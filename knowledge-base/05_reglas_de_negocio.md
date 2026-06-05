# Reglas de Negocio

Cada regla tiene un código único `RN-{DOMINIO}-{NN}` para trazabilidad. Las reglas se derivan del discovery; las marcadas con **Suposición** se infieren de la lógica descrita pero no están literalmente numeradas en la fuente.

## Dominio: Autenticación e identidad (RN-AU)

- **RN-AU-01**: El estudiante ingresa con credenciales institucionales (las mismas del LMS y webmail) vía federación SAML/LDAP a través de Keycloak. No hay autenticación propia.
- **RN-AU-02**: Tras autenticar, el estudiante recibe un token JWT y es redirigido al examen habilitado.
- **RN-AU-03**: El JWT se valida localmente contra la clave pública de Keycloak (JWKS cacheado) en cada request HTTP (firma, expiración, audience, issuer) y en WebSockets en el handshake y periódicamente durante la sesión.
- **RN-AU-04**: Los access tokens duran 15–60 minutos; los refresh tokens rotan en cada uso.
- **RN-AU-05**: MFA obligatorio para roles con acceso a evidencia o administración (proctor, revisor, coordinador, administradores). TOTP mínimo, WebAuthn recomendado.
- **RN-AU-06**: Los usuarios se provisionan just-in-time desde el IdP institucional.
- **RN-AU-07**: El alcance de los permisos depende del rol: el proctor tiene **alcance global** sobre todos los exámenes activos; el revisor está acotado a su jurisdicción (permiso contextual). *(C-50: la restricción de asignación del proctor fue revertida por decisión del dueño del producto; la relajación del mínimo privilegio queda justificada en el DPIA — C-01.)*

## Dominio: Configuración de examen (RN-EX)

- **RN-EX-01**: El admin crea exámenes, asigna la lista de estudiantes habilitados, define parámetros de monitoreo (umbrales, detectores activos) y carga la foto institucional de referencia si no estaba precomputada.
- **RN-EX-02**: La calendarización se carga con anticipación para que operaciones sepa cuándo estará bajo SLA estricto.
- **RN-EX-03**: Solo los estudiantes habilitados/asignados pueden iniciar la sesión del examen.

## Dominio: Consentimiento y privacidad (RN-CO)

- **RN-CO-01**: Antes de habilitar el examen el estudiante debe atravesar un flujo de consentimiento informado con texto **versionado**; el acuse se persiste con timestamp y hash.
- **RN-CO-02**: El consentimiento debe ser libre, expreso e informado, con acción afirmativa (no casillas premarcadas).
- **RN-CO-03**: No se transmite video continuo; los pixels permanecen en el dispositivo del estudiante salvo clips puntuales asociados a eventos (minimización por defecto).
- **RN-CO-04**: Los datos biométricos se usan **solo** para verificar identidad en el examen; prohibida la reutilización para cualquier otra finalidad (finalidad acotada y declarada).
- **RN-CO-05**: Debe ofrecerse una vía alternativa de verificación de identidad sin biometría (p. ej. proctor humano en vivo) para quien no consienta, de modo que el consentimiento sea genuinamente libre. *(Recomendación legal Argentina; ver `1A_legal_y_cumplimiento_argentina.md`.)*

## Dominio: Verificación biométrica (RN-BIO)

- **RN-BIO-01**: La verificación de identidad ocurre en cuatro pasos: (1) captura de video 3–5 s, (2) liveness, (3) cálculo de embedding facial, (4) comparación 1:1 por distancia coseno contra el embedding precomputado.
- **RN-BIO-02**: Si la distancia coseno está bajo el umbral configurado, la verificación es exitosa y se habilita el examen (se emite la clave de sesión rotativa).
- **RN-BIO-03**: El umbral se configura **conservadoramente**: rechazar a un legítimo es peor que aceptar a un impostor en este paso (el impostor aún debe superar la verificación continua).
- **RN-BIO-04**: Se permiten hasta **2 reintentos**; al **3.º fallo** se genera un **evento crítico** y se escala a un proctor humano (nunca se aborta automáticamente).
- **RN-BIO-05**: Sin liveness el bypass es trivial (mostrar una foto/video del compañero); el liveness es prerrequisito obligatorio de la verificación.
- **RN-BIO-06**: Durante todo el examen, la **verificación silenciosa continua** compara el embedding del rostro detectado contra el inicial; una desviación significativa dispara un evento crítico de "posible cambio de identidad".
- **RN-BIO-07**: El embedding se persiste cifrado at-rest; el clip de verificación sigue la misma cadena de custodia que cualquier evidencia.
- **RN-BIO-08**: El embedding se elimina al egreso del estudiante de la institución.

## Dominio: Detección y eventos (RN-EV)

- **RN-EV-01**: La IA no decide "fraude": produce señales que una capa de reglas de transición de estado convierte en eventos con severidad.
- **RN-EV-02**: Las reglas de transición usan umbrales temporales / fotogramas consecutivos / patrones sostenidos para evitar falsos positivos por ruido instantáneo. (Ej.: la ausencia de rostro en un solo fotograma no es evento; lo es si se sostiene > 3 s.)
- **RN-EV-03**: Las reglas de transición son **configurables por la institución**.
- **RN-EV-04**: Disparadores y severidad típica por tipo de evento:

  | Tipo de evento | Disparador (regla de transición) | Severidad | Tratamiento |
  |----------------|----------------------------------|-----------|-------------|
  | Rostro ausente | Sin rostro > 3 s sostenidos | Media | Acumula; alerta moderada |
  | Múltiples rostros | ≥2 rostros durante N fotogramas consecutivos | Alta | Captura de evidencia automática |
  | Mirada desviada sostenida | Iris fuera del marco hacia un punto fijo | Media | Acumula; contexto para revisión |
  | Cambio de pestaña / pérdida de foco | Evento de visibilidad del navegador | Media | Registro; suma al score |
  | Monitor adicional detectado | API de pantallas (donde el navegador lo permite) | Alta | Evidencia + alerta |
  | Posible cambio de identidad | Embedding actual diverge del inicial | Crítica | Atención inmediata del proctor |
  | Tampering / cámara virtual | Heurística de integridad (varianza de pixels, DevTools) | Alta | Log forense, **nunca abort automático** |
  | Corte de conectividad prolongado | Reconexión tras > 5 min sin heartbeats | Crítica | Evento crítico al reconectar |
  | Heartbeat (no es anomalía) | Cada 5 s, firmado con HMAC | Baseline | Prueba de vida de la sesión y el detector |

- **RN-EV-05**: Cada evento incluye: identificador único, `session_id`, `exam_id`, tipo, severidad, `ts_client`, `ts_backend` (completado al recibir), payload JSON y firma. El esquema es versionado (`schema_version`) con compatibilidad hacia atrás.
- **RN-EV-06**: La mirada desviada normal (pensar, mirar al techo) **no** es evento; solo lo es cuando el patrón sugiere consulta sostenida hacia un punto fijo fuera de pantalla.

## Dominio: Heartbeats y resiliencia (RN-HB)

- **RN-HB-01**: Cada 5 s el cliente envía un heartbeat firmado con HMAC; el backend valida la firma.
- **RN-HB-02**: Los eventos se almacenan en un buffer circular local (IndexedDB) resistente a cortes.
- **RN-HB-03**: Un corte de conectividad de hasta 5 min **no** genera pérdida: al reconectar, el cliente reenvía los eventos del buffer en orden con `last_event_id`, sin pérdida ni duplicación (deduplicación por `event_id`, exactly-once lógico).
- **RN-HB-04**: Cortes > 5 min generan un evento crítico al reconectar.
- **RN-HB-05**: La reconexión usa backoff exponencial con jitter del 20% para evitar el "thundering herd".

## Dominio: Scoring (RN-SC)

- **RN-SC-01**: El score de riesgo es una **prioridad para la cola de revisión, no un veredicto**.
- **RN-SC-02**: Se calcula incrementalmente durante el examen, ponderando cada evento por severidad, frecuencia y persistencia.
- **RN-SC-03**: Un patrón sostenido pesa más que un pico aislado; eventos correlacionados (mirada desviada + pérdida de foco simultáneas) pesan más que la suma de sus partes.
- **RN-SC-04**: Al cierre del examen, una tarea asíncrona calcula el score final; si supera el umbral institucional, la sesión entra a la cola de revisión.
- **RN-SC-05**: La filosofía de calibración prioriza minimizar falsos positivos en la detección automática (el filtro humano recupera los verdaderos positivos); los umbrales del MVP son conservadores por defecto y se afinan con datos reales en Fase 2.

## Dominio: Evidencia y cadena de custodia (RN-CC)

- **RN-CC-01**: Solo los eventos de severidad alta o crítica disparan captura automática de evidencia. **C-24 (DD-24-01)**: el artefacto capturado es un **screenshot (frame único PNG)**, no un clip de 5–10 s. Se añade un segundo disparador: **heartbeat periódico de baja frecuencia** (cadencia configurable por examen, default 2 min, tope mínimo 30 s) que provee una línea base de la sesión para revisión humana (DD-24-02). No se graba video continuo bajo ninguna circunstancia (proporcionalidad L2.5, Ley 25.326).
- **RN-CC-02**: La cadena de custodia tiene cuatro etapas criptográficas **acumulativas** (las firmas no se reemplazan, se encadenan): (1) cliente: SHA-256 + firma HMAC con clave de sesión rotativa; (2) backend al recibir: valida firma cliente, recalcula hash, persiste metadata, deposita en bucket + audit log; (3) worker asíncrono: re-descarga, 3.ª verificación de hash, firma con clave maestra asimétrica (RSA-2048 / Ed25519); (4) re-inferencia **estática sobre el frame** (C-24, DD-24-03): detección de rostros/objetos en la imagen firmada por el backend; la discrepancia con lo reportado por el cliente es señal forense, no veredicto automático.
- **RN-CC-03**: Si el hash recalculado no coincide en cualquier etapa, se genera un evento crítico de "evidencia corrupta o manipulada".
- **RN-CC-04**: Las subidas de binarios van **directo al storage** mediante URLs firmadas (no pasan por el backend).
- **RN-CC-05**: La descarga de un clip requiere URL firmada que expira en 15 minutos.
- **RN-CC-06**: El bucket de evidencia usa Object Lock en modo Compliance (WORM): no se puede modificar ni borrar durante la retención, ni siquiera por el propietario.
- **RN-CC-07**: Ante apelación, el sistema genera un certificado de verificación de la cadena de firmas que un perito externo puede validar independientemente.
- **RN-CC-08 (NFR)**: Cero pérdida de eventos confirmados y de evidencia; la re-inferencia y la firma de evidencia son tareas que **no toleran pérdida**.

## Dominio: Revisión humana y disciplina (RN-RV)

- **RN-RV-01**: Entre el 5% y el 15% de las sesiones requieren revisión (35–105 sesiones por examen de 700; 10–20 min cada una).
- **RN-RV-02**: La cola se ordena por score descendente (mayor primero).
- **RN-RV-03**: Cada apertura de sesión por un revisor queda registrada en el audit log con **propósito declarado**.
- **RN-RV-04**: El revisor accede al contexto completo: línea de tiempo de eventos, **screenshots firmados** (C-24: ya no clips de video), heartbeats de línea base, observaciones del proctor en vivo, output de re-inferencia estática server-side y audit log de accesos previos. **Límite L2.5 que los revisores deben conocer**: la evidencia automática es un **frame único** (sin contexto temporal). No permite re-verificar liveness ni movimiento. Si el caso requiere contexto dinámico que no puede resolverse con el frame y la línea de eventos, el revisor DEBE **escalar** (RN-RV-05) en lugar de decidir solo con la imagen. Este límite se comunica en el acuerdo de proctoring (C-01) y en la capacitación de revisores (C-02).
- **RN-RV-05**: El revisor emite **una de tres** resoluciones terminales: descartar (falso positivo), escalar (investigación adicional) o derivar a proceso disciplinario formal.
- **RN-RV-06**: La decisión y su fundamento se persisten vinculados a la evidencia mediante referencias inmutables.
- **RN-RV-07**: **Ninguna sanción es automática**: la decisión disciplinaria final es siempre humana.

## Dominio: Retención y derechos del titular (RN-DSR)

- **RN-DSR-01**: El estudiante puede ejercer acceso, rectificación, eliminación y portabilidad desde la aplicación.
- **RN-DSR-02**: Las políticas de retención y eliminación se aplican automáticamente, con **holds** que extienden la retención mientras haya casos abiertos.
- **RN-DSR-03**: Ante una solicitud de eliminación de un estudiante **sin casos abiertos**, el sistema elimina binarios y embeddings y anonimiza registros, conservando un registro residual sin datos personales; la respuesta es en plazo legal y verificable en auditoría.
- **RN-DSR-04**: El derecho de oposición a decisiones automatizadas se cumple por arquitectura, ya que ninguna sanción es automática.

## Dominio: Excepciones globales

- **RN-GLB-01**: El cliente es un sensor con sesgos conocidos, **no** una fuente de verdad: toda evidencia que sube se trata como entrada potencialmente hostil (zero trust).
- **RN-GLB-02**: Ante fallos del dispositivo o capacidad insuficiente, se comunica el problema con instrucciones claras o se escala a un proctor — **nunca se aborta** el examen abruptamente.
- **RN-GLB-03**: Degradación graceful en dispositivos limitados: primero baja Pose, luego Face Mesh, y solo si es insuficiente se aborta y escala a proctor.
- **RN-GLB-04**: Los despliegues a producción solo ocurren **fuera** de ventanas de examen activo.
- **RN-GLB-05**: Una funcionalidad no observable, no monitoreada ni recuperable **no se considera "lista"** (Definition of Done).
- **RN-GLB-06**: El desarrollo no avanza más allá de la Fase 0 sin el Acuerdo de Nivel de Proctoring firmado y el DPIA completado.
