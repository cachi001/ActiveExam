## Context

El frontend tiene 13 referencias hardcodeadas a "UBA" dispersas en cuatro archivos de UI y en los datos mock de `api.ts`. La institución real es UTN Regional Mendoza (FRM). No existe ningún punto central de configuración institucional: cada archivo repite el nombre a mano.

El stack es React 18 + Vite + Zustand + Tailwind. Las referencias están en:
- `frontend/src/ui/shells.tsx` (footer y soporte)
- `frontend/src/screens/Login.tsx` (título y botón de ingreso)
- `frontend/src/screens/Revisor.tsx` (header de jurisdicción)
- `frontend/src/screens/ConfigureExam.tsx` (ID de examen mock)
- `frontend/src/lib/api.ts` (datos mock: staff y exámenes)

El alumno mock ya usa UTN FRM correctamente (`FRM-23-4912`, `ecaceres@frm.utn.edu.ar`), lo que confirma que el dominio institucional correcto es `frm.utn.edu.ar`.

## Goals / Non-Goals

**Goals:**
- Centralizar la identidad institucional en `frontend/src/config/institution.ts`
- Corregir las 13 referencias hardcodeadas a "UBA" para que lean del config central
- Reemplazar materias de Medicina por materias canónicas de carreras de Ingeniería UTN en los mocks
- Soportar override por variables de entorno `VITE_INSTITUTION_*` para futura multi-tenancy
- Alcance acotado: solo branding y mocks, sin refactor de componentes ni lógica de negocio

**Non-Goals:**
- Implementar soporte multi-tenant real (el override env es solo la infraestructura mínima)
- Modificar lógica de autenticación, rutas, APIs ni contratos de backend
- Tocar `frontend/src/screens/html/StyleGuide.html` (archivo legacy muerto, fuera de scope)
- Refactorizar la estructura de componentes (PascalCase ya es correcto en todos los archivos)
- Agregar tests nuevos (cambios cosméticos y de strings)

## Decisions

### D-01: Módulo de config en `frontend/src/config/institution.ts`

**Decisión**: Crear un módulo TypeScript puro que exporte un objeto `INSTITUTION` con los datos canónicos de UTN FRM, con soporte de override por env var.

**Alternativas consideradas**:
- **A) Constants dispersas en cada componente**: descartado — es exactamente el problema actual.
- **B) Variable en Zustand store**: descartado — la identidad institucional no es estado reactivo, es configuración estática de la plataforma; no necesita reactividad ni persistencia.
- **C) JSON en `public/`**: descartado — requiere fetch asíncrono, agrega complejidad innecesaria para datos estáticos.
- **D) Módulo TypeScript estático con env var override**: elegido — import directo, tipado, tree-shakeable, compatible con Vite, permite override en CI/CD sin cambiar código.

**Forma del objeto** (contrato):
```typescript
export interface InstitutionConfig {
  nombre: string;           // "Universidad Tecnológica Nacional"
  facultad: string;         // "Facultad Regional Mendoza"
  nombreCorto: string;      // "UTN FRM"
  sigla: string;            // "FRM"
  dominioEmail: string;     // "frm.utn.edu.ar"
  idPrefix: string;         // "FRM"  (usado para IDs de exámenes, staff, etc.)
  loginLabel: string;       // "UTN FRM ID"  (texto del botón de ingreso)
  soporteLabel: string;     // "Soporte UTN FRM"
}

export const INSTITUTION: InstitutionConfig = {
  nombre: import.meta.env.VITE_INSTITUTION_NOMBRE ?? "Universidad Tecnológica Nacional",
  facultad: import.meta.env.VITE_INSTITUTION_FACULTAD ?? "Facultad Regional Mendoza",
  nombreCorto: import.meta.env.VITE_INSTITUTION_NOMBRE_CORTO ?? "UTN FRM",
  sigla: import.meta.env.VITE_INSTITUTION_SIGLA ?? "FRM",
  dominioEmail: import.meta.env.VITE_INSTITUTION_DOMINIO ?? "frm.utn.edu.ar",
  idPrefix: import.meta.env.VITE_INSTITUTION_ID_PREFIX ?? "FRM",
  loginLabel: import.meta.env.VITE_INSTITUTION_LOGIN_LABEL ?? "UTN FRM ID",
  soporteLabel: import.meta.env.VITE_INSTITUTION_SOPORTE_LABEL ?? "Soporte UTN FRM",
};
```

