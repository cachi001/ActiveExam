## Why

Las pantallas más densas del sistema (harness de diagnóstico, revisión académica, detalle de sesión, login) mezclan señales técnicas crudas con información de dominio sin jerarquía visual clara, y el harness de detección admin simula señales de visión sin advertirlo, lo que puede llevar a admins a interpretar datos falsos como reales. C-29 mejora la experiencia y claridad sin tocar funcionalidad ni el motor de visión: baja densidad visual, marca honestamente qué es simulado en el harness, añade explicaciones en lenguaje no técnico, y reencuadra el copy del login como portal del alumno.

## What Changes

- **Harness AdminDetectionHarness**: banner persistente "SEÑALES DE VISIÓN SIMULADAS" (face count, bounding boxes, gaze = valores hardcodeados, no MediaPipe real). Panel de señales crudas reemplazado por tarjetas legibles con etiquetas en lenguaje claro; coordenadas y vectores colapsados bajo "ver detalle técnico" (accordion). Panel de entorno acompañado de breve descripción de qué detecta cada señal y por qué importa. Apoyarse en `<Term>` del glosario C-28 para términos como "gaze", "bounding box", "pose keypoints".
- **Harness AdminDetectionHarness**: encabezado informativo que explica para qué sirve la prueba (verificar que el pipeline detecta lo que debe) y qué debe hacer el admin (moverse, tapar la cámara, cambiar de pestaña).
- **Revisor**: en la tabla de eventos (columna izquierda del grid 3-col), aumentar respiro vertical entre items y agrupar por tipo cuando hay muchos eventos repetidos. En la columna de detalle, organizar la sección de cadena de custodia con acordeón colapsable.
- **SessionDetail**: la sección de "Cadena de custodia criptográfica" (4 pasos `CadenaPaso`) en el grid `lg:grid-cols-2` pasa a ser colapsable en tablet; los valores de hash mono se truncan con "ver completo" inline.
- **Login**: cambiar headline de "Acceso a tu evaluación" a "Portal del alumno" y el subtítulo a texto que describe qué puede hacer el alumno en la plataforma (ver materias, inscribirse a exámenes, gestionar perfil), manteniendo el botón de login federado y el branding `INSTITUTION` de C-27.

## Capabilities

### New Capabilities

- `harness-legibility-layer`: Capa de legibilidad sobre AdminDetectionHarness — banner de simulación, tarjetas de señales con lenguaje claro, explicación de propósito del harness, accordion "ver detalle técnico" para datos crudos.
- `login-portal-reframe`: Reencuadre del copy y propósito de Login.tsx: portal del alumno con descripción de capacidades, sin romper el flujo de login ni el branding de institution.ts.

### Modified Capabilities

- `admin-detection-test-harness` (C-23): el banner de simulación y las tarjetas de señales legibles son un DELTA de comportamiento visible de esta capability — el harness ahora comunica honestamente el estado del motor stub.
- `glossary-config` (C-28): agrega 4 términos nuevos al glosario central (`bounding_box`, `gaze_vector`, `pose_keypoints`, `motor_stub`) para que `<Term>` los pueda servir en el harness.

## Impact

- **Archivos afectados**: `frontend/src/screens/AdminDetectionHarness.tsx`, `frontend/src/screens/Login.tsx`, `frontend/src/screens/Revisor.tsx`, `frontend/src/screens/SessionDetail.tsx`, `frontend/src/config/glossary.ts`.
- **Componentes reutilizados**: `<Term>`, `<GlossaryPanel>`, `<Card>`, `<Badge>`, `<Icon>`, `<SectionTitle>`, `<Button>`. No se crean nuevos átomos.
- **Sin cambios en**: lógica de detección, tipos de datos, API, rutas, permisos, motor de visión.
- **Dependencias de proposal**: C-27 (`INSTITUTION`), C-28 (`Term`, `glossary.ts`).
