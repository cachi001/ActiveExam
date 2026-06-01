## 1. Glosario — términos nuevos (glossary.ts)

- [x] 1.1 Abrir `frontend/src/config/glossary.ts` y agregar la entrada `bounding_box` con `term`, `definition` y `example` siguiendo el patrón de entradas existentes.
- [x] 1.2 Agregar la entrada `gaze_vector` con definición en lenguaje claro (valores -1..1, 0 = frente).
- [x] 1.3 Agregar la entrada `pose_keypoints` con definición (puntos de referencia del cuerpo).
- [x] 1.4 Agregar la entrada `motor_stub` con definición (motor provisional que devuelve valores fijos).
- [x] 1.5 Verificar que TypeScript no reporta error de tipo (`tsc --noEmit`) después de las 4 entradas nuevas.

## 2. Login — reframe como portal del alumno (Login.tsx)

- [x] 2.1 Cambiar el `h1` en `Login.tsx` de "Acceso a tu evaluación" a "Portal del alumno".
- [x] 2.2 Cambiar el subtítulo `p` de "Ingresá con tu cuenta institucional federada para continuar" a "Accedé para ver tus materias, inscribirte a exámenes y gestionar tu perfil académico."
- [x] 2.3 Cambiar el ícono del header del card de `verified_user` a `school`.
- [x] 2.4 Verificar visualmente que el botón de login, el widget de institución (`INSTITUTION.nombre`), los links de nav y el footer de privacidad permanecen sin cambios.

## 3. Harness — banner de simulación (AdminDetectionHarness.tsx)

- [x] 3.1 Crear un componente `<SimulacionBanner>` inline (o bloque JSX) con fondo warning, ícono `warning`, texto "SEÑALES DE VISIÓN SIMULADAS — El motor MediaPipe está en modo demo y devuelve valores fijos. Las señales de navegador (pestaña, pantalla completa, portapapeles) SÍ son reales."
- [x] 3.2 Posicionar el banner como primer elemento del layout del harness, antes del video y de cualquier panel de señales.
- [x] 3.3 Verificar que el banner es visible en `harnessState === 'idle'` (antes de iniciar la cámara).
- [x] 3.4 Verificar que el banner permanece visible con `harnessState === 'running'`.

## 4. Harness — panel de propósito (AdminDetectionHarness.tsx)

- [x] 4.1 Agregar un `<Card>` colapsable con título "¿Para qué sirve esta prueba?" inmediatamente después del banner de simulación.
- [x] 4.2 El contenido del panel debe incluir: objetivo del harness (verificar que el pipeline detecta señales), lista de acciones sugeridas (moverse, tapar cámara, cambiar pestaña, pegar texto, salir de fullscreen), y nota sobre qué es real vs. simulado.
- [x] 4.3 Usar `<Term termKey="motor_stub">motor de detección</Term>` y al menos un término más del glosario en el texto del panel.
- [x] 4.4 El panel puede estar colapsado por defecto (usando `<details>/<summary>` nativo o estado local `useState(false)`).

## 5. Harness — señales de visión legibles (AdminDetectionHarness.tsx)

- [x] 5.1 Renombrar el título del panel "Señales crudas" a "Señales de visión [SIMULADAS]" y agregar `sub="Valores generados por el motor en modo demo"`.
- [x] 5.2 Agregar una tarjeta de interpretación de rostros en lenguaje claro antes del bloque de datos técnicos. La tarjeta muestra: "Se detectó 1 persona frente a la cámara" (success), "No se detectó ninguna persona" (warning), o "Se detectaron N personas" (error), según `face_count`.
- [x] 5.3 Agregar una tarjeta de interpretación de mirada: "Mirando hacia el frente" (success) si `|gaze.x| < 0.15 && |gaze.y| < 0.15`, de lo contrario "Mirando hacia un lado" (warning).
- [x] 5.4 Agregar una tarjeta de cuerpo: "Cuerpo presente" / "Cuerpo no detectado" basada en `poseAvailable`.
- [x] 5.5 Envolver los datos técnicos crudos (bounding boxes, vector gaze numérico, pose keypoints) en un accordion `<details>` con `<summary>Ver detalle técnico (coordenadas)</summary>`.
- [x] 5.6 Hacer que el accordion esté abierto automáticamente (`open` attribute) cuando `face_count !== 1` y el harness está corriendo.
- [x] 5.7 Agregar `<Term termKey="bounding_box">bounding box</Term>` como etiqueta en la sección de bounding boxes, y `<Term termKey="gaze_vector">vector gaze</Term>` en la sección de gaze.

## 6. Harness — señales de entorno con descripción (AdminDetectionHarness.tsx)

- [x] 6.1 En el panel "Señales de entorno", agregar una línea descriptiva debajo del título de cada señal:
  - Foco de ventana: "Detecta si el alumno abandonó la ventana del examen."
  - Cambio de pestaña: "Detecta si el alumno abrió otro sitio o aplicación."
  - Pantalla completa: "Detecta si el alumno salió de la vista de examen completa."
  - Portapapeles: "Detecta si el alumno intentó copiar o pegar contenido."
  - Monitor adicional: "Detecta si hay más de una pantalla conectada."
- [x] 6.2 Agregar un badge o etiqueta "Señal REAL" junto al título del panel "Señales de entorno" para diferenciarlo del panel de visión simulado.

## 7. SessionDetail — cadena de custodia colapsable

- [x] 7.1 Envolver el `<Card>` de cadena de custodia en `SessionDetail.tsx` con un `<details>` nativo. El `<summary>` debe contener el título "Cadena de custodia criptográfica".
- [x] 7.2 Aplicar el atributo `open` por defecto solo en desktop (≥1024px) usando clase condicional o media query CSS. En tablet/mobile el bloque empieza colapsado.
- [x] 7.3 Truncar los valores de hash en `CadenaPaso` a los primeros 12 caracteres con `...` y un botón/span "ver completo" que expanda el hash completo usando estado local `useState(false)` o `<details>` inline.

## 8. Revisor — respiro visual en tabla de eventos

- [x] 8.1 En `Revisor.tsx`, cambiar el padding interno de cada item de la lista de eventos de `p-sm` a `p-md`.
- [x] 8.2 Implementar agrupación de eventos repetidos: si hay 5 o más eventos consecutivos del mismo `tipo`, mostrar un solo item agrupado con badge "N veces" en lugar de N items individuales.
- [x] 8.3 Verificar que la agrupación solo aplica a eventos CONSECUTIVOS del mismo tipo (no todos los del mismo tipo en la sesión).

## 9. Verificación final

- [x] 9.1 Correr `tsc --noEmit` sobre el frontend y confirmar 0 errores de tipo.
- [x] 9.2 Verificar visualmente en el navegador (modo demo/mock) que el banner de simulación es el primer elemento visible en `/admin/detection-test`.
- [x] 9.3 Verificar que el Login muestra "Portal del alumno" como headline y que el flujo de login sigue funcionando (navega a `/alumno/dashboard`).
- [x] 9.4 Verificar que el accordion de datos técnicos empieza cerrado con `face_count === 1` y se abre con `face_count !== 1`.
- [x] 9.5 Verificar que los 4 términos nuevos del glosario aparecen en el `<GlossaryPanel>` si está disponible en alguna pantalla del staff.
- [x] 9.6 Verificar que `SessionDetail` muestra la cadena de custodia colapsada en viewport < 1024px.