### D-02: Materias de Ingeniería UTN para reemplazar las de Medicina

**Decisión**: Reemplazar los cuatro exámenes mock (Anatomía I, Fisiología II, Química Orgánica, Histología) por materias canónicas del ciclo básico de Ingeniería UTN:

| ID anterior | ID nuevo | Materia |
|---|---|---|
| `EX-UBA-ANAT-I` | `EX-FRM-AMAT-I` | Análisis Matemático I |
| `EX-UBA-FISIO-II` | `EX-FRM-FIS-I` | Física I |
| `EX-UBA-QUIM-ORG` | `EX-FRM-ALG-I` | Algoritmos y Estructuras de Datos I |
| `EX-UBA-HISTO` | `EX-FRM-SIS-REP` | Sistemas de Representación |

Estas materias pertenecen al Ciclo Básico Unificado (CBU) de las carreras de Ingeniería en UTN FRM, son reconocibles y coherentes con el contexto institucional.

### D-03: Patrón de consumo en UI — import directo, sin hook

**Decisión**: Los componentes importan `INSTITUTION` directamente (`import { INSTITUTION } from '../config/institution'`). No se crea un hook `useInstitution()` ni un context provider.

**Rationale**: La configuración es estática en tiempo de ejecución (resuelve en build o en env var al inicio). Añadir un hook o context sería sobre-ingeniería para datos que no cambian durante la sesión. Si en el futuro se requiere cambio dinámico (multi-tenant con switch de institución en runtime), se puede migrar entonces.

### D-04: Compatibilidad de tipo con `import.meta.env`

**Decisión**: Para que TypeScript no se queje de `import.meta.env.VITE_*`, agregar las variables al archivo `frontend/src/vite-env.d.ts` (o crearlo si no existe) bajo `interface ImportMetaEnv`.

## Risks / Trade-offs

- **[Riesgo] Valores de env var en producción no configurados** → Si se despliega sin setear `VITE_INSTITUTION_*`, el sistema usa los defaults UTN FRM hardcodeados en el módulo. Esto es el comportamiento correcto para el caso de uso actual. Documentar los nombres de las variables en el `README` o `.env.example`.
- **[Riesgo] Divergencia entre `api.ts` y la UI** → Al usar `INSTITUTION.idPrefix` e `INSTITUTION.dominioEmail` en los mocks, se garantiza consistencia. Si alguien edita el config central, los mocks se actualizan automáticamente.
- **[Trade-off] Variables de entorno resueltas en build-time** → Con Vite, `import.meta.env.VITE_*` se resuelve en tiempo de compilación (no en runtime del servidor). Para soporte multi-tenant real se necesitaría un enfoque diferente (config inyectada por el server, no por el bundler). Aceptable para el MVP actual.
- **[Riesgo] StyleGuide.html no actualizado** → Se deja intencionalmente fuera de scope (archivo legacy muerto que no se sirve al usuario). Si se reactiva en el futuro, requerirá un change separado.

## Migration Plan

1. Crear `frontend/src/config/institution.ts` con el objeto `INSTITUTION`.
2. Actualizar `frontend/src/vite-env.d.ts` para declarar las variables `VITE_INSTITUTION_*`.
3. Modificar `frontend/src/ui/shells.tsx` para importar y usar `INSTITUTION`.
4. Modificar `frontend/src/screens/Login.tsx` para importar y usar `INSTITUTION`.
5. Modificar `frontend/src/screens/Revisor.tsx` para importar y usar `INSTITUTION`.
6. Modificar `frontend/src/screens/ConfigureExam.tsx` para usar `INSTITUTION.idPrefix`.
7. Modificar `frontend/src/lib/api.ts` para usar `INSTITUTION.idPrefix` y `INSTITUTION.dominioEmail` en los mocks (staff y exámenes).
8. Verificar visualmente en el navegador que login, footer, panel de revisor y listado de exámenes muestran UTN FRM.

**Rollback**: revertir los cambios de los 7 archivos; no hay cambios de base de datos ni contratos de API.

## Open Questions

- **¿Existe un `.env.example` en el frontend?** Si existe, agregar las variables `VITE_INSTITUTION_*` ahí. Si no existe, crearlo o agregarlo al `.env.example` raíz del monorepo (depende de la estructura que establezca C-04).
- **¿Existe `frontend/src/vite-env.d.ts`?** Verificar al implementar; si no existe, crear con las declaraciones mínimas.
