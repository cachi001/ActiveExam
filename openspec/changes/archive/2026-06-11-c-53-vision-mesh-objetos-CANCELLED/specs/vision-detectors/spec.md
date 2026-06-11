# Spec — vision-detectors (delta C-53)

> Suma Object Detection como cuarto detector de visión, ejecutándose en el mismo runtime WASM+WebGL detrás del motor abstraído.

## ADDED Requirements

### Requirement: Cuarto detector — Object Detection
El motor SHALL ejecutar un detector de objetos adicional a los tres existentes (Face Detection, Face Mesh, Pose), produciendo bounding boxes con etiqueta y score de confianza por objeto. La cadencia del detector de objetos SHALL poder submuestrearse respecto del bucle de frames principal si el costo de cómputo lo exige, y un fallo del detector de objetos NO SHALL interrumpir a los demás detectores ni al examen (degradación silenciosa).

#### Scenario: Object Detection produce objetos con etiqueta y confianza
- **WHEN** el detector de objetos procesa un fotograma con un objeto visible
- **THEN** produce, por cada objeto, su etiqueta cruda, score de confianza y bounding box normalizado

#### Scenario: fallo del detector de objetos no rompe el resto
- **WHEN** el detector de objetos lanza un error en un frame
- **THEN** Face Detection, Face Mesh y Pose continúan procesando ese frame y el bucle no se interrumpe

#### Scenario: Object Detection es el primer candidato a degradar
- **WHEN** el cliente detecta presión de cómputo (fps por debajo del objetivo)
- **THEN** la cadencia del detector de objetos puede reducirse (submuestreo) antes de degradar Pose o Face Mesh
