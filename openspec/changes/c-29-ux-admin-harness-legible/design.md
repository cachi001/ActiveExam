## Context

El frontend de ActiveExam tiene tres pantallas que acumulan densidad visual o generan confusión semántica:

1. **AdminDetectionHarness** (~1210 líneas): muestra señales crudas de visión (coordenadas normalizadas, vectores gaze, bounding boxes) directamente en la UI sin advertir que el motor MediaPipe está en modo stub — el `detectFaces` real lanza un error y el `catch` en línea 467-470 inyecta `face_count: 1` hardcodeado. Un admin sin contexto técnico puede interpretar "1 rostro detectado, conf. 92.0%" como detección real.

2. **Revisor + SessionDetail**: la tabla de eventos usa `text-label-sm` con muchos items compactos; la sección de cadena de custodia muestra hashes largos en mono en un grid que compite con la columna de eventos en tablet.

3. **Login**: el headline "Acceso a tu evaluación" y el subtítulo "Ingresá con tu cuenta institucional federada" son técnicos e implican que el usuario ya tiene un examen asignado. No describe el portal completo (materias, inscripción, perfil).

Los patrones de extensión ya existen: `<Term>` + `glossary.ts` de C-28, `INSTITUTION` de C-27, átomos de `components.tsx`.

## Goals / Non-Goals

**Goals:**

- Advertir explícita y prominentemente que las señales de visión del harness son SIMULADAS (stub MediaPipe, no detección real).
- Añadir explicaciones en lenguaje no técnico sobre qué hace cada panel del harness y qué debe observar el admin.
- Colapsar los datos técnicos crudos (coordenadas, vectores) bajo accordiones opcionales — visible solo cuando el admin quiera el detalle.
- Agregar respiro vertical en la tabla de eventos de Revisor; truncar hashes en SessionDetail con "ver completo" toggle.
- Reencuadrar Login como portal del alumno: headline + subtítulo que describen las capacidades del portal.
- Extender `glossary.ts` con 4 términos nuevos (`bounding_box`, `gaze_vector`, `pose_keypoints`, `motor_stub`) usados en el harness.

**Non-Goals:**

- Cablear MediaPipe real (eso es C-30).
- Refactor de arquitectura de componentes ni extracción masiva.
- Cambios en lógica de detección, eventos, tipos, rutas o permisos.
- Modificar el diseño visual del login (colores, layout, animaciones).
- Agregar nuevas pantallas.

## Decisions

### DD-29-01: Banner de simulación como alerta visual de primer nivel

**Decisión**: El banner "SEÑALES DE VISIÓN SIMULADAS" se coloca ANTES del video y el panel de señales en el harness, usando `tone="warning"` de `<Badge>` o una `<Card>` con borde naranja prominente. No puede estar enterrado entre señales.

**Alternativas consideradas**:
- Tooltip en el título del panel: demasiado sutil, se ignora.
- Sección al pie: el admin ya habrá leído los datos falsos antes de verla.
- Alert banner sticky en el header de la pantalla: elegido — primer elemento visible, imposible pasar por alto.

**Rationale**: El principio de honestidad informacional del sistema (L2.5 no sanciona automático; cliente = sensor no confiable) se extiende a la UI de diagnóstico. Marcar SIMULADO es tan crítico como no sancionar automáticamente.

### DD-29-02: Accordion "ver detalle técnico" para datos crudos

**Decisión**: Las secciones de bounding boxes, vector gaze y pose keypoints se colapsan por defecto. El estado abierto/cerrado es local (useState, no persiste). El título del accordion en lenguaje claro: "Datos técnicos de detección (coordenadas)".

**Alternativas consideradas**:
- Eliminar los datos crudos: innecesario — son útiles para debugging de un agente técnico.
- Tabs separados (técnico / legible): más overhead de implementación; el accordion satisface el caso.

**Rationale**: El admin no técnico ve la interpretación (1 rostro, mirando al frente); el admin técnico puede expandir y ver las coordenadas. Mismo dato, dos audiencias.

### DD-29-03: Tarjetas de señal en lenguaje claro sobre el raw panel

