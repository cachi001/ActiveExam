# frontend/src — estructura por features

Scaffolding del frontend (React + Vite + Zustand + Tailwind). C-04 fija el arbol
canonico (cierra SU-07); el codigo de cada feature llega en changes posteriores.

| Carpeta | Responsabilidad |
|---------|-----------------|
| `features/` | Examen, biometria, consentimiento, panel-proctor, cola-revision (vertical slices). |
| `shared/` | UI, hooks, store (Zustand) reutilizables. |
| `vision/` | Motor de vision ABSTRAIDO (impl. MediaPipe) en Web Worker. |
| `proctoring/` | Detectores de pestana/foco/monitores, liveness, anti-tampering. |
| `transport/` | WS estudiante, SSE panel, upload por URL firmada, buffer IndexedDB. |
| `pages/` | Composicion de rutas/paginas. |

Convencion: componentes en **PascalCase** (archivo y nombre), p. ej. `ProctorPanel.tsx`.
