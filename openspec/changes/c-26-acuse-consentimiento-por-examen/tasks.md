## 1. per-exam-consent-acknowledgment (NEW)

- [ ] 1.1 Modelar el tipo `AcuseExamen` (examen_id, version, timestamp, hash simulado, afirmativo) y el estado de acuses por examen en Zustand — Done: el store expone los acuses por `examen_id` y un selector `tieneAcuseExamen(examenId)`.
- [ ] 1.2 Construir la pantalla/paso de acuse por-examen (PascalCase) que muestra el examen específico (cátedra, fecha/hora, duración) y el alcance de monitoreo (cámara, pantalla/foco, pestañas) — Done: la UI renderiza datos del examen + lista de lo que se monitorea, sin re-presentar el texto pesado de perfil.
- [ ] 1.3 Referenciar el consentimiento de perfil vigente (C-22) sin repetirlo ni re-capturar biometría — Done: la pantalla muestra "consentimiento de perfil vigente (versión X)" con enlace al perfil y NO inicia captura biométrica.
- [ ] 1.4 Exigir acción afirmativa explícita sin casilla premarcada para confirmar ESA instancia — Done: sin clic afirmativo no se registra acuse; no hay casilla premarcada ni consentimiento por inacción.
- [ ] 1.5 Implementar `registrarAcuseExamen(examenId, { afirmativo })` en `frontend/src/lib/api.ts`, idempotente por (estudiante, examen), con acuse inmutable (versión + timestamp + hash simulado) — Done: el mock crea el acuse, retorna el existente si ya hay uno afirmativo y no recaptura biometría.

## 2. exam-enrollment (MODIFIED)

- [ ] 2.1 Insertar el paso de acuse por-examen en el flujo de inscripción (de C-21) antes de quedar inscripto/habilitado para ese examen — Done: inscribirse a un examen ofrece el acuse por-examen; sin acuse afirmativo el examen no queda listo para rendir.
- [ ] 2.2 Reflejar el estado del acuse en "Mis exámenes": acción "Completar acuse del examen" cuando falta el acuse para una inscripción — Done: una inscripción sin acuse muestra la acción de completar acuse en lugar de "Rendir".
- [ ] 2.3 No re-capturar biometría ni re-pedir el consentimiento de perfil en el paso de inscripción — Done: la inscripción + acuse no inician captura biométrica ni re-presentan el texto pesado de perfil.

## 3. consent-gate (MODIFIED)

- [ ] 3.1 Extender `puedeRendir(examenId)` para evaluar el gate en capas: perfil completo (C-22) Y acuse por-examen presente y afirmativo para ESE examen — Done: con perfil completo pero sin acuse del examen, `puedeRendir` retorna `{ puede: false, codigo: 'acuse_examen_faltante' }`.
- [ ] 3.2 Preservar los códigos semánticos existentes de C-22 y agregar `acuse_examen_faltante` sin romperlos — Done: si el perfil está incompleto se devuelven los códigos de C-22; solo cuando el perfil está completo y falta el acuse aparece el código nuevo.
- [ ] 3.3 Derivar a completar el acuse (no sancionar) cuando falta — Done: el gate enlaza al paso de acuse del examen; nunca emite veredicto ni sanción automática (L2.5).
