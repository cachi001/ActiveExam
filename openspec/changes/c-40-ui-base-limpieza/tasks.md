## 1. Flag de herramientas de desarrollo

- [x] 1.1 Crear `frontend/src/lib/devConfig.ts` con la constante `DEV_TOOLS_ENABLED = import.meta.env.VITE_DEV_TOOLS === '1'`
- [x] 1.2 Agregar `VITE_DEV_TOOLS=0` con comentario explicativo a `frontend/.env.example` (o crearlo si no existe) — NOTA: permisos del sistema impidieron crear el archivo; documentar manualmente como paso pendiente para el coordinador.
- [x] 1.3 En `frontend/src/App.tsx` envolver `<ScreenNavigator />` con `{DEV_TOOLS_ENABLED && <ScreenNavigator />}` importando desde `lib/devConfig`

## 2. Sistema de tamaños del componente Button

- [x] 2.1 En `frontend/src/ui/components.tsx` agregar el tipo `type Size = 'sm' | 'md' | 'lg'` y el mapa `SIZE_CLASSES` con las clases Tailwind para cada tamaño (`h-9 px-md` / `h-12 px-lg` / `h-14 px-xl`)
- [x] 2.2 Agregar la prop `size?: Size` (default `'md'`) a la interfaz del componente `Button` y aplicar `SIZE_CLASSES[size]` en el className interno (reemplazando el `h-12 px-lg` hardcodeado)
- [x] 2.3 En `frontend/src/screens/Login.tsx:49` reemplazar `className="w-full h-14"` por `size="lg" className="w-full"` en el `<Button>` de ingreso
- [x] 2.4 Auditar todos los usos de `<Button` en el codebase y migrar los overrides de tamaño via `className` (`h-9`, `h-12`, `h-14`) a la prop `size` correspondiente

## 3. Corrección de stacks de botones sin gap

- [x] 3.1 En `frontend/src/screens/AdminDashboard.tsx` (sección "Acciones rápidas", ~:57-59) agregar `space-y-sm` al contenedor de los tres botones `w-full`
- [x] 3.2 Revisar `Proctor.tsx` y `AuditPrivacy.tsx` en busca de stacks `w-full` sin gap y corregir con `space-y-sm` o `flex flex-col gap-sm` donde aplique

## 4. Primitivas de formulario

- [x] 4.1 En `frontend/src/ui/components.tsx` agregar el componente `FormField` exportado con las props `label`, `hint?`, `error?`, `children`, `className?` según el diseño en design.md D-2
- [x] 4.2 En `frontend/src/ui/components.tsx` agregar el componente `RangeInput` exportado que usa `FormField` internamente, con `accent-primary` (no hex hardcodeado) y label dinámico `"${label}: ${value}${unit}"` según design.md D-3
- [x] 4.3 En `frontend/src/screens/ConfigureExam.tsx` eliminar el componente local `Field` y reemplazar todos los usos por `FormField` importado de `ui/components`
- [x] 4.4 En `frontend/src/screens/ConfigureExam.tsx` reemplazar el `<input type="range">` del campo "Duración" por `<RangeInput label="Duración" unit="minutos" ... />`
- [x] 4.5 En `frontend/src/screens/ConfigureExam.tsx` reemplazar el `<input type="range">` del campo "Umbral de cola de revisión" por `<RangeInput label="Umbral de cola de revisión" unit="%" ... />`

## 5. Limpieza de jerga visible — pantallas de estudiante

- [x] 5.1 En `frontend/src/screens/EquipmentCheck.tsx:107` quitar el sufijo `(modo demo)` del mensaje de fallas; el mensaje queda `"{fallas} requisito(s) con observaciones — podés continuar"`
- [x] 5.2 En `frontend/src/screens/StudentProfile.tsx:595` eliminar el bloque "Control de demostración" (label del ícono `science`) condicional a `DEV_TOOLS_ENABLED` (task 1.3 ya oculta el bloque; verificar que también aplique aquí)
- [x] 5.3 En `frontend/src/screens/StudentProfile.tsx:602` el botón "Demo: simular deriva embedding" queda envuelto por la condición `DEV_TOOLS_ENABLED` del paso anterior (verificar que el bloque completo quede condicional, no solo el botón)
- [x] 5.4 En `frontend/src/screens/StudentProfile.tsx:688` reemplazar `"Disponible próximamente"` por `"No disponible en esta versión"` conservando el resto del texto (Ley 25.326)
- [x] 5.5 En `frontend/src/screens/enrollment/EnrollmentDniStep.tsx:134` cambiar `"Datos extraídos por OCR (demo)"` a `"Datos extraídos por OCR"` (solo el encabezado de sección; el body del disclaimer L2.5 permanece igual)
- [x] 5.6 En `frontend/src/screens/enrollment/EnrollmentDniStep.tsx:205` cambiar el encabezado `"Análisis indicativo (demo)"` a `"Análisis indicativo"` sin tocar el body del disclaimer

## 6. Limpieza de jerga visible — pantallas de admin y navegador

- [x] 6.1 En `frontend/src/ui/ScreenNavigator.tsx:70` cambiar el atributo `title` del botón flotante de `"Navegador de pantallas (demo)"` a `"Navegador de pantallas"`
- [x] 6.2 En `frontend/src/ui/ScreenNavigator.tsx:79` cambiar `api.modoDemo ? 'Modo demo' : 'Backend real'` a `api.modoDemo ? 'Modo simulación' : 'Backend real'`
- [x] 6.3 En `frontend/src/screens/AdminDetectionHarness.tsx:863` reformular `"Las señales de visión siguen siendo del stub"` por `"Las señales de visión corresponden al motor de respaldo (sin MediaPipe)"`
- [x] 6.4 En `frontend/src/screens/ConfigureExam.tsx:41` cambiar `placeholder="Ej: Examen Final — Anatomía I"` a `placeholder="Nombre del examen"`
- [x] 6.5 En `frontend/src/screens/ConfigureExam.tsx:46` cambiar `placeholder="Ej: Cátedra B"` a `placeholder="Nombre de la cátedra"`

## 7. Verificación integral

- [x] 7.1 Verificar que con `VITE_DEV_TOOLS=0` (o no definida) el ScreenNavigator no aparece y el bloque de simulación de deriva tampoco
- [x] 7.2 Verificar que con `VITE_DEV_TOOLS=1` ambas herramientas aparecen y funcionan igual que antes
- [x] 7.3 Verificar que el flujo completo del alumno (login → perfil → mis-examenes) funciona sin el ScreenNavigator
- [x] 7.4 Verificar que `<Button size="sm">`, `<Button>` (default), y `<Button size="lg">` renderizan con las alturas correctas (`h-9`, `h-12`, `h-14`)
- [x] 7.5 Verificar que `FormField` y `RangeInput` renderizan correctamente en ConfigureExam y que los sliders funcionan
- [x] 7.6 Hacer un grep de `"demo"`, `"stub"`, `"Ej:"` y `"modo demo"` en `frontend/src` para confirmar que no quedan instancias visibles al usuario (los comentarios de código no cuentan)
- [x] 7.7 Verificar que los disclaimers L2.5 de EnrollmentDniStep (body completo) están intactos
