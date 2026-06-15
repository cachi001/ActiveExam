# biometric-presentation-attack-defense Specification

## ADDED Requirements

### Requirement: Defensa anti-presentación combinada (reto-respuesta + pasivo + cámara virtual)

El sistema SHALL combinar, como defensa contra ataques de presentación (ISO/IEC 30107-3), las siguientes capas client-side: (1) **reto-respuesta activo** con los tres gestos secuenciales (`parpadear`, `girar_cabeza` con dirección aleatoria, `sonreír`) en orden barajado por intento; (2) **señales pasivas** de liveness (parpadeo, micro-movimientos y profundidad 3D coherente de los 468 landmarks); y (3) **detección de cámara virtual / inyección de pipeline**. Una imagen estática (foto) NO SHALL superar la defensa, dado que no puede ejecutar los gestos ni presenta varianza temporal ni profundidad 3D.

#### Scenario: Una foto estática no pasa el liveness

- **WHEN** se presenta una foto estática a la cámara
- **THEN** los retos activos no se completan (no hay gestos) y las señales pasivas fallan (varianza ~0, profundidad ~0)
- **THEN** la defensa anti-presentación no se considera superada

#### Scenario: El orden y la dirección aleatorios elevan el costo de un video pregrabado

- **WHEN** se inicia un intento de captura
- **THEN** el orden de los tres gestos se baraja y la dirección del giro se elige al azar
- **THEN** un video pregrabado con una secuencia fija no satisface el reto-respuesta esperado

### Requirement: El alcance PAD del cliente se declara y se reporta al backend, sin sustituir la autoridad server-side

El sistema SHALL reportar al backend las señales del intento (liveness pasivo real, retos resueltos reales y la señal de cámara virtual) como parte de la defensa, y SHALL tratar estas señales como **capas de defensa**, no como veredicto único. El alcance de la defensa client-side SHALL declararse honestamente: cubre ataques de presentación de Nivel 1–2 (fotos, videos de reproducción, máscaras de mediana sofisticación) pero NO garantiza inmunidad a la inyección de cámara ni a deepfakes en tiempo real (límite del paradigma cliente, DD-18). La verificación **autoritativa** SHALL ser la re-inferencia server-side, complementada con verificación continua y revisión humana.

#### Scenario: Las señales se reportan al backend para re-inferencia

- **WHEN** la captura concluye
- **THEN** el sistema reporta al backend `liveness_ok` real, los retos resueltos reales y la señal de cámara virtual
- **THEN** la re-inferencia server-side es la verificación autoritativa, no la del cliente

#### Scenario: El límite de inyección/deepfake se reconoce explícitamente

- **WHEN** se documenta la garantía anti-spoofing del cliente
- **THEN** se declara que no hay inmunidad a inyección de cámara ni deepfakes en tiempo real
- **THEN** la red de seguridad real combina re-inferencia server-side, verificación continua y revisión humana (L2.5)
