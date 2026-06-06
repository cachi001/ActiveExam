## ADDED Requirements

### Requirement: El motor de retos captura un baseline neutral del alumno al inicio
El sistema SHALL acumular métricas faciales durante los primeros frames estables con cara detectada antes de iniciar los retos. El baseline SHALL consistir en: `baselineBlinkOpenness` (apertura vertical media del ojo izquierdo, landmarks[159].y − landmarks[145].y), `baselineSmileWidth` (ancho de boca medio, |landmarks[291].x − landmarks[61].x|) y `baselineGazeX` (gaze.x medio). La acumulación de frames para el baseline SHALL comenzar a partir del frame 10 de cara detectada (para evitar subexposición inicial de cámara — OQ-3). El baseline se declara estable cuando se acumulan ≥12 frames válidos (frames 10+) con varianza de posición del centroide de nariz (landmark 1) menor que 0.002, apuntando a una fase baseline total de ~12-15 frames desde la detección. Si después de 60 frames no se estabiliza, el sistema SHALL usar los últimos 10 frames disponibles como baseline (fallback ruidoso). El baseline SHALL invalidarse si `baselineSmileWidth > 0.14` (alumno ya está sonriendo — instrucción incorrecta).

#### Scenario: Baseline capturado con cara estable
- **WHEN** el alumno mantiene la cara centrada y en expresión neutral durante ≥10 frames consecutivos
- **THEN** el sistema declara el baseline estable con las métricas promediadas de esos frames
- **THEN** la máquina de estados transita de `baseline` a `challenge[0]` (primer reto)

#### Scenario: Baseline por timeout (iluminación pobre o cara inestable)
- **WHEN** el alumno lleva 60 frames sin que la varianza de nariz baje del umbral
- **THEN** el sistema usa las métricas de los últimos 10 frames detectados como baseline fallback
- **THEN** la máquina de estados transita igualmente a `challenge[0]`

#### Scenario: Baseline invalidado por sonrisa preexistente
- **WHEN** el `baselineSmileWidth` calculado supera 0.14 (el alumno ya estaba sonriendo)
- **THEN** el sistema descarta el baseline parcial y reinicia la acumulación
- **THEN** la UI muestra "Relajá la expresión y mirá al frente"

#### Scenario: Frame de referencia para embedding capturado en baseline
- **WHEN** el baseline se declara estable (frame N)
- **THEN** el sistema captura el frame N del `<video>` como `bestReferenceFrame`
- **THEN** este frame es el que se entrega al caller en `onComplete` para `computeFaceDescriptor()`, en lugar del último frame del loop

### Requirement: Los retos se evalúan en secuencia estricta, uno a la vez, en orden aleatorio por intento
El sistema SHALL barajar el catálogo `[parpadear, girar_cabeza, sonreír]` con Fisher-Yates (`Math.random()`) al iniciar la captura, produciendo una secuencia aleatoria distinta en cada intento. Solo el reto en la posición `challengeIndex` actual SHALL evaluarse en cada frame. Los retos en otras posiciones NO se evalúan aunque se detecte la acción en el frame. El baseline neutral SHALL capturarse SIEMPRE antes del reto en index 0, independientemente del orden barajado.

Al barajar, si el reto `girar_cabeza` queda en cualquier posición, el sistema SHALL elegir al azar la dirección de giro (`'izquierda'` o `'derecha'`) usando `Math.random()`. Esta dirección se almacena como `turnDirection` y permanece fija durante todo el intento.

#### Scenario: Secuencia barajada al iniciar la captura
- **WHEN** el alumno inicia la captura biométrica
- **THEN** el sistema baraja `[parpadear, girar_cabeza, sonreír]` produciendo una de 6 permutaciones posibles (ej. `[sonreír, parpadear, girar_cabeza]`)
- **THEN** elige aleatoriamente `turnDirection ∈ {izquierda, derecha}`
- **THEN** la UI muestra el primer reto de la secuencia barajada una vez completado el baseline

#### Scenario: Solo el reto activo se evalúa
- **WHEN** el alumno está en el reto activo (cualquier posición) y realiza simultáneamente la acción de otro reto
- **THEN** el sistema no avanza el reto no activo
- **THEN** solo el reto en `challengeIndex` actual se evalúa y acumula frames

#### Scenario: Al completar el reto activo se entra en cooldown
- **WHEN** el acumulador del reto activo alcanza `FRAMES_MIN` consecutivos
- **THEN** el sistema entra en estado `cooldown` de **350 ms**
- **THEN** durante el cooldown ningún reto se evalúa
- **THEN** la UI muestra la confirmación del paso completado

#### Scenario: Al salir del cooldown se activa el siguiente reto
- **WHEN** el cooldown de 350 ms expira
- **THEN** `challengeIndex` avanza al siguiente reto en la secuencia barajada
- **THEN** el acumulador del nuevo reto se inicializa en 0
- **THEN** la UI muestra el label del nuevo reto activo

#### Scenario: Al completar el último reto se entra en fase éxito
- **WHEN** el acumulador del último reto de la secuencia barajada alcanza `FRAMES_MIN` y el cooldown expira
- **THEN** la máquina de estados transita a `done`
- **THEN** el sistema entra en fase `exito` y espera 1.600 ms antes de invocar `onComplete`

### Requirement: La evaluación de cada reto usa delta relativo al baseline neutral
El sistema SHALL evaluar cada reto como un cambio porcentual significativo respecto al baseline capturado, no contra umbrales absolutos globales.

