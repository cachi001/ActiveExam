## 1. Módulo de configuración institucional

- [x] 1.1 Crear `frontend/src/config/institution.ts` con la interfaz `InstitutionConfig` y el objeto `INSTITUTION` exportado, con los valores default de UTN FRM y override por `import.meta.env.VITE_INSTITUTION_*`
- [x] 1.2 Verificar si existe `frontend/src/vite-env.d.ts`; si existe, agregar las 6 variables `VITE_INSTITUTION_*` a `interface ImportMetaEnv`; si no existe, crear el archivo con las declaraciones mínimas de Vite más las variables de institución
- [x] 1.3 Verificar que TypeScript no emite errores en `institution.ts` al acceder a `import.meta.env.VITE_INSTITUTION_*` (requiere paso 1.2 completo)

## 2. Corrección de la shell (footer y soporte)

- [x] 2.1 En `frontend/src/ui/shells.tsx` línea ~110: importar `INSTITUTION` desde `../../config/institution` y reemplazar el string `"Self-hosted · UBA"` por `\`Self-hosted · ${INSTITUTION.nombreCorto}\``
- [x] 2.2 En `frontend/src/ui/shells.tsx` línea ~127: reemplazar el string `"Soporte UBA"` por `{INSTITUTION.soporteLabel}` (o template literal equivalente)

## 3. Corrección de la pantalla de Login

- [x] 3.1 En `frontend/src/screens/Login.tsx` línea ~44: importar `INSTITUTION` y reemplazar `"Universidad de Buenos Aires — UBA"` por la expresión que combine `INSTITUTION.nombre` + `" — "` + `INSTITUTION.nombreCorto` (o `INSTITUTION.facultad` según el diseño visual)
- [x] 3.2 En `frontend/src/screens/Login.tsx` línea ~51: reemplazar el texto del botón `"Ingresar con UBA ID"` por `\`Ingresar con ${INSTITUTION.loginLabel}\`` (o `{INSTITUTION.loginLabel}` si `loginLabel` ya incluye el texto completo)

## 4. Corrección del panel de Revisor

- [x] 4.1 En `frontend/src/screens/Revisor.tsx` línea ~71: importar `INSTITUTION` y reemplazar la parte `"UBA Medicina"` del texto de jurisdicción por `INSTITUTION.nombreCorto` (ej: `\`${INSTITUTION.nombreCorto} · ...\``)

## 5. Corrección de ConfigureExam

- [x] 5.1 En `frontend/src/screens/ConfigureExam.tsx` línea ~17: importar `INSTITUTION` y reemplazar el ID mock `"EX-UBA-..."` para que use `INSTITUTION.idPrefix` como prefijo (ej: `` `EX-${INSTITUTION.idPrefix}-...` ``)

## 6. Corrección de datos mock — staff (api.ts)

- [x] 6.1 En `frontend/src/lib/api.ts` importar `INSTITUTION` desde `../config/institution`
- [x] 6.2 Reemplazar `id_institucional: 'UBA-DOC-1182'` por `` `${INSTITUTION.idPrefix}-DOC-1182` ``
- [x] 6.3 Reemplazar los cuatro emails `@uba.ar` del staff mock (cferreyra, macuna, lmendoza, coordinacion) por emails con dominio `@${INSTITUTION.dominioEmail}` (ej: `` `cferreyra@${INSTITUTION.dominioEmail}` ``)

## 7. Corrección de datos mock — exámenes (api.ts)

- [x] 7.1 Reemplazar ID `'EX-UBA-ANAT-I'` por `` `EX-${INSTITUTION.idPrefix}-AMAT-I` `` y nombre de materia por "Análisis Matemático I"
- [x] 7.2 Reemplazar ID `'EX-UBA-FISIO-II'` por `` `EX-${INSTITUTION.idPrefix}-FIS-I` `` y nombre de materia por "Física I"
- [x] 7.3 Reemplazar ID `'EX-UBA-QUIM-ORG'` por `` `EX-${INSTITUTION.idPrefix}-ALG-I` `` y nombre de materia por "Algoritmos y Estructuras de Datos I"
- [x] 7.4 Reemplazar ID `'EX-UBA-HISTO'` por `` `EX-${INSTITUTION.idPrefix}-SIS-REP` `` y nombre de materia por "Sistemas de Representación"

## 8. Verificación visual

- [x] 8.1 Abrir la aplicación en el navegador y verificar que la pantalla de Login muestra "Universidad Tecnológica Nacional — Facultad Regional Mendoza" y el botón "Ingresar con UTN FRM ID"
- [x] 8.2 Verificar que el footer de la shell muestra "Self-hosted · UTN FRM" y el link de soporte muestra "Soporte UTN FRM"
- [x] 8.3 Verificar que el panel de Revisor muestra "UTN FRM" en lugar de "UBA Medicina" en la jurisdicción
- [x] 8.4 Verificar que la lista de exámenes mock muestra materias de Ingeniería UTN (Análisis Matemático I, Física I, etc.) y no materias de Medicina
- [x] 8.5 Buscar con rg/grep en `frontend/src/` cualquier referencia residual a "UBA" o "uba.ar" o "Buenos Aires" (excluyendo `StyleGuide.html`) — debe retornar cero resultados
