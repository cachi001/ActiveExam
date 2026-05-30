# Legal y Cumplimiento (Argentina)

> **Aviso de la fuente**: resume el marco aplicable a mayo de 2026 con fines de planificación; **no constituye asesoramiento legal**. El área legal y de protección de datos debe validar cada punto y completar el DPIA antes del desarrollo. El marco está en reforma; el diseño debe anticipar el estándar más exigente.

## Norma aplicable y autoridad de control

- **Ley 25.326** de Protección de Datos Personales (habeas data), con jerarquía constitucional desde la reforma de 1994 (art. 43).
- Reglamentada por el **Decreto 1558/2001**.
- Autoridad de control: **AAIP** (Agencia de Acceso a la Información Pública).
- Argentina ratificó el **Convenio 108+** del Consejo de Europa (alineación con estándares internacionales).
- Supletoriamente: derecho a la privacidad del art. 19 de la Constitución.

## Estado de la reforma (señal de diseño)

Hay proyectos de reforma integral en el Congreso, inspirados en el anteproyecto de la AAIP y alineados con RGPD y LGPD. Novedades relevantes: datos biométricos como categoría definida, responsabilidad proactiva y demostrada, privacidad por diseño y por defecto, nuevas bases legales (interés legítimo), derechos de portabilidad y de oposición a decisiones automatizadas.

**Recomendación**: diseñar contra el estándar reformado (evita retrabajo y posiciona por delante del cambio normativo).

## ¿Los embeddings son "datos sensibles"?

- **Resolución AAIP 4/2019** (Anexo I, criterio 4): en Argentina los datos biométricos son sensibles **únicamente cuando pueden revelar información adicional potencialmente discriminatoria** (origen étnico, salud). Difiere del RGPD (donde el biométrico identificatorio es sensible por definición).
- **Recomendación de diseño**: tratar el embedding como **sensible por defecto** y aplicar "responsabilidad reforzada". El costo de sobre-proteger es bajo; el de sub-proteger, alto. (Ver IN-04 en `10_preguntas_abiertas.md`.)

## Base legal del tratamiento

| Base | Aplicación recomendada |
|------|------------------------|
| Consentimiento informado | Base principal para la captura biométrica: libre, expreso e informado, con acción afirmativa (no casillas premarcadas), registrado con timestamp y hash |
| Relación contractual / académica | Puede apoyar parte del tratamiento, pero NO debe usarse para forzar el consentimiento biométrico |
| Alternativa sin biometría | Ofrecer una vía alternativa de verificación (p. ej. proctor humano en vivo) para quien no consienta, de modo que el consentimiento sea genuinamente libre |

## Lección de la jurisprudencia: caso SRFP

El Sistema de Reconocimiento Facial de Prófugos (CABA) fue objeto de amparos colectivos; los tribunales fijaron límites de **legalidad, necesidad y proporcionalidad** y ordenaron suspender/rediseñar. Lecciones directas:

- **Finalidad acotada y declarada**: biometría solo para verificar identidad en el examen, nunca otros fines.
- **Proporcionalidad**: L2.5 + ausencia de video continuo son argumentos jurídicos de proporcionalidad.
- **Control independiente y trazabilidad**: el audit log inmutable responde a la objeción de "ausencia de controles".
- **No reutilización**: prohibición explícita de cruzar la base con otra finalidad (vigilancia, marketing, cesión).

## Menores de edad

Si se evalúa a menores de 18, el consentimiento lo presta quien ejerce la responsabilidad parental, con consideraciones reforzadas. Recomendación: identificar tempranamente población menor y, de haberla, flujo de consentimiento y retención diferenciado, validado por legal.

## Registro, DPIA y derechos del titular

- Inscribir las bases en el **Registro Nacional de Bases de Datos** de la AAIP (la reforma prevé eliminarlo, pero hoy sigue vigente).
- Producir un **DPIA** antes del desarrollo (contemplado en Fase 0).
- Garantizar derechos: acceso, rectificación, supresión y —anticipando la reforma— portabilidad y **oposición a decisiones automatizadas** (ya cumplido por arquitectura: ninguna sanción es automática).

## Checklist de cumplimiento (Argentina)

| Obligación | Estado en el diseño actual |
|-----------|----------------------------|
| Consentimiento libre, expreso e informado | Cubierto (flujo con hash). **Agregar vía alternativa sin biometría** |
| Tratar embeddings como dato sensible (responsabilidad reforzada) | Recomendado: cifrado at-rest previsto; **formalizar la clasificación** |
| Finalidad acotada y no reutilización | Cubierto por diseño; formalizar en política y Acuerdo de Nivel de Proctoring |
| Proporcionalidad (L2.5, sin video continuo) | Cubierto por arquitectura |
| Audit log y control de accesos independiente | Cubierto (audit log inmutable) |
| DPIA previa al desarrollo | Previsto en Fase 0 |
| Inscripción de la base ante la AAIP | **Acción pendiente del área legal** |
| Derechos del titular (incl. oposición a decisiones automatizadas) | Cubierto: revisión humana obligatoria; **portabilidad a implementar** |
| Retención y supresión verificable | Previsto (retención configurable + eliminación al egreso) |
| Soberanía de datos (datos en el país) | Cubierto: self-hosted en infraestructura institucional |
