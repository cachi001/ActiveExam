# Spec — consent-gate (delta C-26)

> El gate de habilitación pasa a ser EN CAPAS: consentimiento de perfil vigente (C-22) Y acuse por-examen para ESE examen (C-26). Resuelve la pregunta abierta de C-22. Delta sobre la capability de C-22.

## MODIFIED Requirements

### Requirement: Consentimiento es prerrequisito de la verificación biométrica
El sistema SHALL exigir un consentimiento válido registrado o la elección de la vía alternativa sin biometría antes de habilitar la captura de referencia biométrica del enrollment de perfil; un estudiante que no resolvió ninguno de los dos SHALL NO poder completar el enrollment ni quedar habilitado para inscribirse o rendir. El gate de **perfil** SHALL resolverse una sola vez al completar el perfil, NO antes de cada examen (RN-CO-01, DD-03). Adicionalmente, la **habilitación para rendir un examen concreto** SHALL ser un gate EN CAPAS: requiere el consentimiento de perfil vigente **Y** un acuse por-examen afirmativo para ESE examen (C-26, finalidad específica — Ley 25.326). La falta del acuse por-examen NO SHALL sancionar: SHALL derivar a completarlo (L2.5).

#### Scenario: Con consentimiento válido se habilita la captura de referencia en el perfil
- **WHEN** un estudiante tiene un acuse de consentimiento válido registrado en su perfil
- **THEN** el sistema habilita la captura de referencia biométrica del enrollment

#### Scenario: Sin consentimiento ni vía alternativa, el enrollment no se habilita
- **WHEN** un estudiante no tiene consentimiento registrado ni eligió la vía alternativa en su perfil
- **THEN** el sistema no habilita la captura de referencia biométrica ni marca el perfil como completo

#### Scenario: Con vía alternativa elegida, la biometría no se exige
- **WHEN** un estudiante eligió la vía alternativa sin biometría en su perfil
- **THEN** el sistema no exige la captura de referencia biométrica y dirige la verificación al proctor humano

#### Scenario: El consentimiento de perfil aplica como base a todas las rendiciones, sin re-pedirse
- **WHEN** un estudiante con consentimiento válido vigente en su perfil inicia el pre-examen de cualquier examen
- **THEN** el sistema no vuelve a solicitar el consentimiento de perfil ni re-captura biometría y reutiliza el acuse de perfil como base de licitud

#### Scenario: La habilitación para rendir requiere además el acuse por-examen
- **WHEN** un estudiante tiene el perfil completo (consentimiento de perfil vigente + biometría vigente) pero no otorgó el acuse por-examen para ESE examen
- **THEN** el sistema no habilita la rendición de ese examen y deriva al estudiante a completar el acuse por-examen
- **THEN** el sistema no sanciona ni emite veredicto automático
