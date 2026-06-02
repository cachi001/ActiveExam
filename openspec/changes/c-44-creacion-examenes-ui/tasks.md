## 1. Preparación y lectura de contexto

- [ ] 1.1 Leer `frontend/src/screens/ConfigureExam.tsx` completo (estado actual post-C-40)
- [ ] 1.2 Leer `frontend/src/ui/components.tsx` — verificar props de `FormField` (label, hint, error), `RangeInput`, `Button`, `Card`, `SectionTitle`
- [ ] 1.3 Leer `frontend/src/lib/types.ts` — verificar tipo `Examen` y `TipoEvento`
- [ ] 1.4 Leer `frontend/src/lib/api.ts` — verificar la firma de `api.saveExam()` (sin cambiarla)
- [ ] 1.5 Verificar que el directorio `frontend/src/screens/admin/components/` existe (creado por C-43); si no existe, crearlo

## 2. Componente DetectoresSelector

- [ ] 2.1 Crear `frontend/src/screens/admin/components/DetectoresSelector.tsx` con props `value: TipoEvento[]` y `onChange: (detectores: TipoEvento[]) => void`
- [ ] 2.2 El componente muestra un checkbox por cada detector en la constante `DETECTORES` (importada o definida localmente)
- [ ] 2.3 Cada checkbox aplica el estilo visual existente (bg-primary-fixed/40 si activo, border-outline-variant/40 si inactivo) usando las clases del design system
- [ ] 2.4 El componente muestra el resumen "N de M detectores activos" encima o debajo de la grilla de checkboxes
- [ ] 2.5 El componente usa `TIPO_EVENTO_LABEL` de `api.ts` para las etiquetas de cada detector

## 3. Componente ExamenResumenCard

- [ ] 3.1 Crear `frontend/src/screens/admin/components/ExamenResumenCard.tsx` con prop `examen: Examen`
- [ ] 3.2 Renderizar la tarjeta con `Card` del design system
- [ ] 3.3 Mostrar nombre (o "—" si vacío), cátedra (o "—"), fecha formateada en español local (usar `new Date(examen.inicio).toLocaleString('es-AR', { ... })`)
- [ ] 3.4 Mostrar duración en minutos, umbral de cola de revisión (con "%")
- [ ] 3.5 Mostrar cantidad de detectores activos con la aclaración "priorizan sesiones para revisión humana, no sancionan" (semántica L2.5)
- [ ] 3.6 Mostrar retención en días con la referencia "(Ley 25.326)"
- [ ] 3.7 Usar `Icon` de `components.tsx` para íconos decorativos (assignment, schedule, shield, visibility) si mejoran la legibilidad; no es obligatorio si complica el layout

## 4. Lógica de validación inline en ConfigureExam

- [ ] 4.1 Agregar cálculo de errores vía `useMemo` que retorna `Record<string, string>` con los campos que fallan
- [ ] 4.2 Implementar regla: `nombre` requerido → mensaje "El nombre del examen es requerido"
- [ ] 4.3 Implementar regla: `catedra` requerida → mensaje "La cátedra es requerida"
- [ ] 4.4 Implementar regla: `inicio` debe ser fecha futura (> now + 5 min) → mensaje "El inicio debe ser en el futuro"
- [ ] 4.5 Implementar regla: `duracion_min` entre 30 y 180 → mensaje "La duración debe estar entre 30 y 180 minutos"
- [ ] 4.6 Implementar regla: `umbral_score` entre 30 y 90 → mensaje "El umbral debe estar entre 30 y 90"
- [ ] 4.7 Implementar regla: `retencion_dias` entre 7 y 90 → mensaje "La retención debe estar entre 7 y 90 días"
- [ ] 4.8 Eliminar el `alert()` existente en la función `guardar`
- [ ] 4.9 La función `guardar` usa `if (Object.keys(errors).length > 0) return;` como guard adicional (defensa en profundidad, el botón ya estará disabled)

## 5. Integración en ConfigureExam

- [ ] 5.1 Pasar `error={errors.nombre}` al `FormField` del nombre
- [ ] 5.2 Pasar `error={errors.catedra}` al `FormField` de la cátedra
- [ ] 5.3 Pasar `error={errors.inicio}` al `FormField` del inicio
- [ ] 5.4 Reemplazar el bloque de checkboxes inline por `<DetectoresSelector value={form.detectores} onChange={(d) => set('detectores', d)} />`
- [ ] 5.5 Agregar la sección "Resumen del examen" con `SectionTitle` y renderizar `<ExamenResumenCard examen={form} />`
- [ ] 5.6 Aplicar `disabled={Object.keys(errors).length > 0 || guardando}` al botón Guardar
- [ ] 5.7 Reorganizar el layout en tres secciones con sus `SectionTitle` ("Información del examen", "Parámetros de proctoring", "Resumen del examen")
- [ ] 5.8 Mover los botones Cancelar/Guardar debajo de la Card de resumen

## 6. Verificación visual y de comportamiento

- [ ] 6.1 Verificar que con nombre vacío al cargar la pantalla, el botón Guardar está deshabilitado (sin mensajes de error visibles hasta que el usuario toque el campo — revisar si corresponde mostrar errores eager o lazy; preferir lazy: mostrar error solo tras el primer `blur` del campo)
- [ ] 6.2 Verificar que el preview se actualiza en tiempo real al tipear en nombre y cátedra
- [ ] 6.3 Verificar que el preview muestra "—" para campos vacíos
- [ ] 6.4 Verificar que `DetectoresSelector` muestra el resumen "N de M detectores activos" correctamente
- [ ] 6.5 Verificar que el flujo de guardado exitoso navega a `/admin/examenes` sin errores en consola
- [ ] 6.6 Verificar que el formulario de edición (cuando `editando` no es null) también aplica la validación y el preview correctamente
