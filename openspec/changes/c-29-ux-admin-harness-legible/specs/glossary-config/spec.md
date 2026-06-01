## MODIFIED Requirements

### Requirement: Glosario extiende términos técnicos de visión y stub
El módulo `frontend/src/config/glossary.ts` SHALL incluir definiciones para al menos los siguientes términos adicionales, en el mismo formato de objeto `GlossaryEntry` con las propiedades `term`, `definition`, `example` (opcional) y `seeAlso` (opcional):

- **`bounding_box`**: "Área rectangular que rodea a una persona o rostro detectado por la cámara. Se expresa como coordenadas x, y y dimensiones width, height normalizadas entre 0 y 1 (0 = borde izquierdo/superior, 1 = borde derecho/inferior de la imagen)."
- **`gaze_vector`**: "Estimación de la dirección de la mirada de una persona. Se expresa como dos valores (x, y) entre -1 y 1: valores cercanos a 0 indican que la persona mira al frente; valores extremos indican que mira hacia los costados o arriba/abajo."
- **`pose_keypoints`**: "Puntos de referencia del cuerpo de una persona (hombros, codos, manos, etc.) detectados por un modelo de visión artificial. Su presencia confirma que hay una persona entera visible, no solo el rostro."
- **`motor_stub`**: "Implementación provisional del motor de visión que devuelve valores fijos (hardcodeados) en lugar de analizar la cámara real. Se usa mientras el motor MediaPipe real no está disponible en el entorno de demo."

#### Scenario: Términos nuevos disponibles para componente Term
- **WHEN** se importa `GLOSSARY` desde `frontend/src/config/glossary.ts`
- **THEN** `GLOSSARY['bounding_box']`, `GLOSSARY['gaze_vector']`, `GLOSSARY['pose_keypoints']` y `GLOSSARY['motor_stub']` existen y tienen al menos la propiedad `definition` no vacía

#### Scenario: Términos nuevos aparecen en GlossaryPanel
- **WHEN** el usuario abre el `<GlossaryPanel>` desde cualquier pantalla que lo incluya
- **THEN** los 4 términos nuevos son visibles en el panel con sus definiciones

#### Scenario: Componente Term usa términos nuevos sin error
- **WHEN** se renderiza `<Term termKey="bounding_box">bounding box</Term>` en el harness
- **THEN** el tooltip muestra la definición del término sin error de tipo ni clave ausente
