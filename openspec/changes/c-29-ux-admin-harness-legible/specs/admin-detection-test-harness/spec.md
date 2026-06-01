## MODIFIED Requirements

### Requirement: Harness de diagnóstico comunica estado del motor
El harness SHALL comunicar de forma inequívoca en su interfaz visual qué componentes del pipeline de visión están funcionando con datos reales y cuáles están en modo stub. Específicamente: cuando el motor MediaPipe no está disponible y `detectFaces` lanza un error que es capturado por el fallback de simulación, el harness SHALL mostrar un indicador prominente de nivel warning que diga que los valores de visión (conteo de rostros, gaze, bounding boxes) son SIMULADOS y no representan una detección real. Este indicador SHALL ser visible desde el primer momento en que el admin accede a la pantalla, sin importar el estado del harness.

#### Scenario: Indicador de motor stub siempre visible
- **WHEN** el admin accede a `/admin/detection-test`
- **THEN** hay un indicador visible de nivel warning que advierte que las señales de visión son simuladas (motor en modo stub)

#### Scenario: Señales de navegador diferenciadas de señales de visión
- **WHEN** el harness muestra señales de entorno (foco, pestaña, fullscreen, portapapeles)
- **THEN** esas señales están claramente diferenciadas como "señales reales del navegador" respecto a las señales de visión simuladas

#### Scenario: El harness permite completar la checklist de cobertura con motor stub
- **WHEN** el motor está en modo stub y el admin realiza acciones de navegador (cambiar pestaña, copiar)
- **THEN** los ítems de checklist correspondientes a señales de navegador se marcan igualmente como verificados

#### Scenario: Explicación de propósito accesible sin conocimiento técnico
- **WHEN** un admin sin conocimiento técnico de MediaPipe usa el harness
- **THEN** puede entender qué está probando (verificar que el sistema detecta señales) y qué resultados esperaría en una sesión real, a partir de la información visible en pantalla
