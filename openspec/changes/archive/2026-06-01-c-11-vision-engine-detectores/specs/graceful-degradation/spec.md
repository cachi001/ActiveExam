# Spec — graceful-degradation

> Degradación graceful ante hardware insuficiente: baja Pose → Face Mesh → escala a proctor, nunca abort silencioso (RN-GLB-02, RN-GLB-03, `11_ia_y_vision.md`).

## ADDED Requirements

### Requirement: Degradación escalonada ante hardware insuficiente
Ante capacidad de cómputo insuficiente, el pipeline SHALL degradar en orden: primero bajar/desactivar Pose, luego Face Mesh; solo si sigue siendo insuficiente SHALL escalar a un proctor. El pipeline SHALL NOT abortar el examen de forma silenciosa (RN-GLB-02, RN-GLB-03).

#### Scenario: Baja Pose primero ante hardware limitado
- **WHEN** la detección de capacidad indica que el dispositivo no sostiene los tres detectores
- **THEN** el pipeline baja primero Pose y continúa con Face Detection y Face Mesh

#### Scenario: Escalada a proctor cuando la degradación no alcanza
- **WHEN** tras bajar Pose y Face Mesh el dispositivo sigue siendo insuficiente
- **THEN** el pipeline escala a un proctor sin abortar el examen de forma silenciosa

### Requirement: Detección de capacidad inicial ajusta la frecuencia
El pipeline SHALL detectar la capacidad del dispositivo al inicio y ajustar la frecuencia de los detectores o degradar gradualmente en consecuencia.

#### Scenario: Ajuste de fps según capacidad detectada
- **WHEN** se detecta la capacidad del dispositivo al iniciar el monitoreo
- **THEN** el pipeline ajusta los fps de los detectores o degrada según esa capacidad
