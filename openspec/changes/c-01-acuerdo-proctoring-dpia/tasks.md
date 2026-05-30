# Tasks — C-01 `acuerdo-proctoring-dpia`

> **Naturaleza**: estas tareas son **entregables legales/administrativos**, no de código. Cada una tiene un **Done verificable** (documento firmado / aprobado / acta). El change se completa solo cuando todos los entregables están firmados/aprobados; recién ahí Fase 0 se desbloquea para C-04+.
> Convención: `(Resp.: <rol decisor>)` indica el responsable. Las fechas objetivo las fija el patrocinador al iniciar el gate.

## 1. Aprobación de la línea base de ADRs (capability `adr-approval-baseline`)

- [ ] 1.1 Revisar y aprobar los 14 ADRs Tier 1 DD-01…DD-14; Done: cada uno marcado `Aprobado` en el acta (Resp.: equipo técnico + patrocinador)
- [ ] 1.2 Revisar y aprobar las 5 revisiones A4 DD-15…DD-19; Done: DD-15..DD-19 marcados `Aprobado` en el acta (Resp.: equipo técnico)
- [ ] 1.3 Registrar en el acta que las revisiones A4 prevalecen sobre el SAD original en el MVP (Postgres-como-cola sobre RabbitMQ+Celery; SSE+backplane sobre WebSocket+sticky), con las opciones del SAD documentadas como evolución condicionada a métricas de C-03; Done: jerarquía explícita en el acta (Resp.: equipo técnico)
- [ ] 1.4 Firmar el acta única de aprobación de los 19 ADRs y entregarla al equipo técnico como contrato de arquitectura; Done: acta firmada y distribuida (Resp.: patrocinador + líder técnico)

## 2. Acuerdo de Nivel de Proctoring L2.5 (capability `proctoring-level-agreement`)

- [ ] 2.1 Redactar el Acuerdo declarando nivel L2.5 y descartando explícitamente L3/L4/L5 como fuera de alcance; Done: borrador con nivel declarado (Resp.: legal + líder técnico)
- [ ] 2.2 Incluir cláusula de finalidad acotada (verificar identidad + integridad del examen) y prohibición de reutilización (vigilancia, marketing, cesión); Done: cláusula presente (Resp.: legal)
- [ ] 2.3 Declarar límites deliberados: sin video continuo, sin lockdown, sin sanción automática (toda sanción pasa por revisión humana); Done: límites declarados (Resp.: legal + dirección académica)
- [ ] 2.4 Delimitar el RACI de responsabilidad entre proveedor, institución, DPO y revisores (mitiga L-004); Done: RACI incluido (Resp.: patrocinador + proveedor)
- [ ] 2.5 Recopilar las firmas de patrocinador, dirección académica y proveedor; Done: documento firmado por las tres partes con fecha y versión (Resp.: patrocinador)

## 3. DPIA y paquete de cumplimiento Ley 25.326 (capability `dpia-legal-compliance`)

- [ ] 3.1 Producir el DPIA completo (tratamiento biométrico, riesgos, medidas de mitigación); Done: documento DPIA completo (Resp.: DPO / área legal)
- [ ] 3.2 Documentar la base legal: consentimiento informado libre/expreso/con acción afirmativa, registrado con timestamp y hash, sin usar la relación académica para forzarlo; Done: base legal en el DPIA (Resp.: DPO)
- [ ] 3.3 Fundamentar proporcionalidad (L2.5 + sin video continuo) referenciando la jurisprudencia SRFP (legalidad, necesidad, proporcionalidad, no reutilización); Done: sección de proporcionalidad (Resp.: DPO + legal)
- [ ] 3.4 Documentar garantía de derechos del titular: acceso, rectificación, supresión, portabilidad y oposición a decisiones automatizadas (esta última ya cubierta por revisión humana obligatoria); Done: sección de derechos (Resp.: DPO)
- [ ] 3.5 Iniciar/planificar la inscripción de las bases ante el Registro Nacional de Bases de Datos de la AAIP y confirmar soberanía de datos (self-hosted en el país); Done: constancia de inicio o plan con responsable y fecha (Resp.: legal)
- [ ] 3.6 Aprobar formalmente el DPIA; Done: DPIA con aprobación firmada y fechada por el DPO (Resp.: DPO)

## 4. Clasificación del embedding como dato sensible (capability `sensitive-data-classification`)

- [ ] 4.1 Analizar IN-04 a la luz de la Resolución AAIP 4/2019 y resolver hacia el estándar más exigente (SU-08); Done: análisis documentado (Resp.: DPO)
- [ ] 4.2 Clasificar formalmente el embedding facial como dato sensible por defecto ("responsabilidad reforzada"); Done: clasificación firmada por el DPO (Resp.: DPO)
- [ ] 4.3 Definir las consecuencias técnicas heredadas downstream: cifrado at-rest del embedding, minimización, finalidad acotada y no reutilización; Done: requisitos derivados documentados para C-09/C-19 (Resp.: DPO + líder técnico)

## 5. Vía alternativa y población menor de 18 (capability `alternative-verification-path`)

- [ ] 5.1 Decidir y documentar si se ofrece vía alternativa de verificación sin biometría (p. ej. proctor humano en vivo) y, si se ofrece, su mecanismo; Done: decisión firmada (Resp.: dirección académica + legal)
- [ ] 5.2 Determinar si existe población menor de 18 años entre los evaluados; Done: determinación documentada (Resp.: dirección académica + legal)
- [ ] 5.3 Si hay menores: definir consentimiento parental y retención diferenciada como insumo de C-08/C-19; Done: requisitos para menores documentados o constancia de "no aplica" (Resp.: legal)

## 6. Cierre del gate de Fase 0

- [ ] 6.1 Verificar que todos los entregables de §1–§5 están firmados/aprobados; Done: checklist de cierre completo (Resp.: patrocinador + DPO)
- [ ] 6.2 Comunicar el cierre del gate al equipo y habilitar el inicio de los changes de dominio (C-04+); Done: Fase 0 declarada desbloqueada y acta de cierre distribuida (Resp.: patrocinador)
