# IA y Visión por Computadora

Complementa `05_reglas_de_negocio.md` (RN-EV) y `09_decisiones_y_supuestos.md` (DD-17). No reemplaza ningún canónico.

## Los tres detectores de MediaPipe

| Detector | Qué produce | Para qué se usa | fps objetivo |
|----------|-------------|-----------------|--------------|
| Face Detection (BlazeFace) | Bounding boxes + score de confianza por rostro | Ausencia de rostro, múltiples rostros, rostros de baja confianza | 5–10 |
| Face Mesh | 468 landmarks faciales densos | Dirección de la mirada (iris) + embedding facial para verificación silenciosa continua | 5–10 |
| Pose | Puntos clave del cuerpo | Posturas compatibles con consulta de material (inclinarse sostenidamente) | 2–5 |

## De inferencia continua a eventos discretos

La IA **no decide "fraude"**: produce señales que una capa de reglas de transición de estado convierte en eventos con severidad. Las reglas usan umbrales temporales, fotogramas consecutivos y patrones sostenidos para evitar falsos positivos por ruido. La mirada desviada es normal (pensar, recordar); solo se vuelve evento cuando el patrón sugiere consulta sostenida hacia un punto fijo fuera de pantalla. Ver tabla de disparadores en `05_reglas_de_negocio.md` (RN-EV-04).

## Ejecución y optimización

- Modelos sobre **WebAssembly** (cómputo casi nativo) + **WebGL** (aceleración GPU), en un **Web Worker** dedicado.
- Comunicación por transferencia de buffers de pixels (sin copias).
- Detección de capacidad inicial ajusta frecuencia o degrada gradualmente.
- **Degradación graceful**: primero baja Pose, luego Face Mesh, y solo si es insuficiente se aborta y escala a proctor.
- Recomendación A3: usar el delegado GPU de MediaPipe Tasks; evaluar **WebGPU** donde el navegador lo soporte, con fallback a WebGL/WASM.

## Limitaciones reales (honestidad arquitectónica)

La detección es **probabilística**. NO detecta directamente:
- Una segunda computadora o celular fuera de cuadro.
- Un cómplice susurrando fuera de cámara.
- Conocimiento memorizado.
- Un adversario técnico que reescribe el cliente.
- Coerción externa.

Por qué: el cliente corre en una máquina no controlada y la cámara solo ve su campo visual. Por eso **ninguna señal de IA aplica sanción automática**: todas alimentan un score y un panel donde una persona pondera el contexto.

## Re-inferencia server-side

El backend re-ejecuta modelos (potencialmente más sofisticados que los del cliente) sobre la captura (frame estático — C-24, DD-24-03) y compara con lo reportado. Una **discrepancia es señal forense de posible tampering**. El output (labels, confidences) se firma sobre la captura exacta como cuarta etapa de la cadena de custodia.

## Falsos positivos vs. falsos negativos

- **Falso positivo** (sesión honesta marcada): combatido con umbrales conservadores y, sobre todo, revisión humana que filtra antes de cualquier sanción.
- **Falso negativo** (fraude no detectado): reducido con múltiples detectores correlacionados y análisis estadístico post-examen; se acepta que no puede llevarse a cero sin disparar los falsos positivos.
- A 700 estudiantes, una tasa de falsos positivos del 2% son ~14 acusaciones potencialmente injustas por examen: por eso el filtro humano es estructural, no opcional.

## Evolución (DD-17)

Motor de visión **abstraído** detrás de una interfaz: MediaPipe en el MVP, ruta a **ONNX Runtime Web** (open standard, WebGPU creciente, control total del pipeline, portabilidad de modelos) sin reescribir el resto.
