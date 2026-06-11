## ADDED Requirements

### Requirement: La confirmación de cada gesto es por tiempo sostenido, no por conteo de frames

El sistema SHALL confirmar un reto de liveness sólo cuando la condición del gesto se cumple de forma sostenida durante al menos un umbral de tiempo configurable (por defecto ~500 ms), medido con un reloj monótono (`performance.now()`), independiente del framerate del loop RAF.

El umbral SHALL ser una constante exportada y ajustable sin re-deploy. Si la condición deja de cumplirse antes de alcanzar el umbral, el temporizador de sostenimiento SHALL reiniciarse a cero.

Este criterio temporal REEMPLAZA al umbral por frames (`FRAMES_MIN_*`) como condición de confirmación; el conteo por frames puede conservarse sólo como derivación interna pero no SHALL ser la condición de aceptación.

#### Scenario: Gesto mantenido el tiempo mínimo confirma
- **WHEN** el alumno sostiene el gesto del reto activo durante ≥ el umbral de tiempo configurado
- **THEN** el reto se marca como completado

#### Scenario: Gesto instantáneo no confirma
- **WHEN** la condición del gesto se cumple sólo por un instante (menos del umbral de tiempo)
- **THEN** el reto NO se marca como completado y el temporizador de sostenimiento se reinicia

#### Scenario: Independencia del framerate
- **WHEN** el loop corre a 60 fps versus 30 fps
- **THEN** el tiempo real requerido para confirmar el gesto es el mismo (no depende de la cantidad de frames)

### Requirement: A lo sumo un reto avanza por gesto (anti doble-paso)

El sistema SHALL avanzar como máximo un reto por cada gesto sostenido. Al confirmar un reto, el sistema SHALL exigir el gate de neutralidad (ver al alumno en estado neutral) antes de empezar a contar positivos del siguiente reto, de modo que el residuo físico del gesto anterior no confirme el siguiente.

El cooldown entre pasos SHALL seguir activo y, durante el cooldown, no SHALL evaluarse ningún reto.

#### Scenario: Residuo del gesto anterior no confirma el siguiente
- **WHEN** el alumno completa un reto y el siguiente reto es satisfecho por el estado físico residual (p. ej. seguir sonriendo)
- **THEN** el gate de neutralidad impide contar positivos hasta ver al alumno en neutral
- **THEN** no se confirman dos retos con un solo gesto

#### Scenario: Un gesto = un avance
- **WHEN** el alumno realiza un único gesto sostenido
- **THEN** avanza exactamente un reto, no dos