**Decisión**: El panel "Señales crudas" se renombra a "Señales de visión [SIMULADAS]" y se reestructura con tarjetas de interpretación en primer lugar:
- Rostros: "Se detectó 1 persona frente a la cámara" / "No se detectó ninguna persona" / "Se detectaron 2 o más personas"
- Mirada: "Mirando hacia el frente (dentro del ángulo permitido)" / "Mirando hacia un costado"
- Pose: "Cuerpo presente / no detectado"

Las tarjetas usan los átomos existentes (`Badge`, `Icon`, colores semánticos).

### DD-29-04: Panel de propósito del harness

**Decisión**: Se agrega un `<Card>` de propósito al tope del harness (debajo del banner de simulación) con:
- Qué es esta pantalla: "Esta herramienta verifica que el sistema detecta señales correctamente antes de un examen real."
- Qué debe hacer el admin: lista de acciones de prueba (moverse, tapar la cámara, cambiar de pestaña, pegar texto).
- Qué señales son reales vs. simuladas: navegador = real, visión = simulada (stub).

Este panel usa `<Term>` para los términos del glosario.

### DD-29-05: Sección colapsable en SessionDetail (cadena de custodia)

**Decisión**: El bloque `<Card>` de cadena de custodia en `SessionDetail.tsx` se envuelve con un toggle `<details>/<summary>` nativo (sin dependencias externas) con el título "Cadena de custodia criptográfica". Por defecto: expandido en desktop, colapsado en tablet/mobile (media query CSS o clase condicional).

**Alternativas**: un botón React con useState — válido pero más verbose que `<details>` nativo con `open` attribute.

### DD-29-06: Respiro visual en Revisor sin cambiar layout

**Decisión**: En la tabla de eventos (columna izquierda), aumentar el `gap` y `p` de cada item de `p-sm` a `p-md`. No cambiar el layout 3-col — es correcto en desktop. En tablet, el panel de detalle pasa a estar debajo de la cola usando `lg:grid-cols-3` que ya está (comportamiento correcto, solo ajuste de spacing).

### DD-29-07: Términos nuevos en glossary.ts

**Decisión**: Agregar en `frontend/src/config/glossary.ts` exactamente 4 términos con el mismo patrón clave→`GlossaryEntry` que los existentes:
- `bounding_box`: "Área rectangular que rodea un objeto detectado..."
- `gaze_vector`: "Estimación de hacia dónde mira una persona..."
- `pose_keypoints`: "Puntos de referencia del cuerpo..."
- `motor_stub`: "Implementación provisional del motor de visión que devuelve valores fijos..."

### DD-29-08: Login reframe — solo copy, sin layout

**Decisión**: Cambiar únicamente:
- `h1`: "Acceso a tu evaluación" → "Portal del alumno"
- `p` de subtítulo: "Ingresá con tu cuenta institucional federada para continuar" → "Accedé para ver tus materias, inscribirte a exámenes y gestionar tu perfil académico."
- Ícono del logo: `verified_user` → `school` (más semántico para portal estudiantil).

El resto del componente (layout, botón, `INSTITUTION`, nav links, footer) queda intacto.

## Risks / Trade-offs

- **[Riesgo] El banner de simulación puede alarmar al equipo técnico** que sabe que el stub es intencional → Mitigación: el banner incluye "en esta demo" + link conceptual a la sección de la checklist que confirma qué señales son reales.
- **[Riesgo] Accordion colapsa datos que a veces son los más relevantes** para debugging → Mitigación: por defecto abierto si el harness acaba de detectar un error (face_count ≠ 1 o gaze fuera de rango).
- **[Trade-off] El reframe de Login es solo copy** — no cambia el flujo de autenticación ni el enrutamiento. Si el usuario entra sin un examen asignado, la lógica de `ingresar()` ya maneja el caso con el primer examen disponible. No hay impacto funcional.

## Open Questions

- ¿El accordion de cadena de custodia en SessionDetail debe estar cerrado por defecto en todos los tamaños, o solo en mobile/tablet? → Decisión del implementador; la spec dice "colapsable en tablet", desktop abierto es razonable.
- ¿El banner de simulación debe aparecer también en modo `harnessState === 'idle'` (antes de iniciar la cámara)? → Sí: el banner es sobre el estado del motor, no del estado de la cámara. Siempre visible.
