# identity-match-1to1 Specification

## MODIFIED Requirements

### Requirement: Comparación 1:1 por distancia coseno con umbral conservador (señal de conveniencia client-side)
El sistema SHALL comparar el embedding capturado contra el embedding de referencia (cargado en C-07, leído cifrado de la DB) mediante distancia coseno, usando un umbral configurado conservadoramente, de modo que rechazar a un legítimo sea preferido por encima de aceptar a un impostor en este paso (RN-BIO-01, RN-BIO-02, RN-BIO-03, US-004 CA-3).

El resultado de esta comparación mostrado al alumno en el navegador SHALL tratarse como **señal de conveniencia / UX**, NO como la verificación autoritativa: la verificación autoritativa es la re-inferencia server-side (cliente = sensor no confiable). El sistema NUNCA SHALL exponer el vector de embedding al cliente ni en logs (dato sensible, Ley 25.326).

#### Scenario: Distancia bajo el umbral es match
- **WHEN** la distancia coseno entre el embedding capturado y el de referencia es menor que el umbral configurado
- **THEN** el sistema considera la comparación 1:1 exitosa

#### Scenario: Distancia sobre el umbral no es match
- **WHEN** la distancia coseno es mayor o igual que el umbral configurado
- **THEN** el sistema considera la comparación fallida y no habilita el examen en ese intento

#### Scenario: El embedding de referencia se lee cifrado
- **WHEN** se ejecuta la comparación 1:1
- **THEN** el embedding de referencia se lee cifrado de la DB y no se expone en claro al cliente

#### Scenario: El resultado client-side no es la autoridad
- **WHEN** se muestra al alumno el resultado de la comparación en el navegador
- **THEN** la verificación autoritativa sigue siendo la re-inferencia server-side, no la del cliente

## ADDED Requirements

### Requirement: El resultado de la comparación 1:1 se presenta al alumno en lenguaje claro y gatea el avance del examen

El sistema SHALL presentar al alumno el resultado de la verificación 1:1 del examen en lenguaje claro (sin jerga visible) y SHALL detener el flujo hasta que el alumno lo reconozca explícitamente, en lugar de avanzar automáticamente. El detalle de la pantalla de resultado se especifica en la capability `exam-verification-result-screen`; esta capability garantiza que la **comparación 1:1** es la fuente del resultado presentado y que su exposición respeta la minimización (sin mostrar el vector).

#### Scenario: El resultado de la comparación gatea el avance
- **WHEN** la comparación 1:1 produce un resultado (coincide o no coincide)
- **THEN** el examen no avanza automáticamente
- **THEN** el alumno debe reconocer el resultado (presentado en lenguaje claro) antes de continuar

#### Scenario: El resultado no expone el vector
- **WHEN** se presenta el resultado de la comparación al alumno
- **THEN** el vector de embedding nunca se muestra; a lo sumo se muestran valores opacos (distancia/umbral) en un detalle opcional, fuera del copy principal