Los umbrales relativos SHALL ser:
- `parpadear`: `openness < baselineBlinkOpenness * 0.45` (el ojo debe cerrarse al menos al 45 % de su apertura en reposo).
- `girar_cabeza`: `|gaze.x| > 0.22` (umbral absoluto ajustado; el giro sigue siendo relativo a la posición del iris, que ya es relativa al ojo — no se usa baseline para giro).
- `sonreír`: `smileWidth > baselineSmileWidth * 1.25` (la boca debe abrirse al menos un 25 % más que en reposo).

#### Scenario: Parpadeo detectado como delta sobre baseline
- **WHEN** el alumno tiene `baselineBlinkOpenness = 0.060` en reposo y cierra el ojo hasta `openness = 0.024`
- **THEN** `0.024 < 0.060 * 0.45 = 0.027` → la condición es verdadera
- **THEN** el frame cuenta para el acumulador del reto `parpadear`

#### Scenario: Sonrisa no dispara falso positivo en reposo
- **WHEN** el alumno tiene `baselineSmileWidth = 0.10` en reposo y la boca está en `smileWidth = 0.105` (leve variación natural)
- **THEN** `0.105 < 0.10 * 1.25 = 0.125` → la condición es falsa
- **THEN** el acumulador de `sonreír` no avanza

#### Scenario: Sonrisa genuina detectada correctamente
- **WHEN** el alumno tiene `baselineSmileWidth = 0.10` y sonríe hasta `smileWidth = 0.14`
- **THEN** `0.14 > 0.10 * 1.25 = 0.125` → la condición es verdadera
- **THEN** el frame cuenta para el acumulador del reto `sonreír`

#### Scenario: Sin baseline disponible, no se evalúa ningún reto
- **WHEN** el baseline aún no se ha capturado (fase `baseline`)
- **THEN** `evaluateChallengeRelative()` retorna `false` para cualquier reto
- **THEN** el acumulador permanece en 0

### Requirement: Los acumuladores de frames mínimos son elevados y se resetean si el reto deja de cumplirse
El sistema SHALL requerir frames CONSECUTIVOS para confirmar un reto. Si en algún frame el reto activo no se cumple, el acumulador de ese reto se resetea a 0. Los mínimos SHALL ser: `parpadear` = **3** frames, `girar_cabeza` = **4** frames, `sonreír` = **4** frames. Estos valores eliminan falsos positivos por ruido mientras mantienen el flujo en el objetivo de ~5-7 s totales.

#### Scenario: Parpadeo requiere 3 frames consecutivos
- **WHEN** el alumno cierra el ojo correctamente durante 2 frames y en el frame 3 lo abre brevemente
- **THEN** el acumulador se resetea a 0 en el frame 3
- **THEN** el reto no se confirma

#### Scenario: Parpadeo confirmado con 3 frames consecutivos
- **WHEN** el alumno cierra el ojo correctamente durante 3 frames consecutivos
- **THEN** el acumulador llega a 3 y el reto `parpadear` se confirma
- **THEN** el sistema entra en cooldown

#### Scenario: Acumulador se resetea si la cara desaparece
- **WHEN** `face_count === 0` durante el reto activo
- **THEN** el acumulador del reto activo se resetea a 0
- **THEN** el reto no avanza

### Requirement: El catálogo de retos secuenciales excluye el reto acercarse; el reto girar_cabeza es direccional y aleatorio
El sistema SHALL definir el catálogo `SEQUENTIAL_CHALLENGES = ['parpadear', 'girar_cabeza', 'sonreír']` como constante exportada. El reto `acercarse` NO SHALL formar parte de los retos del flujo de enrollment o verificación biométrica. El reto `girar_cabeza` SHALL requerir la dirección específica (`turnDirection`) elegida al azar al iniciar el intento; solo el giro hacia esa dirección satisface el reto.

La convención de signo (coherente con el espejo selfie de `enrollmentChallengeDetector.ts`):
- `turnDirection === 'izquierda'` → condición: `gaze.x > +GAZE_TURN_THRESHOLD_ADJUSTED`
- `turnDirection === 'derecha'` → condición: `gaze.x < -GAZE_TURN_THRESHOLD_ADJUSTED`

#### Scenario: Catálogo no incluye acercarse
- **WHEN** se inicializa el flujo de captura biométrica
- **THEN** `desafios` (antes de barajar) contiene exactamente `['parpadear', 'girar_cabeza', 'sonreír']`
- **THEN** `acercarse` no aparece en ningún momento en la secuencia de retos

#### Scenario: girar_cabeza solo acepta el giro en la dirección elegida al azar
- **GIVEN** que `turnDirection = 'derecha'` fue elegida al iniciar este intento
- **WHEN** el alumno gira la cabeza a su DERECHA (`gaze.x < -0.22`)
- **THEN** el reto `girar_cabeza` acumula el frame (dirección correcta)
- **WHEN** el alumno gira la cabeza a su IZQUIERDA (`gaze.x > +0.22`) en el mismo intento
- **THEN** el reto `girar_cabeza` NO acumula el frame (dirección incorrecta)

#### Scenario: Instrucción en pantalla refleja la dirección elegida
- **WHEN** `turnDirection = 'izquierda'` y el reto `girar_cabeza` está activo
- **THEN** la UI muestra "Girá la cabeza a la IZQUIERDA" (no "Girá la cabeza hacia un lado")
- **WHEN** `turnDirection = 'derecha'` y el reto `girar_cabeza` está activo
- **THEN** la UI muestra "Girá la cabeza a la DERECHA"
