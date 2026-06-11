# vision-engine-abstraction

## Purpose

Define la interfaz `VisionEngine` que abstrae el motor de visión detrás de un puerto: MediaPipe en el MVP, ruta a ONNX Runtime Web en el futuro (DD-17). Garantiza que las reglas de transición, los detectores de contexto y la capa de transporte no dependan de la implementación concreta del motor, de modo que cambiarlo sea reemplazar la implementación sin reescribir el resto del pipeline.

## Requirements

### Requirement: Motor de visión detrás de una interfaz abstracta
El pipeline SHALL acceder al motor de visión únicamente a través de una interfaz `VisionEngine` abstracta; ningún componente de reglas de transición ni de transporte SHALL depender directamente de MediaPipe (DD-17).

#### Scenario: Reglas de transición operan sin conocer la implementación
- **WHEN** las reglas de transición consumen señales del motor
- **THEN** lo hacen a través de la interfaz `VisionEngine` sin referenciar tipos ni APIs específicas de MediaPipe

### Requirement: Implementación MediaPipe en el MVP, ruta a ONNX Runtime Web
La interfaz `VisionEngine` SHALL tener una implementación basada en MediaPipe para el MVP y SHALL permitir sustituirla por una implementación basada en ONNX Runtime Web sin reescribir las reglas de transición ni el transporte.

#### Scenario: Sustituir la implementación del motor sin tocar el resto
- **WHEN** se reemplaza la implementación MediaPipe por una de ONNX Runtime Web detrás de la misma interfaz
- **THEN** las reglas de transición, los detectores de contexto y el transporte siguen operando sin cambios
