# biometric-gesture-progress-ring Specification

## ADDED Requirements

### Requirement: El anillo de progreso se renderiza en el borde exterior del óvalo

El anillo de progreso de la captura biométrica SHALL renderizarse en el **borde exterior** del óvalo, fuera del recorte (`clip-path`) del video, de modo que el trazo no se superponga a la imagen del rostro del alumno. El sistema NO SHALL dibujar el anillo de progreso por dentro del óvalo, sobre la imagen de cámara.

El trazo del anillo SHALL ser fino y minimalista (grosor reducido respecto del trazo grueso previo), tanto en el track de fondo como en el trazo de progreso.

#### Scenario: El anillo queda en el contorno externo, no sobre la cara

- **WHEN** se renderiza la captura con el óvalo de cámara visible
- **THEN** el anillo de progreso se dibuja en el borde exterior del óvalo
- **THEN** el trazo no se superpone a la imagen del rostro recortada por el `clip-path`

#### Scenario: Trazo fino y minimalista

- **WHEN** se renderiza el anillo de progreso
- **THEN** el grosor del trazo es menor que el grosor grueso previo (más minimalista)

### Requirement: El anillo se llena de verde progresivamente como barra de carga circular

Mientras el alumno sostiene el gesto correcto del reto activo, el anillo SHALL llenarse de forma progresiva (de 0 a 1) en color verde, comunicando un avance tipo barra de carga circular alrededor del óvalo. El relleno SHALL avanzar de forma continua y frame-rate independiente (proporcional al tiempo efectivo de gesto cumplido, no al conteo de frames).

#### Scenario: El relleno avanza mientras el gesto se sostiene

- **WHEN** el alumno sostiene el gesto correcto del reto activo
- **THEN** el arco verde del anillo crece progresivamente hacia el perímetro completo

#### Scenario: El relleno completo coincide con la confirmación del reto

- **WHEN** el relleno del gesto activo alcanza el 100%
- **THEN** el reto se considera confirmado (coherente con el criterio de hold por tiempo)
