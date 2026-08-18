/**
 * Tipos compartidos del frontend — barril.
 *
 * Este archivo tenia 878 lineas con 62 interfaces de cinco dominios distintos.
 * Se partio por dominio en `lib/types/`, y esto quedo como re-exportacion: todos
 * los `import { X } from '../lib/types'` que ya existian siguen funcionando igual.
 *
 * Al agregar un tipo nuevo, ponelo en el modulo de su dominio, no aca.
 */

export * from './types/proctoring-eventos';
export * from './types/usuarios';
export * from './types/alumno';
export * from './types/proctoring-activeexam';
export * from './types/estadisticas';
